"""Agent Core - 核心Agent逻辑模块 (使用 Claude Agent SDK)

基于 Anthropic Claude Agent SDK 的实现
"""

import os
import asyncio
import json
import sys
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, cast, Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from .webhook import WebhookNotifier
    from .slack_notifier import SlackNotifier

from .constants import EventTypes
from .console import agent_output
from .metrics import get_metrics_collector
from .model_provider import ModelProviderManager, create_provider_manager
from .exceptions import (
    AgentLoopError,
    WebhookError,
    SlackError,
    TaskExecutionError,
    TaskTimeoutError,
    ProviderError,
)

from claude_agent_sdk import (
    query,
    ClaudeSDKClient,
    ClaudeAgentOptions,
    AgentDefinition,
    HookMatcher,
    ClaudeSDKError,
    CLINotFoundError,
    CLIConnectionError,
    ProcessError,
)
from claude_agent_sdk.types import (
    StreamEvent,
    AssistantMessage,
    ResultMessage,
    UserMessage,
    PreToolUseHookInput,
    PostToolUseHookInput,
    NotificationHookInput,
    StopHookInput,
    HookContext,
    AsyncHookJSONOutput,
)


# ========== Service Factory ==========

class ServiceFactory:
    """Service factory for lazy-loading services

    Provides a unified interface for getting service instances,
    avoiding circular imports and managing service lifecycle.
    """

    _instances: dict[str, Any] = {}

    @staticmethod
    def get(service_name: str) -> Any:
        """Get a service instance by name

        Args:
            service_name: Name of the service ('webhook', 'slack', 'event_pusher')

        Returns:
            Service instance or None if not available
        """
        if service_name in ServiceFactory._instances:
            return ServiceFactory._instances[service_name]

        instance = ServiceFactory._create_service(service_name)
        if instance is not None:
            ServiceFactory._instances[service_name] = instance
        return instance

    @staticmethod
    def _create_service(service_name: str) -> Any:
        """Create a service instance by name"""
        try:
            if service_name == "webhook":
                from .webhook import get_webhook_notifier
                return get_webhook_notifier()
            elif service_name == "slack":
                from .slack_notifier import get_slack_notifier
                return get_slack_notifier()
            elif service_name == "event_pusher":
                from api import EventPusher
                return EventPusher.get_instance()
        except ImportError:
            return None
        return None

    @staticmethod
    def reset() -> None:
        """Reset all cached service instances (for testing)"""
        ServiceFactory._instances.clear()


# ========== Webhook Notifier (Lazy Import) ==========

def _get_webhook_notifier() -> "WebhookNotifier | None":
    """Get webhook notifier using ServiceFactory"""
    return ServiceFactory.get("webhook")


async def _send_webhook_notification_async(event_type: str, data: Dict[str, Any]) -> bool:
    """Send webhook notification (async)"""
    try:
        notifier = _get_webhook_notifier()
        if notifier:
            return await notifier.send_notification(event_type, data)
    except WebhookError as e:
        logger.warning(f"Webhook notification failed: {e}")
    except Exception as e:
        logger.warning(f"Failed to send webhook notification: {type(e).__name__}: {e}")
    return False


def _send_webhook_notification(event_type: str, data: Dict[str, Any]) -> None:
    """Send webhook notification (sync wrapper)"""
    try:
        try:
            loop = asyncio.get_running_loop()
            # We're in an async context, schedule the task
            task = loop.create_task(_send_webhook_notification_async(event_type, data))
            # Add callback to suppress unhandled exceptions
            task.add_done_callback(lambda t: t.exception() if not t.cancelled() and t.done() else None)
        except RuntimeError:
            # No running event loop, run in new one
            asyncio.run(_send_webhook_notification_async(event_type, data))
    except WebhookError as e:
        logger.warning(f"Webhook notification failed: {e}")
    except Exception as e:
        logger.warning(f"Failed to send webhook notification: {type(e).__name__}: {e}")


# ========== Slack Notifier (Lazy Import) ==========

def _get_slack_notifier() -> "SlackNotifier | None":
    """Get slack notifier using ServiceFactory"""
    return ServiceFactory.get("slack")


async def _send_slack_notification_async(event_type: str, data: Dict[str, Any]) -> bool:
    """Send Slack notification (async)"""
    try:
        notifier = _get_slack_notifier()
        if notifier:
            return await notifier.send_notification(event_type, data)
    except SlackError as e:
        logger.warning(f"Slack notification failed: {e}")
    except Exception as e:
        logger.warning(f"Failed to send Slack notification: {type(e).__name__}: {e}")
    return False


def _send_slack_notification(event_type: str, data: Dict[str, Any]) -> None:
    """Send Slack notification (sync wrapper)"""
    try:
        try:
            loop = asyncio.get_running_loop()
            # We're in an async context, schedule the task
            task = loop.create_task(_send_slack_notification_async(event_type, data))
            # Add callback to suppress unhandled exceptions
            task.add_done_callback(lambda t: t.exception() if not t.cancelled() and t.done() else None)
        except RuntimeError:
            # No running event loop, run in new one
            asyncio.run(_send_slack_notification_async(event_type, data))
    except SlackError as e:
        logger.warning(f"Slack notification failed: {e}")
    except Exception as e:
        logger.warning(f"Failed to send Slack notification: {type(e).__name__}: {e}")


# ========== WebSocket Event Pusher (Lazy Import) ==========

def _get_event_pusher():
    """Get event pusher using ServiceFactory"""
    return ServiceFactory.get("event_pusher")


async def _push_log_async(level: str, message: str, source: str = "agent_core"):
    """Push log to WebSocket clients (async)"""
    pusher = _get_event_pusher()
    if pusher:
        try:
            await pusher.push_log(level, message, source)
        except Exception as e:
            logger.warning(f"Failed to push log to WebSocket: {type(e).__name__}: {e}")


def _push_log_sync(level: str, message: str, source: str = "agent_core"):
    """Push log to WebSocket clients (sync wrapper)"""
    try:
        pusher = _get_event_pusher()
        if pusher:
            try:
                loop = asyncio.get_running_loop()
                if loop.is_running():
                    task = asyncio.create_task(_push_log_async(level, message, source))
                    task.add_done_callback(lambda t: t.exception() if not t.cancelled() and t.done() else None)
            except RuntimeError:
                # No running event loop - skip WebSocket push in sync context
                pass
    except Exception as e:
        logger.warning(f"Failed to push log to WebSocket: {type(e).__name__}: {e}")


# ========== Hooks 实现 ==========

async def pre_tool_hook(input_data: Any, tool_use_id: str | None, context: Any) -> AsyncHookJSONOutput:
    """工具执行前调用 - 记录工具调用信息"""
    tool_name = input_data.get("tool_name", "unknown")
    tool_input = input_data.get("tool_input", {})

    logger.debug(f"PreToolUse: {tool_name}")
    input_preview = json.dumps(tool_input, ensure_ascii=False)
    if len(input_preview) > 300:
        input_preview = input_preview[:300] + "..."
    agent_output.render_tool_call(tool_name, tool_input, tool_use_id)

    # Push to WebSocket
    await _push_log_async("info", f"[PreToolUse] {tool_name}: {input_preview}", "tool")

    return {"async_": True}  # 允许执行


async def post_tool_hook(input_data: Any, tool_use_id: str | None, context: Any) -> AsyncHookJSONOutput:
    """工具执行后调用 - 流式输出结果"""
    tool_name = input_data.get("tool_name", "unknown")
    result = input_data.get("tool_response", {})
    agent_output.render_tool_result(result, tool_name=tool_name, tool_use_id=tool_use_id)

    # Push to WebSocket
    await _push_log_async("info", f"[PostToolUse] {tool_name}: completed", "tool")

    return {"async_": True}


async def notification_hook(input_data: Any, tool_use_id: str | None, context: Any) -> AsyncHookJSONOutput:
    """处理通知消息"""
    notification = input_data.get("notification", {}) or {}
    message = input_data.get("message") or notification.get("message", "")
    notification_type = input_data.get("notification_type") or notification.get("type", "")
    details = input_data.get("details") or notification.get("details")

    logger.info(f"Notification: {notification_type}: {message[:200]}")
    agent_output.render_notification(notification_type, message, details)

    # Push to WebSocket
    await _push_log_async("info", f"[Notification] {notification_type}: {message[:200]}", "notification")

    return {"async_": True}


async def stop_hook(input_data: Any, tool_use_id: str | None, context: Any) -> AsyncHookJSONOutput:
    """处理停止事件"""
    session_id = input_data.get("session_id", "")
    reason = input_data.get("reason", "")
    logger.info(f"Session {session_id} ended")
    agent_output.render_session_stop(session_id, reason)

    # Push to WebSocket
    await _push_log_async("info", f"Session {session_id} ended", "session")

    return {"async_": True}

from .state_manager import StateManager
from .task_selector import TaskSelector
from .git_helper import GitHelper
from .human_intervention import HumanIntervention
from .performance_monitor import PerformanceMonitor, get_monitor
from .prompt_manager import PromptManager, render_template, scan_project_structure
from .config_reloader import ConfigReloader


# 配置日志
def setup_logging(name: str = "agent_core", level: int = logging.INFO) -> logging.Logger:
    """配置日志记录器"""
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # 避免重复添加 handler
    if logger.handlers:
        return logger

    # 控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)

    # 格式化
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(formatter)

    logger.addHandler(console_handler)
    return logger


# 创建模块级日志记录器
logger = setup_logging("agent_core")


class AgentCore:
    """核心Agent逻辑 - 使用 Claude Agent SDK"""

    def __init__(self, project_root: str | None = None) -> None:
        # 解决嵌套 Claude Code 会话问题
        if "CLAUDECODE" in os.environ:
            del os.environ["CLAUDECODE"]

        self.state_manager = StateManager()
        self.task_selector = TaskSelector(self.state_manager)
        self.git_helper = GitHelper(project_root)
        self.human_intervention = HumanIntervention(self.state_manager)
        self.prompt_manager = PromptManager()
        self.config = self.state_manager.load_config()
        self.project_root = project_root or str(Path(__file__).parent.parent)

        # Initialize model provider manager
        self.provider_manager = create_provider_manager(self.config)

        # 缓存 CLAUDE.md 内容
        self._claude_md_cache: str | None = None

        # 迭代计数器，用于决定何时执行文档清理
        self._iteration_count: int = 0

        # 代码变更检测
        self._last_known_files: Dict[str, float] = {}
        self._code_changed: bool = False
        self._initial_file_state()

        # 配置热重载器
        self.config_reloader = ConfigReloader()
        self.config_reloader.add_reload_callback(self._on_config_reloaded)

        # 性能监控
        self.perf_monitor = get_monitor()

        # 指标收集器
        self.metrics_collector = get_metrics_collector()

    def _initial_file_state(self) -> None:
        """记录初始文件状态，用于检测代码变更"""
        agent_dir = Path(self.project_root) / "agent"
        if agent_dir.exists():
            for f in agent_dir.glob("*.py"):
                self._last_known_files[str(f)] = f.stat().st_mtime

    def check_code_changes(self) -> bool:
        """检测代码文件是否有变更"""
        agent_dir = Path(self.project_root) / "agent"
        if not agent_dir.exists():
            return False

        changed = False
        current_files: Dict[str, float] = {}
        for f in agent_dir.glob("*.py"):
            f_path = str(f)
            current_mtime = f.stat().st_mtime
            current_files[f_path] = current_mtime
            if f_path in self._last_known_files:
                if current_mtime > self._last_known_files[f_path]:
                    changed = True
            else:
                # 新文件
                changed = True

        if changed:
            self._code_changed = True
            # 更新跟踪状态，避免重复触发
            self._last_known_files = current_files

        return changed

    def needs_reload(self) -> bool:
        """检查是否需要重新加载（代码变更或配置变更）"""
        # 检查配置文件变更
        config_changes = self.config_reloader.check_for_changes()
        if config_changes["config"] or config_changes["feature_list"]:
            self.config_reloader.reload()
        return self._code_changed or self.check_code_changes()

    def reload_modules(self) -> bool:
        """热更新 Python 模块，重新加载修改过的代码

        注意: 不重载 agent.agent_core 自身，因为当前实例仍引用旧类定义，
        importlib.reload 后新方法不会对已有实例生效。
        若 agent_core.py 自身被修改，应走 graceful_restart 路径。
        """
        import importlib

        # 检查 agent_core.py 自身是否被修改
        core_path = Path(self.project_root) / "agent" / "agent_core.py"
        if core_path.exists():
            core_mtime = core_path.stat().st_mtime
            tracked_mtime = self._last_known_files.get(str(core_path), 0.0)
            if core_mtime > tracked_mtime:
                logger.warning("agent_core.py itself was modified, hot reload cannot apply — need graceful restart")
                return False

        # 只重载非自身的依赖模块
        modules_to_reload = [
            "agent.state_manager",
            "agent.task_selector",
            "agent.session_manager",
            "agent.git_helper",
            "agent.human_intervention",
            "agent.test_runner",
            "agent.prompt_manager",
            "agent.performance_monitor",
            "agent.config_reloader",
        ]

        reloaded = []
        failed = []

        for module_name in modules_to_reload:
            try:
                if module_name in sys.modules:
                    importlib.reload(sys.modules[module_name])
                    reloaded.append(module_name)
            except Exception as e:
                failed.append((module_name, str(e)))

        # 重新初始化组件
        if not failed:
            self._reinitialize_components()
            self._code_changed = False
            logger.info(f"Hot reload successful: {len(reloaded)} modules reloaded")
            return True
        else:
            logger.error(f"Hot reload failed: {failed}")
            return False

    def _on_config_reloaded(self) -> None:
        """配置热重载回调 — 更新运行时使用的配置"""
        self.config = self.config_reloader.get_cached_config()
        self.task_selector = TaskSelector(self.state_manager)
        self.provider_manager = create_provider_manager(self.config)
        self._claude_md_cache = None
        logger.info("Runtime config reloaded")

    def _reinitialize_components(self) -> None:
        """重新初始化所有组件（热更新后）"""
        # Clear old references before creating new instances
        self._last_known_files.clear()
        self._claude_md_cache = None

        self.state_manager = StateManager()
        self.task_selector = TaskSelector(self.state_manager)
        self.git_helper = GitHelper(self.project_root)
        self.human_intervention = HumanIntervention(self.state_manager)
        self.prompt_manager = PromptManager()
        self.config = self.state_manager.load_config()
        self.provider_manager = create_provider_manager(self.config)
        self.config_reloader = ConfigReloader()
        self.config_reloader.add_reload_callback(self._on_config_reloaded)

        # Reset performance monitor to clear accumulated data
        from .performance_monitor import reset_monitor
        reset_monitor()
        self.perf_monitor = get_monitor()
        self.metrics_collector = get_metrics_collector()

        logger.info("Components reinitialized after hot reload")

    def graceful_restart(self) -> None:
        """优雅重启：保存状态后退出，让外部进程重启"""
        logger.info("Code changes detected, preparing for graceful restart...")

        # 保存当前状态
        state = self.state_manager.load_state()
        state["needs_restart"] = True
        state["restart_reason"] = "code_changed"
        self.state_manager.save_state(state)

        agent_output.render_restart_required()

    @staticmethod
    def _normalize_tool_result_content(result_content: Any) -> str:
        """Normalize SDK tool result payloads into a bounded string."""
        if isinstance(result_content, list):
            return " ".join(str(item) for item in result_content)
        return str(result_content)

    @staticmethod
    def _remember_tool_result(
        tool_results: dict[str, str],
        tool_use_id: str,
        result_content: Any,
        max_tool_results: int,
    ) -> None:
        """Store recent tool results without unbounded growth."""
        if not tool_use_id:
            return

        result_str = AgentCore._normalize_tool_result_content(result_content)
        if tool_use_id not in tool_results and len(tool_results) >= max_tool_results:
            oldest_key = next(iter(tool_results))
            del tool_results[oldest_key]
        tool_results[tool_use_id] = result_str

    def _handle_stream_event(self, event: Dict[str, Any]) -> None:
        """Render Claude SDK stream events to the unified console."""
        event_type = event.get("type", "")

        if event_type == "content_block_delta":
            delta = event.get("delta", {})
            delta_type = delta.get("type", "")
            if delta_type == "text_delta":
                agent_output.stream_assistant_text(delta.get("text", ""))
            return

        if event_type == "content_block_stop":
            agent_output.finish_stream()
            return

        if event_type == "message_delta":
            delta = event.get("delta", {})
            agent_output.render_stop_reason(delta.get("stop_reason", ""))

    def _handle_assistant_message(
        self,
        message: AssistantMessage,
        tool_results: dict[str, str],
        max_tool_results: int,
    ) -> None:
        """Handle assistant message blocks without duplicating tool logs."""
        content = message.content
        if not isinstance(content, list):
            return

        for block in content:
            block_type = getattr(block, 'type', None)
            if block_type == "tool_result":
                tool_use_id = getattr(block, 'tool_use_id', '')
                result_content = getattr(block, 'content', '')
                self._remember_tool_result(tool_results, tool_use_id, result_content, max_tool_results)
            elif block_type == "thinking":
                thinking = getattr(block, 'thinking', '')
                if thinking:
                    agent_output.stream_thinking_text(thinking)

    def _handle_user_message(
        self,
        message: UserMessage,
        tool_results: dict[str, str],
        max_tool_results: int,
    ) -> None:
        """Capture tool results emitted through user messages."""
        content = message.content
        if not isinstance(content, list):
            return

        for block in content:
            if getattr(block, 'type', None) != "tool_result":
                continue
            tool_use_id = getattr(block, 'tool_use_id', '')
            result_content = getattr(block, 'content', '')
            self._remember_tool_result(tool_results, tool_use_id, result_content, max_tool_results)

    async def _run_follow_up_query(
        self,
        client: ClaudeSDKClient,
        prompt: str,
        session_id: str,
        phase_title: str,
    ) -> str:
        """Run self-review or cleanup prompts with the same terminal renderer."""
        agent_output.render_phase(phase_title)
        await client.query(prompt, session_id=session_id)

        tool_results: dict[str, str] = {}
        async for follow_up_msg in client.receive_response():
            if isinstance(follow_up_msg, StreamEvent):
                self._handle_stream_event(follow_up_msg.event)
            elif isinstance(follow_up_msg, AssistantMessage):
                self._handle_assistant_message(follow_up_msg, tool_results, 10)
            elif isinstance(follow_up_msg, UserMessage):
                self._handle_user_message(follow_up_msg, tool_results, 10)
            elif isinstance(follow_up_msg, ResultMessage):
                agent_output.finish_stream()
                return str(follow_up_msg.result or '')

        agent_output.finish_stream()
        return ""

    def read_claude_md(self) -> str:
        """读取 CLAUDE.md 文件内容"""
        if self._claude_md_cache:
            return self._claude_md_cache

        claude_md_path = Path(self.project_root) / "CLAUDE.md"
        if claude_md_path.exists():
            with open(claude_md_path, "r", encoding="utf-8") as f:
                self._claude_md_cache = f.read()
                return self._claude_md_cache
        return ""

    def gather_project_context(self) -> Dict[str, Any]:
        """收集项目上下文信息，用于制定计划前的分析"""
        context: Dict[str, Any] = {
            "config": self.state_manager.load_config(),
            "feature_list": self.state_manager.load_feature_list(),
            "state": self.state_manager.load_state(),
            "session_stats": self._get_session_stats(),
            "git_branch": self.git_helper.get_current_branch(),
            "git_status": self.git_helper.get_status(),
            "recent_commits": self.git_helper.get_recent_commits(5),
            "pending_tasks": [],
            "completed_tasks": [],
            "failed_tasks": [],
        }

        # 分类任务
        data: dict[str, Any] = cast(dict[str, Any], context["feature_list"])
        for task in data.get("features", []):
            status = task.get("status", "pending")
            if status == "completed":
                context["completed_tasks"].append(task)
            elif status == "failed":
                context["failed_tasks"].append(task)
            else:
                context["pending_tasks"].append(task)

        return context

    def _get_session_stats(self) -> Dict[str, Any]:
        """获取会话统计信息"""
        history = self.state_manager.load_session_history()
        sessions = history.get("sessions", [])
        return {
            "total": len(sessions),
            "completed": sum(1 for s in sessions if s.get("status") == "completed"),
            "failed": sum(1 for s in sessions if s.get("status") == "failed"),
        }

    def get_system_prompt(self) -> str:
        """获取系统提示词 - 渲染模板变量"""
        raw_prompt = self.prompt_manager.get_active_prompt()

        # Build context files list from config
        context_files = self.config.get("context_files", ["CLAUDE.md", "README.md"])
        context_list = "\n".join(f"- {f}" for f in context_files)

        variables = {
            "project_name": self.config.get("project_name", Path(self.project_root).name),
            "context_files_list": context_list,
        }

        return render_template(raw_prompt, variables)

    def get_task_prompt(self, task: Dict[str, Any]) -> str:
        """获取任务提示词 - 使用模板系统渲染"""
        git_status = self.git_helper.get_status()
        current_branch = self.git_helper.get_current_branch()

        # 读取 CLAUDE.md 关键内容
        claude_md = self.read_claude_md()
        key_sections = self._extract_key_claude_sections(claude_md)

        # 动态扫描项目结构（而非硬编码）
        project_structure = scan_project_structure(self.project_root)

        variables = {
            "task_name": task.get("name", ""),
            "task_id": task.get("id", ""),
            "task_description": task.get("description", ""),
            "task_priority": str(task.get("priority", "")),
            "project_root": self.project_root,
            "project_structure": project_structure,
            "current_branch": current_branch,
            "git_status": git_status,
            "project_guidelines": key_sections,
            "verify_command": self._get_verify_command(task),
            "test_command": self.config.get("test_command", ""),
        }

        return self.prompt_manager.render_template("task", variables)

    def _get_verify_command(self, task: Dict[str, Any]) -> str:
        """获取验证命令 - 从任务或配置中获取"""
        if task.get('verify_command'):
            return f"Run: `{task.get('verify_command')}`"
        default_cmd = self.config.get("verify_command", self.config.get("test_command", ""))
        if default_cmd:
            return f"Run: `{default_cmd}`"
        return "Verify your changes manually or run the project's test suite."

    def _build_self_review_prompt(self, completed_task: Dict[str, Any]) -> str:
        """Build prompt for post-task self-review using templates.

        Args:
            completed_task: The task that was just completed

        Returns:
            Self-review prompt
        """
        data = self.state_manager.load_feature_list()
        features = data.get("features", [])
        completed_count = sum(1 for f in features if f.get("status") == "completed")
        pending_count = sum(1 for f in features if f.get("status") == "pending")
        failed_count = sum(1 for f in features if f.get("status") == "failed")

        recent_commits = self.git_helper.get_recent_commits(5)
        current_branch = self.git_helper.get_current_branch()
        git_status = self.git_helper.get_status()

        commits_text = "\n".join(f"  - {c}" for c in recent_commits) if recent_commits else "  (none)"

        variables = {
            "completed_task_name": completed_task.get("name", "N/A"),
            "current_branch": current_branch,
            "recent_commits": commits_text,
            "git_status": git_status[:200] if git_status else "clean",
            "completed_count": str(completed_count),
            "pending_count": str(pending_count),
            "failed_count": str(failed_count),
        }

        return self.prompt_manager.render_template("self_review", variables)

    def _extract_key_claude_sections(self, claude_md: str) -> str:
        """从 CLAUDE.md 提取关键部分"""
        if not claude_md:
            return "No CLAUDE.md found."

        import re

        # 提取项目概述、技术栈、开发原则等关键部分
        key_patterns = [
            r'##\s*(?:Project\s*Overview|Technical\s*Stack|Key\s*Files|Development\s*Principles|Common\s*Commands)',
            r'###\s*(?:Project\s*Overview|Technical\s*Stack|Key\s*Files|Development\s*Principles|Common\s*Commands)',
        ]

        lines = claude_md.split('\n')
        selected_lines: list[str] = []
        in_key_section = False

        for line in lines:
            # 检查是否是关键部分的标题
            if re.match(r'^##\s+', line):
                # 检查是否是关键部分
                for pattern in key_patterns:
                    if re.search(pattern, line, re.IGNORECASE):
                        in_key_section = True
                        break
                else:
                    in_key_section = False

            if in_key_section or selected_lines:
                selected_lines.append(line)
                # 限制长度
                if len('\n'.join(selected_lines)) > 2000:
                    break

        if selected_lines:
            return '\n'.join(selected_lines)

        # 如果没有匹配到关键部分，返回前500字符
        return claude_md[:500] + "..."

    def update_claude_md(self, task: Dict[str, Any], result: Dict[str, Any]) -> None:
        """根据任务执行结果更新 CLAUDE.md"""
        claude_md_path = Path(self.project_root) / "CLAUDE.md"

        if not claude_md_path.exists():
            logger.warning("CLAUDE.md not found, skipping update")
            return

        with open(claude_md_path, "r", encoding="utf-8") as f:
            current_content = f.read()

        # 从执行结果中提取有价值的经验
        new_insight = self._extract_insight_from_result(task, result)
        if not new_insight:
            return

        # 更新内容
        updated_content = self._merge_claude_insight(current_content, new_insight, task)

        with open(claude_md_path, "w", encoding="utf-8") as f:
            f.write(updated_content)

        # 清除缓存
        self._claude_md_cache = None
        logger.info(f"CLAUDE.md updated with insights from task {task.get('id')}")

    def _extract_insight_from_result(self, task: Dict[str, Any], result: Dict[str, Any]) -> str | None:
        """从执行结果中提取有价值的见解"""
        import re

        message = result.get('message', '')
        status = result.get('status', 'unknown')

        if status != 'completed' or not message:
            return None

        insights = []

        # 提取修改内容
        modify_match = re.search(r'修改内容[:：]\s*\n?(.+?)(?=\n###|\n##|\n\n\n|\Z)', message, re.DOTALL)
        if modify_match:
            content = modify_match.group(1).strip()
            # 清理每行
            lines = [l.strip() for l in content.split('\n') if l.strip()]
            for line in lines[:3]:  # 最多3条
                if line.startswith('-'):
                    insights.append(line[:200])
                else:
                    insights.append(f"- {line[:200]}")

        # 提取问题分析
        problem_match = re.search(r'问题分析[:：]\s*\n?(.+?)(?=\n###|\n##|\n\n\n|\Z)', message, re.DOTALL)
        if problem_match:
            insights.append(f"- 问题: {problem_match.group(1).strip()[:150]}")

        # 提取验证结果
        verify_match = re.search(r'验证结果[:：]\s*\n?(.+?)(?=\n###|\n##|\n\n\n|\Z)', message, re.DOTALL)
        if verify_match:
            content = verify_match.group(1).strip()
            # 只取第一行
            first_line = content.split('\n')[0].strip()[:150]
            if first_line:
                insights.append(f"- 验证: {first_line}")

        if insights:
            # 去重
            seen = set()
            unique_insights = []
            for i in insights:
                if i not in seen:
                    seen.add(i)
                    unique_insights.append(i)
            return "\n".join(unique_insights)

        return None

    def _merge_claude_insight(self, content: str, insight: str, task: Dict[str, Any]) -> str:
        """将新见解合并到 CLAUDE.md"""
        import re

        task_id = task.get('id', 'unknown')
        task_name = task.get('name', 'unknown')

        # 查找或创建 "Lessons Learned" 部分
        lessons_pattern = r'(##\s*Lessons\s*Learned\n)'
        match = re.search(lessons_pattern, content, re.IGNORECASE)

        new_entry = f"\n### {datetime.now().strftime('%Y-%m-%d')} - {task_name} ({task_id})\n{insight}"

        if match:
            # 插入到 Lessons Learned 部分
            insert_pos = match.end()
            # 避免重复添加
            if insight not in content:
                content = content[:insert_pos] + new_entry + content[insert_pos:]
        else:
            # 在文件末尾添加
            content += f"\n\n## Lessons Learned\n{new_entry}\n"

        return content

    def plan_next_steps(self) -> List[Dict[str, Any]]:
        """基于项目上下文自主制定后续计划

        在制定计划前，系统会先收集足够的上下文信息：
        1. 当前任务状态（pending/completed/failed）
        2. 配置和会话统计
        3. Git 状态和最近的提交
        4. 失败任务的原因分析
        """
        context = self.gather_project_context()
        new_tasks: List[Dict[str, Any]] = []
        today = datetime.now().strftime('%Y-%m-%d')

        # 分析失败任务，生成修复任务
        for failed_task in context.get("failed_tasks", []):
            task_id = failed_task.get("id")
            # 检查是否已有对应的修复任务
            existing = any(t.get("id", "").startswith(f"fix-{task_id}") for t in context["pending_tasks"])
            if not existing:
                new_tasks.append({
                    "id": f"fix-{task_id}",
                    "name": f"Fix {task_id}",
                    "description": f"修复失败任务 {task_id}：{failed_task.get('description', '')}",
                    "priority": 10,  # 高优先级
                    "status": "pending",
                    "passes": False,
                    "context_files": failed_task.get("context_files", []),
                    "created_at": today,
                    "updated_at": today,
                })

        # 分析待完成任务，生成优化建议
        for pending_task in context.get("pending_tasks", []):
            priority = pending_task.get("priority", 99)
            # 如果待办任务太多，生成一些低优先级的整理任务
            if len(context["pending_tasks"]) > 10 and priority > 50:
                # 可以考虑添加一些优化任务
                pass

        # 根据会话统计添加相应任务
        stats = context.get("session_stats", {})
        if stats.get("failed", 0) > stats.get("completed", 0) * 0.3:
            # 失败率过高，添加自检任务
            new_tasks.append({
                "id": "self-check",
                "name": "System self-check",
                "description": "系统失败率过高，执行自检并优化",
                "priority": 5,
                "status": "pending",
                "passes": False,
                "created_at": today,
                "updated_at": today,
            })

        return new_tasks

    def _auto_plan_next_steps(self) -> None:
        """自动制定后续计划并将新任务添加到列表中"""
        new_tasks = self.plan_next_steps()

        if not new_tasks:
            return

        # 获取当前任务列表
        data = self.state_manager.load_feature_list()
        existing_ids = {task.get("id") for task in data.get("features", [])}

        # 添加不重复的新任务
        added_count = 0
        for task in new_tasks:
            if task.get("id") not in existing_ids:
                self.state_manager.add_feature(task)
                added_count += 1
                logger.info(f"Auto-added task: {task['id']} - {task['name']}")

        if added_count > 0:
            logger.info(f"Auto-planned {added_count} new tasks based on project context")

    def suggest_memory_cleanup(self) -> str:
        """生成 MEMORY.md 清理建议

        返回一个提示信息，让 Agent 自主判断如何清理 MEMORY.md

        Returns:
            清理建议文本
        """
        memory_file = self.state_manager.agent_dir / "MEMORY.md"

        if not memory_file.exists():
            return ""

        with open(memory_file, "r", encoding="utf-8") as f:
            content = f.read()

        # 统计
        lines = content.split('\n')
        task_record_count = content.count("### ")
        lessons_count = content.count("### 2026")

        suggestions = []

        if len(lines) > 300:
            suggestions.append(f"- MEMORY.md 内容较多 ({len(lines)} 行)，可能需要精简")

        if task_record_count > 30:
            suggestions.append(f"- 任务记录较多 ({task_record_count} 条)，考虑保留最重要的")

        if lessons_count > 20:
            suggestions.append(f"- Lessons Learned 较多 ({lessons_count} 条)，考虑合并重复内容")

        # 检查重复章节
        seen_titles = set()
        duplicates = []
        for line in lines:
            if line.startswith("## "):
                title = line[3:].strip()
                if title in seen_titles:
                    duplicates.append(title)
                seen_titles.add(title)

        if duplicates:
            suggestions.append(f"- 发现重复章节: {', '.join(duplicates[:3])}")

        if suggestions:
            return "MEMORY.md 清理建议:\n" + "\n".join(suggestions)
        return ""

    def suggest_claude_md_cleanup(self) -> str:
        """生成 CLAUDE.md 清理建议

        返回一个提示信息，让 Agent 自主判断如何清理 CLAUDE.md

        Returns:
            清理建议文本
        """
        claude_md_path = Path(self.project_root) / "CLAUDE.md"

        if not claude_md_path.exists():
            return ""

        with open(claude_md_path, "r", encoding="utf-8") as f:
            content = f.read()

        # 统计
        lines = content.split('\n')
        lessons_count = content.count("### 2026")

        suggestions = []

        if len(lines) > 200:
            suggestions.append(f"- CLAUDE.md 内容较多 ({len(lines)} 行)，可能需要精简")

        if lessons_count > 15:
            suggestions.append(f"- Lessons Learned 较多 ({lessons_count} 条)，考虑保留最精华的内容")

        # 检查重复章节
        seen_titles = set()
        duplicates = []
        for line in lines:
            if line.startswith("## ") or line.startswith("### "):
                title = line[2:].strip() if line.startswith("##") else line[3:].strip()
                if title in seen_titles:
                    duplicates.append(title)
                seen_titles.add(title)

        if duplicates:
            suggestions.append(f"- 发现重复章节: {', '.join(set(duplicates[:3]))}")

        if suggestions:
            return "CLAUDE.md 清理建议:\n" + "\n".join(suggestions)
        return ""

    def refine_memory(self, force: bool = False) -> str:
        """生成 MEMORY.md 清理任务

        不自动删除内容，而是生成一个自省任务让 Agent 自主判断如何清理

        Args:
            force: 是否强制生成（即使内容较少）

        Returns:
            清理建议文本
        """
        return self.suggest_memory_cleanup()

    def _build_memory_cleanup_prompt(self) -> str:
        """Build prompt for MEMORY.md optimization using templates.

        Returns:
            Optimization prompt, empty string if not needed
        """
        suggestion = self.suggest_memory_cleanup()
        if not suggestion:
            return ""

        recent_commits = self.git_helper.get_recent_commits(5)
        current_branch = self.git_helper.get_current_branch()

        commits_text = "\n".join(f"  - {c}" for c in recent_commits) if recent_commits else "  (none)"

        variables = {
            "cleanup_suggestions": suggestion,
            "current_branch": current_branch,
            "recent_commits": commits_text,
        }

        return self.prompt_manager.render_template("memory_cleanup", variables)

    def refine_claude_md(self, force: bool = False) -> str:
        """生成 CLAUDE.md 清理任务

        不自动删除内容，而是生成一个自省任务让 Agent 自主判断如何清理

        Args:
            force: 是否强制生成（即使内容较少）

        Returns:
            清理建议文本
        """
        return self.suggest_claude_md_cleanup()

    def _build_claude_md_cleanup_prompt(self) -> str:
        """Build prompt for CLAUDE.md optimization using templates.

        Returns:
            Optimization prompt, empty string if not needed
        """
        suggestion = self.suggest_claude_md_cleanup()
        if not suggestion:
            return ""

        recent_commits = self.git_helper.get_recent_commits(5)
        current_branch = self.git_helper.get_current_branch()

        commits_text = "\n".join(f"  - {c}" for c in recent_commits) if recent_commits else "  (none)"

        variables = {
            "cleanup_suggestions": suggestion,
            "current_branch": current_branch,
            "recent_commits": commits_text,
        }

        return self.prompt_manager.render_template("claude_md_cleanup", variables)

    async def execute_task_with_sdk(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """使用 Claude Agent SDK 执行任务"""
        task_id = task.get("id")
        task_name = task.get("name")

        logger.info(f"Executing task: {task_name}")
        logger.debug(f"Description: {task.get('description')}")

        # 更新当前任务状态
        self.state_manager.update_state({
            "current_task": task_id
        })

        # 构建提示词
        system_prompt = self.get_system_prompt()
        user_prompt = self.get_task_prompt(task)

        # 使用模型提供者系统获取配置
        model = self.provider_manager.get_model()
        provider_env = self.provider_manager.get_sdk_env_vars()

        # 从配置文件加载工具列表和 MCP 服务器（而非硬编码）
        default_tools = [
            "Read", "Write", "Edit", "Bash", "Glob", "Grep",
            "WebSearch", "WebFetch", "AskUserQuestion",
            "TodoWrite", "ExitPlanMode", "EnterPlanMode",
        ]
        allowed_tools = self.config.get("allowed_tools", default_tools)
        mcp_servers = self.config.get("mcp_servers", {})

        # 创建 agent 选项
        options = ClaudeAgentOptions(
            model=model,
            system_prompt=system_prompt,
            # 通过 env 传递 API 配置 (from provider manager)
            env=provider_env,
            # 工具列表从配置加载
            allowed_tools=allowed_tools,
            # 启用完整流式输出
            include_partial_messages=True,
            # 启用文件检查点功能，支持文件修改追踪和恢复
            enable_file_checkpointing=True,
            # 使用 acceptEdits 模式允许所有操作
            permission_mode="acceptEdits",
            # MCP 服务器从配置加载
            mcp_servers=mcp_servers,
            # 注册 Hooks
            hooks={
                "PreToolUse": [HookMatcher(hooks=[pre_tool_hook])],
                "PostToolUse": [HookMatcher(hooks=[post_tool_hook])],
                "Notification": [HookMatcher(hooks=[notification_hook])],
                "Stop": [HookMatcher(hooks=[stop_hook])],
            },
            # 工作目录
            cwd=self.project_root,
        )

        # 使用 SDK 执行任务 - 使用 ClaudeSDKClient 获得更精细的控制
        result_text = ""
        tool_results: dict[str, str] = {}  # tool_use_id -> result (bounded)
        MAX_TOOL_RESULTS = 50  # Limit stored tool results to prevent memory bloat
        session_id = None
        agent_output.reset_session()
        try:
            async with ClaudeSDKClient(options=options) as client:
                await client.query(user_prompt)

                async for message in client.receive_response():
                    # 处理流事件 - 实时显示 AI 思考过程和工具调用
                    if isinstance(message, StreamEvent):
                        self._handle_stream_event(message.event)

                    # 处理 AssistantMessage - 完整消息
                    elif isinstance(message, AssistantMessage):
                        self._handle_assistant_message(message, tool_results, MAX_TOOL_RESULTS)

                    # 处理 UserMessage - 工具结果（来自工具执行）
                    elif isinstance(message, UserMessage):
                        self._handle_user_message(message, tool_results, MAX_TOOL_RESULTS)

                    # 处理 ResultMessage - 最终结果
                    elif isinstance(message, ResultMessage):
                        agent_output.finish_stream()
                        result_text = str(message.result or '')
                        is_error = message.is_error
                        num_turns = message.num_turns
                        stop_reason = message.stop_reason
                        session_id = message.session_id
                        logger.info(f"Final Result (turns: {num_turns}, stop: {stop_reason}): {result_text[:500]}...")

                        # 检测 API 错误（如 429 rate limit）被包装为正常结果的情况
                        if not is_error and self._is_api_error_in_result(result_text):
                            logger.warning(f"Detected API error in result text: {result_text[:200]}")
                            is_error = True

                        # 任务完成后执行自省（仅当任务成功时）
                        if not is_error and session_id:
                            # 1. 任务计划自省
                            logger.info("Starting post-task self-review...")
                            review_prompt = self._build_self_review_prompt(task)
                            review_result = await self._run_follow_up_query(
                                client,
                                review_prompt,
                                session_id,
                                "Self-review",
                            )
                            logger.info(f"Self-review completed: {review_result[:300]}...")

                            # 2. MEMORY.md 清理（每5次迭代执行一次）
                            if self._iteration_count > 0 and self._iteration_count % 5 == 0:
                                memory_prompt = self._build_memory_cleanup_prompt()
                                if memory_prompt:
                                    logger.info("Starting MEMORY.md cleanup...")
                                    cleanup_result = await self._run_follow_up_query(
                                        client,
                                        memory_prompt,
                                        session_id,
                                        "MEMORY.md cleanup",
                                    )
                                    logger.info(f"MEMORY.md cleanup completed: {cleanup_result[:200]}...")

                            # 3. CLAUDE.md 清理（每10次迭代执行一次）
                            if self._iteration_count > 0 and self._iteration_count % 10 == 0:
                                claude_prompt = self._build_claude_md_cleanup_prompt()
                                if claude_prompt:
                                    logger.info("Starting CLAUDE.md cleanup...")
                                    cleanup_result = await self._run_follow_up_query(
                                        client,
                                        claude_prompt,
                                        session_id,
                                        "CLAUDE.md cleanup",
                                    )
                                    logger.info(f"CLAUDE.md cleanup completed: {cleanup_result[:200]}...")

                    # 处理其他消息类型
                    else:
                        # 处理 system 消息
                        msg_type = getattr(message, 'type', None)
                        if msg_type == "system":
                            subtype = getattr(message, 'subtype', '')
                            if subtype == "task_started":
                                desc = getattr(message, 'description', '')
                                logger.info(f"任务开始: {desc}")
                            elif subtype == "task_progress":
                                desc = getattr(message, 'description', '')
                                last_tool = getattr(message, 'last_tool_name', '')
                                logger.debug(f"进度: {desc} (工具: {last_tool})")
                            elif subtype == "task_notification":
                                status = getattr(message, 'status', '')
                                summary = getattr(message, 'summary', '')
                                logger.info(f"任务通知: {status} - {summary[:100]}")

        except CLINotFoundError as e:
            logger.error(f"Claude Code not found: {e}")
            return {
                "task_id": task_id,
                "status": "error",
                "message": f"Claude Code not found: {e}"
            }
        except CLIConnectionError as e:
            logger.error(f"Cannot connect to Claude Code: {e}")
            return {
                "task_id": task_id,
                "status": "error",
                "message": f"Connection error: {e}"
            }
        except ProcessError as e:
            logger.error(f"Claude Code process failed with exit code {e.exit_code}")
            return {
                "task_id": task_id,
                "status": "error",
                "message": f"Process error: {e}"
            }
        except ClaudeSDKError as e:
            logger.error(f"SDK error: {e}")
            return {
                "task_id": task_id,
                "status": "error",
                "message": f"SDK error: {e}"
            }
        except Exception as e:
            logger.error(f"SDK execution error: {e}")
            error_msg = str(e) if str(e) else f"Unexpected error occurred: {type(e).__name__}"
            return {
                "task_id": task_id,
                "status": "error",
                "message": error_msg
            }
        finally:
            agent_output.finish_stream()

        # 如果检测到 API 错误，返回 error 状态以触发重试
        if is_error and result_text and self._is_api_error_in_result(result_text):
            return {
                "task_id": task_id,
                "status": "error",
                "message": result_text[:500],
                "is_rate_limit": "rate_limit" in result_text.lower(),
                "session_id": session_id,
                "tool_call_count": agent_output.tool_count
            }

        return {
            "task_id": task_id,
            "status": "completed",
            "message": result_text[:500] if result_text else "Task completed",
            "session_id": session_id,
            "tool_call_count": agent_output.tool_count
        }

    @staticmethod
    def _is_api_error_in_result(result_text: str) -> bool:
        """检测结果文本中是否包含 API 错误信息"""
        error_indicators = [
            '"type":"error"',
            'rate_limit_error',
            'overloaded_error',
            'api_error',
            'authentication_error',
            'invalid_request_error',
        ]
        text_lower = result_text.lower()
        return any(indicator.lower() in text_lower for indicator in error_indicators)

    def execute_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """同步包装器 - 执行任务（带重试机制）"""
        import time as time_module
        task_id = task.get("id", "unknown")
        task_name = task.get("name", "unknown")
        start_time = time_module.time()

        # 使用性能监控跟踪任务执行
        with self.perf_monitor.track_operation("execute_task", task_id):
            # 获取重试配置
            retry_config = self.config.get("retry", {})
            max_retries = retry_config.get("max_retries", 3)
            retry_interval = retry_config.get("retry_interval", 5)

            # 重试记录
            retry_count = 0
            retry_reasons: List[str] = []
            result: Dict[str, Any] | None = None

            # 尝试执行任务
            while retry_count <= max_retries:
                try:
                    # 执行任务
                    result = asyncio.run(self.execute_task_with_sdk(task))

                    # 检查结果状态
                    if result.get("status") == "error":
                        error_msg = result.get("message", "Unknown error")

                        # 判断是否应该重试
                        if retry_count < max_retries:
                            retry_count += 1
                            retry_reasons.append(f"Attempt {retry_count}: {error_msg}")

                            # 速率限制错误使用指数退避
                            if result.get("is_rate_limit"):
                                wait_time = retry_interval * (2 ** (retry_count - 1))  # 5s, 10s, 20s...
                                logger.warning(f"Task {task.get('id')} hit rate limit. Waiting {wait_time}s before retry (attempt {retry_count}/{max_retries})...")
                            else:
                                wait_time = retry_interval
                                logger.warning(f"Task {task.get('id')} failed: {error_msg}. Retrying in {wait_time}s (attempt {retry_count}/{max_retries})...")

                            # 等待后重试
                            time_module.sleep(wait_time)

                            # 继续下一次尝试
                            continue
                        else:
                            # 达到最大重试次数，返回最终错误
                            result["retry_count"] = retry_count
                            result["retry_reasons"] = retry_reasons
                            logger.error(f"Task {task.get('id')} failed after {retry_count} attempts: {error_msg}")
                    else:
                        # 任务成功
                        if retry_count > 0:
                            result["retry_count"] = retry_count
                            result["retry_reasons"] = retry_reasons
                            logger.info(f"Task {task.get('id')} succeeded after {retry_count} retries")
                    break

                except Exception as e:
                    error_msg = str(e) if str(e) else f"Task execution failed: {type(e).__name__}"

                    if retry_count < max_retries:
                        retry_count += 1
                        retry_reasons.append(f"Attempt {retry_count}: {error_msg}")
                        logger.warning(f"Task {task.get('id')} exception: {error_msg}. Retrying in {retry_interval}s (attempt {retry_count}/{max_retries})...")

                        time_module.sleep(retry_interval)
                    else:
                        logger.error(f"Task {task.get('id')} failed after {retry_count} attempts: {error_msg}")
                        result = {
                            "task_id": task.get("id"),
                            "status": "error",
                            "message": error_msg,
                            "retry_count": retry_count,
                            "retry_reasons": retry_reasons
                        }
                        break

            # 如果循环正常结束但没有结果（理论上不会发生）
            if result is None:
                result = {
                    "task_id": task.get("id"),
                    "status": "error",
                    "message": "Max retries exceeded",
                    "retry_count": retry_count,
                    "retry_reasons": retry_reasons
                }

            # 记录任务性能数据
            duration = time_module.time() - start_time
            status = result.get("status", "unknown")
            self.perf_monitor.metrics.record_task(task_id, task_name, duration, status)

            # Record task completion metrics
            if status == "error":
                self.metrics_collector.increment_task_completed(success=False)
                self.metrics_collector.increment_error("task_execution_error")
            else:
                self.metrics_collector.increment_task_completed(success=True)

            return result

    def verify_task(self, task: Dict[str, Any]) -> bool:
        """验证任务完成度"""
        task_id: str = task.get("id", "")

        # 1. 检查任务是否已被 Agent 在执行过程中标记为 completed
        if task_id:
            data = self.state_manager.load_feature_list()
            features = data.get("features", [])
            for f in features:
                if f.get("id") == task_id and f.get("status") == "completed":
                    logger.info(f"Task {task_id} verified - already marked completed")
                    return True

        # 2. 检查是否有未提交的文件修改
        git_status = self.git_helper.get_status()
        has_changes = bool(git_status.strip())

        if has_changes and task_id:
            self.task_selector.mark_task_completed(task_id)
            logger.info(f"Task {task_id} verified - changes detected")
            return True

        # 3. 检查是否有本次执行期间产生的新 commit
        recent_commits = self.git_helper.get_recent_commits(1)
        if recent_commits and recent_commits[0] and task_id:
            # 如果最近的 commit 存在，说明 Agent 已提交了变更
            commit_msg = recent_commits[0].lower()
            if task_id.lower() in commit_msg or task.get("name", "").lower()[:20] in commit_msg:
                self.task_selector.mark_task_completed(task_id)
                logger.info(f"Task {task_id} verified - recent commit found")
                return True

        logger.info(f"Task {task_id} - no changes detected")
        return False

    def handle_error(self, error: str, task: Dict[str, Any] | None = None) -> None:
        """处理错误"""
        state = self.state_manager.load_state()
        error_count = state.get("error_count", 0) + 1

        state["error_count"] = error_count
        state["last_error"] = error

        self.state_manager.save_state(state)

        # 检查是否需要人工干预
        intervention = self.human_intervention.check_and_notify(state)

        if intervention:
            self.human_intervention.wait_for_human(intervention)

    def initialize_session(self, agent_type: str = "coder") -> Dict[str, Any]:
        """初始化会话"""
        # 开始性能监控
        self.perf_monitor.metrics.start_session()

        session_id = datetime.now().strftime("%Y%m%d_%H%M%S")

        state = self.state_manager.load_state()
        state["current_session"] = {
            "id": session_id,
            "start_time": datetime.now().isoformat(),
            "agent_type": agent_type
        }
        state["error_count"] = 0
        state["last_error"] = None

        self.state_manager.save_state(state)

        progress = self.state_manager.load_progress()
        recent_commits = self.git_helper.get_recent_commits(3)

        self.state_manager.add_session({
            "id": session_id,
            "start_time": datetime.now().isoformat(),
            "agent_type": agent_type,
            "status": "started"
        })

        return {
            "session_id": session_id,
            "progress": progress,
            "recent_commits": recent_commits,
            "pending_tasks": self.task_selector.get_pending_count()
        }

    def gather_context(self) -> Dict[str, Any]:
        """收集上下文信息"""
        current_task = self.task_selector.select_next_task()
        state = self.state_manager.load_state()
        git_status = self.git_helper.get_status()
        current_branch = self.git_helper.get_current_branch()

        return {
            "current_task": current_task,
            "state": state,
            "git_status": git_status,
            "current_branch": current_branch,
            "pending_count": self.task_selector.get_pending_count(),
            "completed_count": self.task_selector.get_completed_count(),
            "total_count": self.task_selector.get_total_count()
        }

    def complete_session(self, summary: Dict[str, Any] | None = None) -> None:
        """完成会话"""
        # 结束性能监控
        perf_stats = self.perf_monitor.metrics.end_session()

        state = self.state_manager.load_state()
        session_id = state.get("current_session", {}).get("id")

        if session_id:
            history = self.state_manager.load_session_history()
            for session in history.get("sessions", []):
                if session.get("id") == session_id:
                    session["end_time"] = datetime.now().isoformat()
                    session["status"] = "completed"
                    session["summary"] = summary or {}
                    session["performance"] = perf_stats
            self.state_manager.save_session_history(history)

        self._write_progress_summary()

        # Clear accumulated data to free memory
        self.perf_monitor.clear_operations()
        self._claude_md_cache = None
        self._last_known_files.clear()
        self._initial_file_state()

        logger.info(f"Session {session_id} completed")

    def _write_progress_summary(self) -> None:
        """写进度总结"""
        pending = self.task_selector.get_pending_count()
        completed = self.task_selector.get_completed_count()
        total = self.task_selector.get_total_count()

        entry = f"\n## {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
        entry += f"- Tasks: {completed}/{total} completed, {pending} pending\n"

        self.state_manager.append_progress(entry)

    def extract_and_save_experience(self, task: Dict[str, Any], result: Dict[str, Any]) -> None:
        """提取并保存经验教训，自动去重和整合"""
        memory_file = self.state_manager.agent_dir / "MEMORY.md"

        # 读取当前记忆
        current_content = ""
        if memory_file.exists():
            with open(memory_file, "r", encoding="utf-8") as f:
                current_content = f.read()

        # 解析并去重
        updated_content = self._merge_experience(current_content, task, result)

        self.state_manager.save_text_file(memory_file, updated_content)

        logger.info(f"经验已更新到 {memory_file}")

    def _merge_experience(self, content: str, task: Dict[str, Any], result: Dict[str, Any]) -> str:
        """解析现有内容，合并新经验，去除重复"""
        task_id = str(task.get("id", "unknown"))
        task_name = str(task.get("name", "Untitled Task"))
        task_description = str(task.get("description", ""))
        status = str(result.get("status", "unknown"))
        raw_message = str(result.get("message", "") or "")
        message = self._format_memory_message(raw_message)

        static_content = content.strip()
        task_records: List[str] = []
        existing_same_task: str | None = None

        # 分离静态部分（项目概述、技术栈、模式等）和任务记录
        if "## Task Experience Records" in content:
            parts = content.split("## Task Experience Records", 1)
            static_content = parts[0].strip()
            task_section = parts[1] if len(parts) > 1 else ""
        else:
            task_section = ""

        for entry in self._split_memory_task_entries(task_section):
            existing_id = self._extract_memory_task_id(entry)
            if existing_id != task_id:
                task_records.append(entry)
                continue

            if existing_same_task is None or len(entry) > len(existing_same_task):
                existing_same_task = entry

        # 生成新条目
        new_entry_lines = [
            f"### {datetime.now().strftime('%Y-%m-%d')} - {task_name} ({task_id})",
            "",
            f"**任务描述**: {task_description}",
            "",
            f"**执行结果**: {status}",
        ]

        if message:
            new_entry_lines.extend(["**执行消息**:", message, ""])

        # 从执行结果中提取经验（如果任务完成）
        if status == 'completed' and message:
            # 尝试从消息中提取关键学习点
            learned = self._extract_learned_from_message(raw_message)
            if learned:
                new_entry_lines.extend(["", f"**学到的经验**:", learned])

        new_entry = "\n".join(new_entry_lines).strip()

        if existing_same_task and not (status == "completed" and raw_message.strip()):
            task_records.append(existing_same_task)
        else:
            task_records.append(new_entry)

        # 限制保留最近的任务记录（最多50条）
        if len(task_records) > 50:
            task_records = task_records[-50:]

        # 重组内容
        task_content = "\n\n---\n\n".join(task_records)

        if static_content:
            return f"{static_content}\n\n## Task Experience Records\n\n{task_content}\n"
        return f"## Task Experience Records\n\n{task_content}\n"

    def _split_memory_task_entries(self, task_section: str) -> List[str]:
        """Split task records while preserving and normalizing heading markers."""
        import re

        section = task_section.strip()
        if not section:
            return []

        header_pattern = re.compile(
            r"(?m)^\s*(?:###\s+)?\d{4}-\d{2}-\d{2}\s+-\s+.+?\s+\([^)]+\)\s*$"
        )
        matches = list(header_pattern.finditer(section))
        if not matches:
            fallback = section.strip()
            return [fallback] if fallback else []

        entries: List[str] = []
        for index, match in enumerate(matches):
            start = match.start()
            end = matches[index + 1].start() if index + 1 < len(matches) else len(section)
            entry = section[start:end].strip()
            normalized = self._normalize_memory_task_entry(entry)
            if normalized:
                entries.append(normalized)

        return entries

    def _normalize_memory_task_entry(self, entry: str) -> str:
        """Normalize task record headings and remove stray separators."""
        import re

        lines = [line.rstrip() for line in entry.strip().splitlines()]
        while lines and (not lines[0].strip() or lines[0].strip() == "---"):
            lines.pop(0)
        while lines and (not lines[-1].strip() or lines[-1].strip() == "---"):
            lines.pop()

        if not lines:
            return ""

        first_line = lines[0].strip()
        if re.match(r"^\d{4}-\d{2}-\d{2}\s+-\s+.+\s+\([^)]+\)$", first_line):
            lines[0] = f"### {first_line}"
        elif first_line.startswith("### "):
            lines[0] = first_line

        return "\n".join(lines).strip()

    def _extract_memory_task_id(self, entry: str) -> str | None:
        """Extract task id from a normalized MEMORY.md task entry."""
        import re

        match = re.match(r"^###\s+\d{4}-\d{2}-\d{2}\s+-\s+.+?\s+\(([^)]+)\)", entry.strip())
        return match.group(1) if match else None

    def _format_memory_message(self, message: str, max_chars: int = 4000) -> str:
        """Keep long messages readable without silently truncating them at 500 chars."""
        normalized = message.strip()
        if len(normalized) <= max_chars:
            return normalized

        cutoff = max_chars
        last_newline = normalized.rfind("\n", 0, max_chars)
        if last_newline >= int(max_chars * 0.7):
            cutoff = last_newline

        truncated = normalized[:cutoff].rstrip()
        return f"{truncated}\n...[truncated from {len(normalized)} chars]"

    def _extract_learned_from_message(self, message: str) -> str:
        """从执行消息中提取关键经验"""
        import re

        lines = []
        current_section = None
        current_content: list[str] = []

        # 提取修改内容
        modify_match = re.search(r'修改内容[:：]\s*(.+?)(?=\n\n|\n##|\Z)', message, re.DOTALL)
        if modify_match:
            lines.append(f"- {modify_match.group(1).strip()[:200]}")

        # 提取验证结果
        verify_match = re.search(r'验证结果[:：]\s*(.+?)(?=\n\n|\n##|\Z)', message, re.DOTALL)
        if verify_match:
            lines.append(f"- {verify_match.group(1).strip()[:200]}")

        # 提取问题分析
        problem_match = re.search(r'问题分析[:：]\s*(.+?)(?=\n\n|\n##|\Z)', message, re.DOTALL)
        if problem_match:
            lines.append(f"- 问题: {problem_match.group(1).strip()[:150]}")

        if lines:
            return "\n".join(lines)

        # 如果没有匹配到结构化内容，尝试提取关键句子
        key_sentences: list[str] = re.findall(r'[^。]+(?:修复|添加|更新|修复了|添加了)[^。]+。', message)
        if key_sentences:
            result_str: str = "- " + key_sentences[0].strip()[:200]
            return result_str

        return ""

    def run_agent_loop(
        self,
        max_iterations: int = 10,
        resume_session_id: str | None = None,
        shutdown_flag: Callable[[], bool] | None = None
    ) -> Dict[str, Any]:
        """运行Agent循环

        Args:
            max_iterations: 最大迭代次数
            resume_session_id: 要恢复的会话ID（如果需要恢复之前的会话）
            shutdown_flag: 可调用对象，返回是否请求了关闭
        """
        init_info = self.initialize_session("coder")
        logger.info(f"Session initialized: {init_info['session_id']}")
        if resume_session_id:
            logger.info(f"Resuming from session: {resume_session_id}")
        logger.info(f"Pending tasks: {init_info['pending_tasks']}")

        # Push session start status to WebSocket
        _push_log_sync("info", f"Session initialized: {init_info['session_id']}", "session")

        # Record session start for metrics
        self.metrics_collector.start_session(init_info["session_id"])

        # 保存会话ID用于可能的恢复
        current_sdk_session_id = resume_session_id

        summary = {
            "completed": 0,
            "errors": 0,
            "iterations": 0,
            "session_id": init_info["session_id"]
        }

        for i in range(max_iterations):
            # 检查是否请求了优雅关闭
            if shutdown_flag and shutdown_flag():
                logger.info("Shutdown requested, finishing current iteration...")
                _push_log_sync("info", "Shutdown requested, finishing current iteration...", "agent")
                break

            logger.info(f"--- Iteration {i + 1} ---")
            _push_log_sync("info", f"--- Iteration {i + 1} ---", "iteration")

            context = self.gather_context()

            if not context["current_task"]:
                logger.info("No pending tasks. Exiting.")
                _push_log_sync("info", "No pending tasks. Exiting.", "agent")
                break

            task = context["current_task"]
            task_id = task.get("id", "unknown")
            task_name = task.get("name", "unknown")

            # Push task start
            _push_log_sync("info", f"Starting task: {task_name} ({task_id})", "task")

            try:
                # 传递 session_id 以支持会话恢复
                result = self.execute_task(task)

                # 保存最新的 session_id 用于恢复
                if result.get("session_id"):
                    current_sdk_session_id = result["session_id"]
                    summary["sdk_session_id"] = current_sdk_session_id

                # 验证任务
                verified = self.verify_task(task)

                if verified:
                    summary["completed"] += 1
                    _push_log_sync("info", f"Task completed: {task_name} ({task_id})", "task")

                    # 发送Webhook通知 - 任务完成
                    _send_webhook_notification(EventTypes.TASK_COMPLETED, {
                        "task_id": task_id,
                        "task_name": task_name,
                        "status": "completed"
                    })
                    # 发送Slack通知 - 任务完成
                    _send_slack_notification(EventTypes.TASK_COMPLETED, {
                        "task_id": task_id,
                        "task_name": task_name,
                        "status": "completed"
                    })
                else:
                    summary["errors"] += 1
                    _push_log_sync("warning", f"Task verification failed: {task_name} ({task_id})", "task")

                    # Record verification failure metrics
                    self.metrics_collector.increment_error("task_verification_failed")

                    # 发送Webhook通知 - 任务失败
                    _send_webhook_notification(EventTypes.TASK_FAILED, {
                        "task_id": task_id,
                        "task_name": task_name,
                        "status": "failed",
                        "error_message": result.get("message", "Verification failed")
                    })
                    # 发送Slack通知 - 任务失败
                    _send_slack_notification(EventTypes.TASK_FAILED, {
                        "task_id": task_id,
                        "task_name": task_name,
                        "status": "failed",
                        "error_message": result.get("message", "Verification failed")
                    })

                # 提取并保存经验
                self.extract_and_save_experience(task, result)

                # 更新 CLAUDE.md
                self.update_claude_md(task, result)

                # 自主制定后续计划
                self._auto_plan_next_steps()

                # 审查并更新任务计划（任务完成后的自我调整）
                # 注意: 自省和文档清理现在在 execute_task_with_sdk 内部执行，保持上下文不丢失

                # 检测代码变更并尝试热更新
                if self.needs_reload():
                    logger.info("Code changes detected, attempting hot reload...")
                    if self.reload_modules():
                        logger.info("Hot reload successful, continuing...")
                    else:
                        logger.warning("Hot reload failed, will trigger graceful restart")
                        self.graceful_restart()
                        break

            except Exception as e:
                error_msg = str(e) if str(e) else f"Unexpected error: {type(e).__name__}"
                logger.error(f"Error executing task: {error_msg}")
                self.handle_error(error_msg, task)
                summary["errors"] += 1
                # Record error metrics for unexpected exceptions
                self.metrics_collector.increment_error(f"loop_exception_{type(e).__name__}")

            summary["iterations"] += 1
            self._iteration_count = summary["iterations"]

        # Push session completion
        _push_log_sync("info", f"Session completed. Iterations: {summary['iterations']}, Completed: {summary['completed']}, Errors: {summary['errors']}", "session")

        # Record session end for metrics
        self.metrics_collector.end_session(init_info["session_id"])

        self.complete_session(summary)
        return summary
