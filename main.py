"""Main Entry Point - CLI for Agent-Loop

A long-running autonomous AI agent system with session management,
task execution, and human intervention capabilities.
"""

import argparse
import sys
import signal
from pathlib import Path
from typing import Any, Dict

# 添加当前目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from agent.state_manager import StateManager
from agent.task_selector import TaskSelector
from agent.agent_core import AgentCore
from agent.session_manager import SessionManager
from agent.git_helper import GitHelper

# 全局 shutdown 标志
_shutdown_requested = False

# CLI version
__version__ = "1.0.0"


def _signal_handler(signum: int, frame: Any) -> None:
    """处理 SIGINT/SIGTERM 信号，实现优雅关闭"""
    global _shutdown_requested
    sig_name = signal.Signals(signum).name
    print(f"\n⚠️  Received {sig_name}, initiating graceful shutdown...")
    print("   Finishing current task before exit...")
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

    # 显示初始化信息
    print(f"Project directory: {state_manager.agent_dir}")
    print("Configuration files created:")
    print("  - config.json")
    print("  - feature_list.json")
    print("  - progress.txt")
    print("  - session_history.json")
    print("  - state.json")

    print("\nProject initialized successfully!")
    print("\nTo add features, edit .agent/feature_list.json")
    print("To run the agent, use: python main.py --run")


def run_agent(args: argparse.Namespace, max_restarts: int = 3) -> None:
    """运行Agent循环，支持自动重启和优雅关闭"""
    global _shutdown_requested
    _shutdown_requested = False

    # 注册信号处理器
    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    project_root = args.project_dir if args.project_dir else None

    for restart_count in range(max_restarts + 1):
        # 检查是否需要优雅关闭
        if _shutdown_requested:
            print("\n🛑 Shutdown requested, exiting gracefully...")
            break
        # 检查是否需要重启
        state_manager = StateManager(project_root)
        state = state_manager.load_state()

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
        "created_at": "2026-03-07",
        "updated_at": "2026-03-07"
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

For more information, see: https://github.com/agent-loop/docs
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
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
