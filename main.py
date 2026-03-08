"""Main Entry Point - CLI for Agent-Loop

A long-running autonomous AI agent system with session management,
task execution, and human intervention capabilities.
"""

import argparse
import os
import sys
import signal
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

# 添加当前目录到路径
sys.path.insert(0, str(Path(__file__).parent))

# Configure structured logging
from agent.logging_ import configure_logging, get_logger

# Get log level and file from environment variables
log_level = os.environ.get("LOG_LEVEL", "INFO")
log_file = os.environ.get("LOG_FILE", "")

# Configure logging - use JSON format if log file is specified, otherwise console
json_output = bool(log_file)
configure_logging(log_level=log_level, log_file=log_file, json_output=json_output)
logger = get_logger(__name__)

from agent.state_manager import StateManager
from agent.task_selector import TaskSelector
from agent.agent_core import AgentCore
from agent.session_manager import SessionManager
from agent.git_helper import GitHelper
from agent.config_reloader import ConfigReloader
from agent.prompt_manager import PromptManager
from agent.model_provider import (
    ModelProviderManager,
    create_provider_manager,
    ProviderHealthStatus,
    mask_api_key,
)
from agent.console import (
    agent_output,
    console,
    print_header,
    print_success,
    print_error,
    print_warning,
    print_info,
    print_task_table,
    print_status_panel,
    print_run_summary,
    create_progress,
    print_init_info,
    print_reload_result,
    print_prompt_list,
    print_template_list,
)

# 全局 shutdown 标志
_shutdown_requested = False

# CLI version
__version__ = "0.1.0"


def _signal_handler(signum: int, frame: Any) -> None:
    """处理 SIGINT/SIGTERM 信号，实现优雅关闭"""
    global _shutdown_requested
    if _shutdown_requested:
        agent_output.render_shutdown_notice(signal.Signals(signum).name, force=True)
        sys.exit(1)
    sig_name = signal.Signals(signum).name
    agent_output.render_shutdown_notice(sig_name)
    _shutdown_requested = True


def init_project(args: argparse.Namespace) -> None:
    """初始化项目"""
    print_info("Initializing Agent-Loop project...")

    state_manager = StateManager(args.project_dir if args.project_dir else None)
    git_helper = GitHelper(args.project_dir if args.project_dir else None)

    # 初始化git仓库
    if not git_helper.is_git_repo():
        print_info("Initializing git repository...")
        git_helper.init_repo()

    # 创建 .agent 目录
    state_manager.agent_dir.mkdir(parents=True, exist_ok=True)

    # 创建默认配置文件
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if not state_manager.config_path.exists():
        default_config = {
            "project_name": Path.cwd().name,
            "project_type": "python",
            "model": "MiniMax-M2.5-highspeed",
            "session_type": "coder",
            "test_command": "uv run pytest tests/ -v",
            "test_pattern": "test_*.py",
            "max_errors_before_intervention": 3,
            "context_window_limit": 100000,
            "active_provider": "default",
            "providers": {
                "default": {
                    "provider": "minimax",
                    "model": "MiniMax-M2.5-highspeed",
                    "api_key_env": "ANTHROPIC_AUTH_TOKEN",
                    "base_url_env": "ANTHROPIC_BASE_URL"
                }
            },
            "context_files": ["CLAUDE.md", "README.md"],
            "verify_command": "uv run pytest tests/ -x -q",
            "allowed_tools": [
                "Read", "Write", "Edit", "Bash", "Glob", "Grep",
                "WebSearch", "WebFetch", "AskUserQuestion",
                "TodoWrite", "ExitPlanMode", "EnterPlanMode"
            ],
            "mcp_servers": {},
            "retry": {
                "max_retries": 3,
                "retry_interval": 5,
                "retry_on_errors": ["connection_error", "timeout", "process_error"]
            },
            "documentation_urls": {}
        }
        state_manager.save_config(default_config)

    if not state_manager.feature_list_path.exists():
        default_features = {
            "features": [
                {
                    "id": "example-task",
                    "name": "Example Task",
                    "description": "Replace this with your first task",
                    "priority": 1,
                    "status": "pending",
                    "passes": False,
                    "created_at": now,
                    "updated_at": now
                }
            ]
        }
        state_manager.save_feature_list(default_features)

    if not state_manager.progress_path.exists():
        state_manager.save_progress("")

    if not state_manager.session_history_path.exists():
        state_manager.save_session_history({"sessions": [], "total_sessions": 0})

    if not state_manager.state_path.exists():
        state_manager.save_state(state_manager.load_state())

    # Scaffold prompt templates for user customization
    prompt_manager = PromptManager(str(state_manager.agent_dir))
    created_templates = prompt_manager.scaffold_templates()

    # 显示初始化信息
    print_init_info(str(state_manager.agent_dir), created_templates)


def run_agent(args: argparse.Namespace, max_restarts: int = 3) -> None:
    """运行Agent循环，支持自动重启和优雅关闭"""
    global _shutdown_requested
    _shutdown_requested = False

    # 注册信号处理器
    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    project_root = args.project_dir if args.project_dir else None

    # Create single StateManager instance outside the loop
    state_manager = StateManager(project_root)

    for restart_count in range(max_restarts + 1):
        # 检查是否需要优雅关闭
        if _shutdown_requested:
            print_warning("Shutdown requested, exiting gracefully...")
            break

        if restart_count > 0:
            print_header(f"RESTART {restart_count}/{max_restarts}", style="bold yellow")

        print_info("Starting agent...")

        agent = AgentCore(project_root)
        session_manager = SessionManager(agent.state_manager)

        # 显示会话统计
        stats = session_manager.get_session_stats()
        print(f"Total sessions: {stats['total_sessions']}")
        print(f"Completed sessions: {stats['completed_sessions']}")

        # 运行Agent循环
        iterations = getattr(args, 'iterations', None) or 10
        summary = agent.run_agent_loop(iterations, shutdown_flag=lambda: _shutdown_requested)

        # 检查是否需要重启
        state = state_manager.load_state()
        if state.get("needs_restart"):
            # 清除重启标记
            state["needs_restart"] = False
            state["restart_reason"] = None
            state_manager.save_state(state)

            if restart_count < max_restarts:
                print_warning("Code changed, restarting to apply updates...")
                continue
            else:
                print_error("Max restarts reached, exiting.")

        break

    print("\n")
    print_run_summary(summary['iterations'], summary['completed'], summary['errors'])


def list_tasks(args: argparse.Namespace) -> None:
    """列出所有任务"""
    state_manager = StateManager(args.project_dir if args.project_dir else None)
    task_selector = TaskSelector(state_manager)

    data = state_manager.load_feature_list()
    features = data.get("features", [])

    # Apply filter if specified
    filter_type = getattr(args, 'filter', 'all')
    if filter_type == "pending":
        features = [f for f in features if not f.get("passes")]
    elif filter_type == "completed":
        features = [f for f in features if f.get("passes")]

    # Check if tree view is requested
    if getattr(args, 'tree', False):
        print_task_tree(features, task_selector)
    else:
        print_task_table(
            features,
            task_selector.get_completed_count(),
            task_selector.get_pending_count()
        )


def print_task_tree(features: list[dict], task_selector: TaskSelector) -> None:
    """Print tasks in tree format with dependencies"""
    from .console import print_info

    # Build task map
    task_map = {f.get("id", ""): f for f in features}

    # Find root tasks (no dependencies or all dependencies are not in the task list)
    in_degree = {}
    dependents = {}  # task_id -> list of tasks that depend on it

    for f in features:
        task_id = f.get("id", "")
        deps = f.get("depends_on", [])
        if not isinstance(deps, list):
            deps = []
        in_degree[task_id] = len(deps)
        if task_id not in dependents:
            dependents[task_id] = []

    # Build dependents map
    for f in features:
        task_id = f.get("id", "")
        deps = f.get("depends_on", [])
        if not isinstance(deps, list):
            deps = []
        for dep_id in deps:
            if dep_id in dependents:
                dependents[dep_id].append(task_id)

    # Print tree recursively
    def print_tree(task_id: str, prefix: str = "", is_last: bool = True):
        task = task_map.get(task_id)
        if not task:
            return

        # Determine status
        status = task.get("status", "pending")
        passes = task.get("passes", False)

        if status == "completed" or passes:
            status_str = "\033[92m✓\033[0m"
        elif status == "failed":
            status_str = "\033[91m✗\033[0m"
        elif status == "in_progress":
            status_str = "\033[93m⋯\033[0m"
        else:
            # Check if blocked
            if not task_selector.is_dependency_satisfied(task_id):
                status_str = "\033[90m⊘\033[0m"  # Blocked - gray
            else:
                status_str = "○"

        # Get dependencies
        deps = task.get("depends_on", [])
        if not isinstance(deps, list):
            deps = []
        dep_info = f" (depends on: {', '.join(deps)})" if deps else ""

        print(f"{prefix}└─ {status_str} {task.get('id', '')}: {task.get('name', '')}{dep_info}")

        # Print dependents
        children = dependents.get(task_id, [])
        for i, child_id in enumerate(children):
            child_prefix = prefix + ("    " if is_last else "│   ")
            print_tree(child_id, child_prefix, i == len(children) - 1)

    # Find root tasks (no incoming edges)
    roots = [tid for tid, degree in in_degree.items() if degree == 0]

    # Also include tasks with external dependencies
    all_task_ids = set(task_map.keys())
    for f in features:
        deps = f.get("depends_on", [])
        if not isinstance(deps, list):
            deps = []
        for dep_id in deps:
            if dep_id not in all_task_ids and f.get("id") not in roots:
                roots.append(f.get("id"))

    # Remove duplicates
    roots = list(set(roots))

    if not roots:
        roots = list(task_map.keys())

    # Print each root
    for i, task_id in enumerate(sorted(roots)):
        is_last = (i == len(roots) - 1)
        print_tree(task_id, "", is_last)


def add_feature(args: argparse.Namespace) -> None:
    """添加新功能"""
    state_manager = StateManager(args.project_dir if args.project_dir else None)

    feature = {
        "id": args.id or f"feature-{len(state_manager.load_feature_list().get('features', [])) + 1:03d}",
        "name": args.name,
        "description": args.description or "",
        "priority": args.priority or 99,
        "status": "pending",
        "passes": False,
        "created_at": datetime.now().strftime("%Y-%m-%d"),
        "updated_at": datetime.now().strftime("%Y-%m-%d")
    }

    # Add depends_on if provided
    if args.depends_on:
        feature["depends_on"] = args.depends_on

    state_manager.add_feature(feature)
    print(f"Added feature: {feature['id']} - {feature['name']}")
    if args.depends_on:
        print(f"  Depends on: {', '.join(args.depends_on)}")


def show_status(args: argparse.Namespace) -> None:
    """显示状态"""
    state_manager = StateManager(args.project_dir if args.project_dir else None)
    git_helper = GitHelper(args.project_dir if args.project_dir else None)

    # 配置信息
    config = state_manager.load_config()

    # Git状态
    branch = git_helper.get_current_branch()
    has_changes = git_helper.has_changes()

    # 任务统计
    task_selector = TaskSelector(state_manager)
    tasks_completed = task_selector.get_completed_count()
    tasks_total = task_selector.get_total_count()
    tasks_pending = task_selector.get_pending_count()

    # 当前状态
    state = state_manager.load_state()
    current_session = state.get('current_session', {}).get('id', 'N/A')
    error_count = state.get('error_count', 0)

    print_status_panel(
        project_name=config.get('project_name', 'N/A'),
        project_type=config.get('project_type', 'N/A'),
        test_command=config.get('test_command', 'N/A'),
        branch=branch,
        has_changes=has_changes,
        tasks_completed=tasks_completed,
        tasks_total=tasks_total,
        tasks_pending=tasks_pending,
        current_session=current_session,
        error_count=error_count
    )


def reload_config(args: argparse.Namespace) -> None:
    """重载配置文件"""
    state_manager = StateManager(args.project_dir if args.project_dir else None)
    reloader = ConfigReloader(args.project_dir if args.project_dir else None)

    print_info(f"Reloading configuration from: {reloader.agent_dir}")

    # 执行重载
    force = getattr(args, 'force', False)
    result = reloader.reload(force=force)

    # 显示结果
    print_reload_result(
        success=result["success"],
        message=result["message"],
        reloaded=result.get("reloaded", []),
        errors=result.get("errors", []),
        timestamp=result.get("timestamp", "N/A")
    )


def config_get(args: argparse.Namespace) -> None:
    """Get a configuration value"""
    from agent.config_model import ConfigLoader
    from pydantic import ValidationError

    agent_dir = args.project_dir if args.project_dir else None

    try:
        loader = ConfigLoader(agent_dir)
        config = loader.load()

        # Navigate to the key
        key = args.key
        keys = key.split(".")

        value = config.model_dump()
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                print_error(f"Key not found: {key}")
                return

        # Print the value
        import json
        if isinstance(value, (dict, list)):
            print(json.dumps(value, indent=2))
        else:
            print(value)

    except ValidationError as e:
        print_error(f"Configuration validation error: {e}")
    except Exception as e:
        print_error(f"Failed to get config: {e}")


def config_set(args: argparse.Namespace) -> None:
    """Set a configuration value"""
    from agent.config_model import ConfigLoader
    from agent.logging_ import log_audit
    from pydantic import ValidationError
    import json

    agent_dir = args.project_dir if args.project_dir else None
    key = args.key
    value_str = args.value

    try:
        loader = ConfigLoader(agent_dir)
        config = loader.load()

        # Try to parse value as JSON first
        try:
            value = json.loads(value_str)
        except json.JSONDecodeError:
            # Use as string
            value = value_str

        # Convert value to appropriate type based on existing key type
        keys = key.split(".")
        config_dict = config.model_dump()

        # Navigate to the parent dict
        current = config_dict
        for k in keys[:-1]:
            if k not in current:
                current[k] = {}
            current = current[k]

        # Try to maintain type consistency
        last_key = keys[-1]
        if last_key in current:
            existing_type = type(current[last_key])
            if existing_type == int and isinstance(value, float):
                value = int(value)
            elif existing_type == bool and isinstance(value, str):
                value = value.lower() in ("true", "1", "yes")
            elif existing_type == list and not isinstance(value, list):
                value = [value]

        current[last_key] = value

        # Re-create config to validate
        from agent.config_model import ProjectConfig
        config = ProjectConfig(**config_dict)

        # Save
        loader.save(config)

        print_success(f"Set {key} = {args.value}")

        # Audit log
        log_audit(
            action="update",
            entity_type="config",
            entity_id=key,
            details={"value": str(value)[:100]},  # Truncate for log
        )

    except ValidationError as e:
        print_error(f"Configuration validation error: {e}")
    except Exception as e:
        print_error(f"Failed to set config: {e}")


def config_validate(args: argparse.Namespace) -> None:
    """Validate configuration"""
    from agent.config_model import ConfigLoader
    from pydantic import ValidationError

    agent_dir = args.project_dir if args.project_dir else None

    try:
        loader = ConfigLoader(agent_dir)
        config = loader.load()

        print_success("Configuration is valid!")
        print(f"\nSchema version: {config.schema_version}")
        print(f"Model: {config.model}")
        print(f"Context window: {config.context_window_limit}")

    except ValidationError as e:
        print_error("Configuration validation failed:")
        for error in e.errors():
            print_error(f"  - {error['loc']}: {error['msg']}")
    except Exception as e:
        print_error(f"Configuration error: {e}")


def config_export(args: argparse.Namespace) -> None:
    """Export configuration"""
    from agent.config_model import export_config
    import json

    agent_dir = args.project_dir if args.project_dir else None

    try:
        config_dict = export_config(agent_dir, include_sensitive=args.include_sensitive)

        output = json.dumps(config_dict, indent=2)

        if args.output:
            with open(args.output, "w") as f:
                f.write(output)
            print_success(f"Configuration exported to {args.output}")
        else:
            print(output)

    except Exception as e:
        print_error(f"Failed to export config: {e}")


def config_import(args: argparse.Namespace) -> None:
    """Import configuration"""
    from agent.config_model import ConfigLoader, import_config, ProjectConfig
    from agent.logging_ import log_audit
    import json

    agent_dir = args.project_dir if args.project_dir else None

    try:
        # Load the file
        with open(args.file, "r") as f:
            config_dict = json.load(f)

        # Validate only mode
        if args.validate_only:
            config = import_config(config_dict, agent_dir)
            print_success("Configuration is valid!")
            return

        # Full import
        loader = ConfigLoader(agent_dir)
        config = import_config(config_dict, agent_dir)
        loader.save(config)

        print_success(f"Configuration imported from {args.file}")

        # Audit log
        log_audit(
            action="import",
            entity_type="config",
            entity_id="config.json",
            details={"source_file": args.file},
        )

    except json.JSONDecodeError as e:
        print_error(f"Invalid JSON in file: {e}")
    except Exception as e:
        print_error(f"Failed to import config: {e}")


def start_server(args: argparse.Namespace) -> None:
    """Start the REST API server"""
    import uvicorn

    browser_host = "localhost" if args.host in {"0.0.0.0", "::"} else args.host

    print(f"Starting Agent-Loop API server...")
    print(f"Host: {args.host}")
    print(f"Port: {args.port}")
    print(f"Dashboard: http://{browser_host}:{args.port}/")
    print(f"API docs: http://{browser_host}:{args.port}/docs")

    uvicorn.run(
        "api:app",
        host=args.host,
        port=args.port,
        reload=False
    )


def list_prompts(args: argparse.Namespace) -> None:
    """列出所有提示词"""
    prompt_manager = PromptManager(args.project_dir if args.project_dir else None)

    prompts = prompt_manager.list_prompts()

    print_prompt_list(prompts)


def show_prompt(args: argparse.Namespace) -> None:
    """显示指定提示词"""
    prompt_manager = PromptManager(args.project_dir if args.project_dir else None)

    if args.key:
        prompt = prompt_manager.get_prompt(args.key)
        if prompt:
            print(f"\nPrompt: {prompt['name']}")
            print(f"Key: {args.key}")
            print(f"Description: {prompt['description']}")
            print(f"Created: {prompt.get('created_at', 'N/A')}")
            print(f"Updated: {prompt.get('updated_at', 'N/A')}")
            print("\n" + "=" * 60)
            print("System Prompt:")
            print("=" * 60)
            print(prompt["system"])
            print("=" * 60)
        else:
            print(f"Prompt '{args.key}' not found.")
    else:
        # Show active prompt
        system_prompt = prompt_manager.get_active_prompt()
        active_name = prompt_manager.get_active_prompt_name()
        print(f"\nActive Prompt: {active_name}")
        print("=" * 60)
        print(system_prompt)
        print("=" * 60)


def set_prompt(args: argparse.Namespace) -> None:
    """设置活动提示词"""
    prompt_manager = PromptManager(args.project_dir if args.project_dir else None)

    if prompt_manager.set_active_prompt(args.key):
        print(f"Active prompt set to: {args.key}")
    else:
        print(f"Error: Prompt '{args.key}' not found.")


def add_prompt(args: argparse.Namespace) -> None:
    """添加新提示词"""
    prompt_manager = PromptManager(args.project_dir if args.project_dir else None)

    # If --system is not provided, use the system template as default
    system_prompt = args.system
    if not system_prompt:
        system_prompt = prompt_manager.load_template("system")

    if prompt_manager.add_prompt(args.key, args.name, args.description or "", system_prompt):
        print(f"Added prompt: {args.key} - {args.name}")
    else:
        print(f"Error: Prompt '{args.key}' already exists. Use 'prompt edit' to modify it.")


def delete_prompt(args: argparse.Namespace) -> None:
    """删除提示词"""
    prompt_manager = PromptManager(args.project_dir if args.project_dir else None)

    if prompt_manager.delete_prompt(args.key):
        print(f"Deleted prompt: {args.key}")
    else:
        print(f"Error: Could not delete prompt '{args.key}'. It may be the last prompt or not exist.")


def list_templates(args: argparse.Namespace) -> None:
    """列出所有提示词模板"""
    prompt_manager = PromptManager(args.project_dir if args.project_dir else None)

    templates = prompt_manager.list_templates()

    console.print("\n[bold magenta]Available Templates:[/bold magenta]")
    print_template_list(templates)


def show_template(args: argparse.Namespace) -> None:
    """显示指定模板内容"""
    prompt_manager = PromptManager(args.project_dir if args.project_dir else None)

    try:
        content = prompt_manager.load_template(args.name)
        print(f"\nTemplate: {args.name}")
        print("=" * 60)
        print(content)
        print("=" * 60)
    except ValueError as e:
        print(f"Error: {e}")


def scaffold_templates(args: argparse.Namespace) -> None:
    """生成所有默认模板文件"""
    prompt_manager = PromptManager(args.project_dir if args.project_dir else None)

    created = prompt_manager.scaffold_templates()

    if created:
        print(f"\nCreated {len(created)} template files in .agent/prompt_templates/:")
        for name in created:
            print(f"  - {name}")
        print("\nEdit these files to customize prompts for your project.")
    else:
        print("\nAll template files already exist. No new files created.")
        print("To reset a template to default, use: uv run python main.py template reset <name>")


def reset_template(args: argparse.Namespace) -> None:
    """重置模板为内置默认值"""
    prompt_manager = PromptManager(args.project_dir if args.project_dir else None)

    if prompt_manager.reset_template(args.name):
        print(f"Reset template '{args.name}' to built-in default.")
    else:
        print(f"No override found for template '{args.name}'.")


# ========== Provider Command Handlers ==========

def list_providers(args: argparse.Namespace) -> None:
    """List all configured providers and their status"""
    state_manager = StateManager(args.project_dir if args.project_dir else None)
    config = state_manager.load_config()
    provider_manager = create_provider_manager(config)

    providers = provider_manager.list_providers()
    active = provider_manager.get_active_provider()

    if not providers:
        print("No providers configured.")
        return

    print("\n=== Configured Providers ===\n")
    print(f"{'Name':<20} {'Type':<12} {'Model':<25} {'Health':<12} {'Status':<10}")
    print("-" * 80)

    for name, provider in providers.items():
        health = provider_manager.get_health_status(name)
        status = "active" if active and active.config == provider else "inactive"

        # Get masked API key info
        keys = provider.get_all_api_keys()
        key_info = f"{len(keys)} key(s)" if keys else "no key"

        print(f"{name:<20} {provider.provider:<12} {provider.get_model():<25} {health.value:<12} {status:<10}")

    print("\n=== Provider Statistics ===\n")
    all_stats = provider_manager.get_all_stats()
    if all_stats:
        print(f"{'Provider':<20} {'Calls':<10} {'Success':<10} {'Success Rate':<15} {'Avg Response Time':<15}")
        print("-" * 70)
        for name, stats in all_stats.items():
            print(f"{name:<20} {stats.total_calls:<10} {stats.successful_calls:<10} "
                  f"{stats.success_rate:.2%}            {stats.average_response_time:.3f}s")
    else:
        print("No statistics available yet.")

    print("\n=== Fallback Chains ===\n")
    for name, provider in providers.items():
        if provider.fallback_provider:
            print(f"  {name} -> {provider.fallback_provider}")
        else:
            print(f"  {name} -> (no fallback)")

    print()


def switch_provider_cmd(args: argparse.Namespace) -> None:
    """Switch to a different provider"""
    state_manager = StateManager(args.project_dir if args.project_dir else None)
    config = state_manager.load_config()
    provider_manager = create_provider_manager(config)

    # Get the provider to switch to
    provider_name = args.name

    # Check if provider exists
    providers = provider_manager.list_providers()
    if provider_name not in providers:
        print(f"Error: Provider '{provider_name}' not found.")
        print("\nAvailable providers:")
        for name in providers:
            print(f"  - {name}")
        return

    # Validate and switch
    warnings = provider_manager.validate_providers()
    if provider_name in warnings:
        print(f"Warning: Provider '{provider_name}' has validation issues:")
        for warning in warnings[provider_name]:
            print(f"  - {warning}")

    success = provider_manager.switch_provider(provider_name)
    if success:
        # Update config to persist the change
        config["active_provider"] = provider_name
        state_manager.save_config(config)

        print(f"Switched to provider '{provider_name}'.")
    else:
        print(f"Failed to switch to provider '{provider_name}'.")


async def check_provider_health(args: argparse.Namespace) -> None:
    """Check provider health status"""
    state_manager = StateManager(args.project_dir if args.project_dir else None)
    config = state_manager.load_config()
    provider_manager = create_provider_manager(config)

    providers = provider_manager.list_providers()

    if not providers:
        print("No providers configured.")
        return

    # Check specific provider or all
    if args.name:
        providers_to_check = {args.name: providers[args.name]} if args.name in providers else {}
        if not providers_to_check:
            print(f"Error: Provider '{args.name}' not found.")
            return
    else:
        providers_to_check = providers

    print("\n=== Provider Health Check ===\n")

    for name in providers_to_check:
        print(f"Checking {name}...", end=" ")
        is_healthy = await provider_manager.provider_health_check(name)
        health = provider_manager.get_health_status(name)
        status = "✓ Healthy" if is_healthy else "✗ Unhealthy"
        print(status)

    print()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Agent-Loop: Autonomous AI Agent System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s init                 Initialize a new project
  %(prog)s run                  Run agent with default settings (10 iterations)
  %(prog)s run --iterations 3   Run agent for 3 iterations
  %(prog)s run --max-restarts 5 --iterations 20  Run with more restarts
  %(prog)s list                 List all tasks/features
  %(prog)s add --name "Add feature" --priority 1  Add a new task
  %(prog)s status               Show current agent status
  %(prog)s --version            Show version information

For more information, see: https://github.com/oGYCo/Agent-Loop
"""
    )

    parser.add_argument(
        "--project-dir",
        type=str,
        help="Project directory (default: current directory)"
    )

    parser.add_argument(
        "--version",
        action="store_true",
        help="Show version information"
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # init command
    init_parser = subparsers.add_parser(
        "init",
        help="Initialize the project",
        description="Create initial configuration files and git repository"
    )
    init_parser.add_argument(
        "--force",
        action="store_true",
        help="Force reinitialize if already initialized"
    )

    # run command
    run_parser = subparsers.add_parser(
        "run",
        help="Run the agent",
        description="Start the autonomous agent loop to execute tasks"
    )
    run_parser.add_argument(
        "--iterations",
        type=int,
        default=10,
        help="Maximum iterations (default: 10)"
    )
    run_parser.add_argument(
        "--max-restarts",
        type=int,
        default=3,
        help="Maximum restarts on code changes (default: 3)"
    )

    # list command
    list_parser = subparsers.add_parser(
        "list",
        help="List all tasks",
        description="Show all features/tasks from feature_list.json"
    )
    list_parser.add_argument(
        "--filter",
        type=str,
        choices=["all", "pending", "completed"],
        default="all",
        help="Filter tasks by status (default: all)"
    )
    list_parser.add_argument(
        "--tree",
        action="store_true",
        help="Show tasks in tree format with dependencies"
    )

    # add command
    add_parser = subparsers.add_parser(
        "add",
        help="Add a new task",
        description="Add a new feature/task to feature_list.json"
    )
    add_parser.add_argument(
        "--id",
        type=str,
        help="Feature ID (auto-generated if not provided)"
    )
    add_parser.add_argument(
        "--name",
        type=str,
        required=True,
        help="Feature name (required)"
    )
    add_parser.add_argument(
        "--description",
        type=str,
        help="Feature description"
    )
    add_parser.add_argument(
        "--priority",
        type=int,
        help="Priority (lower number = higher priority, default: 99)"
    )
    add_parser.add_argument(
        "--depends-on",
        type=str,
        nargs="*",
        help="Task IDs this task depends on (space-separated)"
    )

    # status command
    status_parser = subparsers.add_parser(
        "status",
        help="Show agent status",
        description="Display current project and agent state"
    )
    status_parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show verbose output"
    )

    # reload command
    reload_parser = subparsers.add_parser(
        "reload",
        help="Reload configuration files",
        description="Reload config.json and feature_list.json without restarting the agent"
    )
    reload_parser.add_argument(
        "--force",
        action="store_true",
        help="Force reload even if files haven't changed"
    )

    # server command
    server_parser = subparsers.add_parser(
        "server",
        help="Start REST API server",
        description="Start FastAPI REST API server"
    )
    server_parser.add_argument(
        "--host",
        type=str,
        default="0.0.0.0",
        help="Host to bind to (default: 0.0.0.0)"
    )
    server_parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to bind to (default: 8000)"
    )

    # prompt command
    prompt_parser = subparsers.add_parser(
        "prompt",
        help="Manage prompts",
        description="Manage system prompts for different task types"
    )
    prompt_subparsers = prompt_parser.add_subparsers(dest="prompt_action", help="Prompt actions")

    # prompt list
    prompt_list_parser = prompt_subparsers.add_parser(
        "list",
        help="List all prompts"
    )

    # prompt show
    prompt_show_parser = prompt_subparsers.add_parser(
        "show",
        help="Show prompt content"
    )
    prompt_show_parser.add_argument(
        "key",
        nargs="?",
        help="Prompt key to show (default: show active prompt)"
    )

    # prompt set
    prompt_set_parser = prompt_subparsers.add_parser(
        "set",
        help="Set active prompt"
    )
    prompt_set_parser.add_argument(
        "key",
        help="Prompt key to activate"
    )

    # prompt add
    prompt_add_parser = prompt_subparsers.add_parser(
        "add",
        help="Add a new prompt"
    )
    prompt_add_parser.add_argument(
        "key",
        help="Unique key for the prompt"
    )
    prompt_add_parser.add_argument(
        "name",
        help="Display name for the prompt"
    )
    prompt_add_parser.add_argument(
        "--description",
        "-d",
        default="",
        help="Description of the prompt"
    )
    prompt_add_parser.add_argument(
        "--system",
        "-s",
        default="",
        help="System prompt content"
    )

    # prompt delete
    prompt_delete_parser = prompt_subparsers.add_parser(
        "delete",
        help="Delete a prompt"
    )
    prompt_delete_parser.add_argument(
        "key",
        help="Prompt key to delete"
    )

    # provider command
    provider_parser = subparsers.add_parser(
        "provider",
        help="Manage model providers",
        description="Manage model providers for failover and load balancing"
    )
    provider_subparsers = provider_parser.add_subparsers(dest="provider_action", help="Provider actions")

    # provider list
    provider_subparsers.add_parser(
        "list",
        help="List all configured providers and their status"
    )

    # provider switch
    provider_switch_parser = provider_subparsers.add_parser(
        "switch",
        help="Switch to a different provider"
    )
    provider_switch_parser.add_argument(
        "name",
        help="Provider name to switch to"
    )

    # provider health
    provider_health_parser = provider_subparsers.add_parser(
        "health",
        help="Check provider health status"
    )
    provider_health_parser.add_argument(
        "name",
        nargs="?",  # Optional - if not provided, check all providers
        help="Provider name to check (optional, checks all if not provided)"
    )

    # template command
    template_parser = subparsers.add_parser(
        "template",
        help="Manage prompt templates",
        description="Manage prompt templates for customizing agent behavior"
    )
    template_subparsers = template_parser.add_subparsers(dest="template_action", help="Template actions")

    # template list
    template_subparsers.add_parser(
        "list",
        help="List all available templates"
    )

    # template show
    template_show_parser = template_subparsers.add_parser(
        "show",
        help="Show template content"
    )
    template_show_parser.add_argument(
        "name",
        help="Template name (e.g., system, task, self_review)"
    )

    # template scaffold
    template_subparsers.add_parser(
        "scaffold",
        help="Create all default template files for editing"
    )

    # template reset
    template_reset_parser = template_subparsers.add_parser(
        "reset",
        help="Reset a template to built-in default"
    )
    template_reset_parser.add_argument(
        "name",
        help="Template name to reset"
    )

    # config command
    config_parser = subparsers.add_parser(
        "config",
        help="Manage configuration",
        description="View, set, validate, export, and import configuration"
    )
    config_subparsers = config_parser.add_subparsers(dest="config_action", help="Config actions")

    # config get
    config_get_parser = config_subparsers.add_parser(
        "get",
        help="Get a configuration value"
    )
    config_get_parser.add_argument(
        "key",
        help="Configuration key (e.g., project_name, model, providers.default.model)"
    )

    # config set
    config_set_parser = config_subparsers.add_parser(
        "set",
        help="Set a configuration value"
    )
    config_set_parser.add_argument(
        "key",
        help="Configuration key (e.g., project_name, model)"
    )
    config_set_parser.add_argument(
        "value",
        help="Configuration value"
    )

    # config validate
    config_subparsers.add_parser(
        "validate",
        help="Validate configuration"
    )

    # config export
    config_export_parser = config_subparsers.add_parser(
        "export",
        help="Export configuration"
    )
    config_export_parser.add_argument(
        "--include-sensitive",
        action="store_true",
        help="Include sensitive data (API keys, passwords)"
    )
    config_export_parser.add_argument(
        "--output", "-o",
        type=str,
        help="Output file (default: stdout)"
    )

    # config import
    config_import_parser = config_subparsers.add_parser(
        "import",
        help="Import configuration"
    )
    config_import_parser.add_argument(
        "file",
        type=str,
        help="Configuration file to import"
    )
    config_import_parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Only validate without importing"
    )

    # Backwards compatibility: --init and --run flags
    parser.add_argument("--init", action="store_true", help="Initialize the project (deprecated, use 'init' subcommand)")
    parser.add_argument("--run", action="store_true", help="Run the agent (deprecated, use 'run' subcommand)")

    args = parser.parse_args()

    # Handle version flag
    if args.version:
        print(f"Agent-Loop CLI {__version__}")
        return

    # 处理兼容性格式
    if args.init:
        init_project(args)
    elif args.run:
        run_agent(args, max_restarts=3)
    elif args.command:
        # 执行子命令
        if args.command == "init":
            init_project(args)
        elif args.command == "run":
            max_restarts = getattr(args, 'max_restarts', 3)
            run_agent(args, max_restarts=max_restarts)
        elif args.command == "list":
            list_tasks(args)
        elif args.command == "add":
            add_feature(args)
        elif args.command == "status":
            show_status(args)
        elif args.command == "reload":
            reload_config(args)
        elif args.command == "server":
            start_server(args)
        elif args.command == "prompt":
            if args.prompt_action == "list":
                list_prompts(args)
            elif args.prompt_action == "show":
                show_prompt(args)
            elif args.prompt_action == "set":
                set_prompt(args)
            elif args.prompt_action == "add":
                add_prompt(args)
            elif args.prompt_action == "delete":
                delete_prompt(args)
            else:
                prompt_parser.print_help()
        elif args.command == "provider":
            import asyncio
            if args.provider_action == "list":
                list_providers(args)
            elif args.provider_action == "switch":
                switch_provider_cmd(args)
            elif args.provider_action == "health":
                asyncio.run(check_provider_health(args))
            else:
                provider_parser.print_help()
        elif args.command == "config":
            if args.config_action == "get":
                config_get(args)
            elif args.config_action == "set":
                config_set(args)
            elif args.config_action == "validate":
                config_validate(args)
            elif args.config_action == "export":
                config_export(args)
            elif args.config_action == "import":
                config_import(args)
            else:
                config_parser.print_help()
        elif args.command == "template":
            if args.template_action == "list":
                list_templates(args)
            elif args.template_action == "show":
                show_template(args)
            elif args.template_action == "scaffold":
                scaffold_templates(args)
            elif args.template_action == "reset":
                reset_template(args)
            else:
                template_parser.print_help()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
