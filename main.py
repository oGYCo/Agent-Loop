"""Main Entry Point - CLI for Agent-Loop

A long-running autonomous AI agent system with session management,
task execution, and human intervention capabilities.
"""

import argparse
import logging
import os
import sys
import signal
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

# 添加当前目录到路径
sys.path.insert(0, str(Path(__file__).parent))

# Configure logging
def _configure_logging() -> None:
    """Configure logging for the application."""
    # Get log level from environment variable (default: INFO)
    log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
    log_level_num = getattr(logging, log_level, logging.INFO)

    # Get log file path from environment variable (optional)
    log_file = os.environ.get("LOG_FILE", "")

    # Create formatter
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level_num)

    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level_num)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # File handler (if LOG_FILE is set)
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(log_level_num)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

# Initialize logging
_configure_logging()

from agent.state_manager import StateManager
from agent.task_selector import TaskSelector
from agent.agent_core import AgentCore
from agent.session_manager import SessionManager
from agent.git_helper import GitHelper
from agent.config_reloader import ConfigReloader
from agent.prompt_manager import PromptManager

# 全局 shutdown 标志
_shutdown_requested = False

# CLI version
__version__ = "1.0.0"


def _signal_handler(signum: int, frame: Any) -> None:
    """处理 SIGINT/SIGTERM 信号，实现优雅关闭"""
    global _shutdown_requested
    if _shutdown_requested:
        print("\n🛑 Force exit!")
        sys.exit(1)
    sig_name = signal.Signals(signum).name
    print(f"\n⚠️  Received {sig_name}, initiating graceful shutdown...")
    print("   Finishing current task before exit... (press Ctrl+C again to force quit)")
    _shutdown_requested = True


def init_project(args: argparse.Namespace) -> None:
    """初始化项目"""
    print("Initializing Agent-Loop project...")

    state_manager = StateManager(args.project_dir if args.project_dir else None)
    git_helper = GitHelper(args.project_dir if args.project_dir else None)

    # 初始化git仓库
    if not git_helper.is_git_repo():
        print("Initializing git repository...")
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
            "test_command": "pytest tests/ -v",
            "test_pattern": "test_*.py",
            "max_errors_before_intervention": 3,
            "context_window_limit": 100000,
            "context_files": ["CLAUDE.md", "README.md"],
            "verify_command": "pytest tests/ -x -q",
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
    print(f"Project directory: {state_manager.agent_dir}")
    print("Configuration files created:")
    print("  - config.json")
    print("  - feature_list.json")
    print("  - progress.txt")
    print("  - session_history.json")
    print("  - state.json")
    if created_templates:
        print(f"  - prompt_templates/ ({len(created_templates)} templates)")
        for t in created_templates:
            print(f"      - {t}")

    print("\nProject initialized successfully!")
    print("\nTo add features, edit .agent/feature_list.json")
    print("To customize prompts, edit files in .agent/prompt_templates/")
    print("To run the agent, use: python main.py run")


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
            print("\n🛑 Shutdown requested, exiting gracefully...")
            break

        if restart_count > 0:
            print(f"\n{'='*50}")
            print(f"RESTART {restart_count}/{max_restarts}")
            print(f"{'='*50}")

        print("Starting agent...")

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
                print(f"\n{'='*50}")
                print("Code changed, restarting to apply updates...")
                print(f"{'='*50}\n")
                continue
            else:
                print("\nMax restarts reached, exiting.")

        break

    print("\n" + "=" * 50)
    print("Agent Run Summary")
    print("=" * 50)
    print(f"Iterations: {summary['iterations']}")
    print(f"Tasks completed: {summary['completed']}")
    print(f"Errors: {summary['errors']}")
    print("=" * 50)


def list_tasks(args: argparse.Namespace) -> None:
    """列出所有任务"""
    state_manager = StateManager(args.project_dir if args.project_dir else None)
    task_selector = TaskSelector(state_manager)

    data = state_manager.load_feature_list()
    features = data.get("features", [])

    print("\nFeature List:")
    print("-" * 60)

    for f in features:
        status_icon = "✓" if f.get("passes") else "○"
        print(f"{status_icon} [{f.get('id')}] {f.get('name')}")
        print(f"   Priority: {f.get('priority')}, Status: {f.get('status')}")
        print(f"   {f.get('description')}")
        print()

    print("-" * 60)
    print(f"Total: {len(features)} | Completed: {task_selector.get_completed_count()} | Pending: {task_selector.get_pending_count()}")


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

    state_manager.add_feature(feature)
    print(f"Added feature: {feature['id']} - {feature['name']}")


def show_status(args: argparse.Namespace) -> None:
    """显示状态"""
    state_manager = StateManager(args.project_dir if args.project_dir else None)
    git_helper = GitHelper(args.project_dir if args.project_dir else None)

    print("\nAgent Status")
    print("=" * 50)

    # 配置信息
    config = state_manager.load_config()
    print(f"Project: {config.get('project_name', 'N/A')}")
    print(f"Type: {config.get('project_type', 'N/A')}")
    print(f"Test command: {config.get('test_command', 'N/A')}")

    # Git状态
    print(f"\nGit Branch: {git_helper.get_current_branch()}")
    print(f"Has changes: {git_helper.has_changes()}")

    # 任务统计
    task_selector = TaskSelector(state_manager)
    print(f"\nTasks: {task_selector.get_completed_count()}/{task_selector.get_total_count()} completed")
    print(f"Pending: {task_selector.get_pending_count()}")

    # 当前状态
    state = state_manager.load_state()
    print(f"\nCurrent session: {state.get('current_session', {}).get('id', 'N/A')}")
    print(f"Error count: {state.get('error_count', 0)}")

    print("=" * 50)


def reload_config(args: argparse.Namespace) -> None:
    """重载配置文件"""
    state_manager = StateManager(args.project_dir if args.project_dir else None)
    reloader = ConfigReloader(args.project_dir if args.project_dir else None)

    print("\nReloading configuration...")
    print(f"Config path: {reloader.agent_dir}")

    # 执行重载
    force = getattr(args, 'force', False)
    result = reloader.reload(force=force)

    # 显示结果
    print("\nReload Result:")
    print("-" * 40)
    if result["success"]:
        print(f"✓ Success: {result['message']}")
    else:
        print(f"✗ Failed: {result['message']}")

    if result.get("reloaded"):
        print(f"  Reloaded files: {', '.join(result['reloaded'])}")

    if result.get("errors"):
        print("  Errors:")
        for error in result["errors"]:
            print(f"    - {error}")

    print(f"  Timestamp: {result.get('timestamp', 'N/A')}")
    print("-" * 40)


def start_server(args: argparse.Namespace) -> None:
    """Start the REST API server"""
    import uvicorn

    print(f"Starting Agent-Loop API server...")
    print(f"Host: {args.host}")
    print(f"Port: {args.port}")
    print(f"API docs: http://{args.host}:{args.port}/docs")

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

    print("\nAvailable Prompts:")
    print("-" * 60)

    for p in prompts:
        active_mark = " [ACTIVE]" if p["is_active"] else ""
        print(f"[{p['key']}] {p['name']}{active_mark}")
        print(f"   {p['description']}")
        print()

    print("-" * 60)


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

    print("\nAvailable Templates:")
    print("-" * 60)

    for t in templates:
        override_mark = " [OVERRIDE]" if t["has_override"] else ""
        builtin_mark = " (built-in)" if t["builtin"] else " (custom)"
        print(f"  {t['name']}{override_mark}{builtin_mark}")
        if t["path"]:
            print(f"    Path: {t['path']}")

    print("-" * 60)
    print("\nTo customize a template, edit: .agent/prompt_templates/<name>.md")
    print("To scaffold all templates: python main.py template scaffold")


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
        print("To reset a template to default, use: python main.py template reset <name>")


def reset_template(args: argparse.Namespace) -> None:
    """重置模板为内置默认值"""
    prompt_manager = PromptManager(args.project_dir if args.project_dir else None)

    if prompt_manager.reset_template(args.name):
        print(f"Reset template '{args.name}' to built-in default.")
    else:
        print(f"No override found for template '{args.name}'.")


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
