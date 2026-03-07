"""Agent Core - 核心Agent逻辑模块 (使用 Claude Agent SDK)

基于 Anthropic Claude Agent SDK 的实现
"""

import os
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List

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
from claude_agent_sdk.types import StreamEvent, AssistantMessage, ResultMessage, UserMessage


# ========== Hooks 实现 ==========

async def pre_tool_hook(input_data: dict, tool_use_id: str | None, context: dict) -> dict:
    """工具执行前调用 - 记录工具调用信息"""
    tool_name = input_data.get("tool_name", "unknown")
    tool_input = input_data.get("tool_input", {})

    print(f"\n[PreToolUse] {tool_name}", flush=True)
    # 显示简化后的输入
    input_preview = json.dumps(tool_input, ensure_ascii=False)
    if len(input_preview) > 300:
        input_preview = input_preview[:300] + "..."
    print(f"  Input: {input_preview}", flush=True)

    return {}  # 允许执行


async def post_tool_hook(input_data: dict, tool_use_id: str | None, context: dict) -> dict:
    """工具执行后调用 - 流式输出结果"""
    import sys

    tool_name = input_data.get("tool_name", "unknown")
    result = input_data.get("result", {})
    result_type = input_data.get("result_type", "unknown")

    # 根据结果类型进行流式输出
    if result_type == "text":
        # 文本结果直接打印（流式）
        text_content = result.get("text", "")
        if text_content:
            print(f"\n📤 Result: ", end="", flush=True)
            # 流式输出每个字符或行
            print(text_content, end="", flush=True)
            sys.stdout.flush()
            print()  # 换行
    else:
        # 非文本结果（如文件操作）显示摘要
        result_preview = str(result)
        if len(result_preview) > 500:
            result_preview = result_preview[:500] + "..."

        print(f"\n✅ [PostToolUse] {tool_name}: completed")
        if result_preview:
            print(f"  Result: {result_preview[:300]}...")
        sys.stdout.flush()

    return {}


async def notification_hook(input_data: dict, tool_use_id: str | None, context: dict) -> dict:
    """处理通知消息"""
    message = input_data.get("message", "")
    notification_type = input_data.get("notification_type", "")

    print(f"\n[Notification] {notification_type}: {message[:200]}", flush=True)

    return {}


async def stop_hook(input_data: dict, tool_use_id: str | None, context: dict) -> dict:
    """处理停止事件"""
    session_id = input_data.get("session_id", "")
    print(f"\n[Stop] Session {session_id} ended", flush=True)

    return {}

from .state_manager import StateManager
from .task_selector import TaskSelector
from .git_helper import GitHelper
from .human_intervention import HumanIntervention


class AgentCore:
    """核心Agent逻辑 - 使用 Claude Agent SDK"""

    def __init__(self, project_root: Optional[str] = None) -> None:
        # 解决嵌套 Claude Code 会话问题
        if "CLAUDECODE" in os.environ:
            del os.environ["CLAUDECODE"]

        self.state_manager = StateManager()
        self.task_selector = TaskSelector(self.state_manager)
        self.git_helper = GitHelper(project_root)
        self.human_intervention = HumanIntervention(self.state_manager)
        self.config = self.state_manager.load_config()
        self.project_root = project_root or str(Path(__file__).parent.parent)

    def get_system_prompt(self) -> str:
        """获取系统提示词"""
        return """You are an autonomous AI agent for the Agent-Loop project.

## CRITICAL: Read Project Context First

Before starting any task, you MUST read these key files:
1. CLAUDE.md - Project guidelines and architecture
2. README.md - Project overview and usage
3. The relevant source files for the task

Use the Read tool to read these files completely.

## Your Mission

You are responsible for the continuous improvement of this Agent-Loop project. Your work follows this loop:
1. Read project context (CLAUDE.md, README.md)
2. Understand the current task
3. Implement the solution
4. Test and verify
5. Update task status
6. Extract lessons learned

## Available Tools

### Browser Tools (Preferred)
- Browser Navigate, Snapshot, Click, Type, Evaluate, Search

### Web Tools
- WebSearch: Search for latest information
- WebFetch: Fetch web page content

### File Tools
- Read: Read file content
- Write: Create new files
- Edit: Modify existing files
- Glob: Find files by pattern
- Grep: Search file content

### Terminal Tools
- Bash: Execute commands

## Working Principles

1. **Always read CLAUDE.md first** - It contains critical development guidelines
2. **Keep changes minimal and focused** - One small atomic change per task
3. **Test before completing** - Run tests to verify your changes
4. **Commit after each task** - Use git to save progress
5. **Extract lessons** - Update MEMORY.md with what you learned

## Important Rules

- NEVER assume or guess - always use tools to verify
- NEVER use hardcoded values - use config files
- NEVER skip tests - always verify with real data
- ALWAYS provide enough context for the next agent
- ALWAYS think about how your changes integrate with the system
- 完成后更新 feature_list.json 中的任务状态
- 提取经验教训并更新 .agent/MEMORY.md"""

    def get_task_prompt(self, task: Dict[str, Any]) -> str:  # type: ignore[no-untyped-def]
        """获取任务提示词 - 包含完整上下文"""
        git_status = self.git_helper.get_status()
        current_branch = self.git_helper.get_current_branch()
        project_root = self.project_root

        prompt = f"""# Task: {task.get('name')}

## Task ID
`{task.get('id')}`

## Description
{task.get('description')}

## Priority
{task.get('priority')} (lower = higher priority)

## Project Structure
```
{project_root}/
├── agent/                  # Core package (READ FIRST)
│   ├── __init__.py
│   ├── agent_core.py       # Main agent logic
│   ├── session_manager.py
│   ├── state_manager.py
│   ├── task_selector.py
│   ├── human_intervention.py
│   ├── git_helper.py
│   └── test_runner.py
├── tests/                  # Unit tests
├── main.py                 # CLI entry
├── CLAUDE.md              # Project guidelines (READ FIRST)
├── README.md              # Documentation
├── pyproject.toml         # Project config
└── .agent/                # Configuration
    ├── config.json
    ├── feature_list.json  # Task list
    └── MEMORY.md          # Lessons learned
```

## Current Git Status
```
Branch: {current_branch}
{git_status}
```

## Your Task Context

This is an atomic task in a self-improving agent system. Before starting:

1. **READ CLAUDE.md** - Use Read tool to understand project guidelines
2. **READ relevant source files** - Understand the code you'll modify
3. **Plan your change** - Keep it minimal and focused
4. **Implement** - Make the smallest possible change
5. **Test** - Run tests to verify
6. **Commit** - Save progress with git
7. **Update MEMORY.md** - Record what you learned

## Key Instructions

- This task should take 5-15 minutes
- Make ONE small atomic change
- If task is too large, complete only a part and update status to "in_progress"
- Always provide context for the next agent
- Run tests before marking as complete

## Verification
{self._get_verify_command(task)}

Start by reading CLAUDE.md and the relevant source files for this task."""

        return prompt

    def _get_verify_command(self, task: Dict[str, Any]) -> str:  # type: ignore[no-untyped-def]
        """获取验证命令"""
        if task.get('verify_command'):
            return f"Run: `{task.get('verify_command')}`"
        return "Run: `pytest tests/ -x -q`"

    async def execute_task_with_sdk(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """使用 Claude Agent SDK 执行任务"""
        task_id = task.get("id")
        task_name = task.get("name")

        print(f"\nExecuting task: {task_name}")
        print(f"Description: {task.get('description')}")

        # 更新当前任务状态
        self.state_manager.update_state({
            "current_task": task_id
        })

        # 构建提示词
        system_prompt = self.get_system_prompt()
        user_prompt = self.get_task_prompt(task)

        # 配置选项 - 使用 MiniMax 模型
        model = self.config.get("model", "MiniMax-M2.5-highspeed")

        # 获取环境变量
        api_key = os.environ.get("ANTHROPIC_AUTH_TOKEN", "")
        base_url = os.environ.get("ANTHROPIC_BASE_URL", "https://api.minimaxi.com/anthropic")

        # 创建 agent 选项
        options = ClaudeAgentOptions(
            model=model,
            system_prompt=system_prompt,
            # 通过 env 传递 API 配置
            env={
                "ANTHROPIC_AUTH_TOKEN": api_key,
                "ANTHROPIC_BASE_URL": base_url,
            },
            # 允许所有内置工具和 MCP 工具
            allowed_tools=[
                # 内置工具
                "Read", "Write", "Edit", "Bash", "Glob", "Grep",
                "WebSearch", "WebFetch", "AskUserQuestion",
                "TodoWrite", "ExitPlanMode", "EnterPlanMode",
                "mcp__plugin_playwright_playwright__browser_navigate",
                "mcp__plugin_playwright_playwright__browser_snapshot",
                "mcp__plugin_playwright_playwright__browser_click",
                "mcp__plugin_playwright_playwright__browser_type",
                "mcp__plugin_playwright_playwright__browser_evaluate",
                "mcp__plugin_playwright_playwright__browser_search",
                "mcp__plugin_playwright_playwright__browser_tabs",
                "mcp__plugin_playwright_playwright__browser_console_messages",
                "mcp__plugin_playwright_playwright__browser_resize",
                "mcp__plugin_playwright_playwright__browser_select_option",
                "mcp__plugin_playwright_playwright__browser_hover",
                "mcp__plugin_playwright_playwright__browser_drag",
                "mcp__plugin_playwright_playwright__browser_install",
                "mcp__plugin_playwright_playwright__browser_take_screenshot",
                "mcp__plugin_playwright_playwright__browser_network_requests",
                "mcp__plugin_playwright_playwright__browser_handle_dialog",
                "mcp__plugin_playwright_playwright__browser_file_upload",
                "mcp__plugin_playwright_playwright__browser_press_key",
                "mcp__plugin_playwright_playwright__browser_wait_for",
                "mcp__plugin_playwright_playwright__browser_navigate_back",
                "mcp__plugin_playwright_playwright__browser_run_code",
                "mcp__plugin_playwright_playwright__browser_close",
                "mcp__plugin_playwright_playwright__browser_fill_form",
                # MiniMax MCP 工具
                "mcp__MiniMax__web_search",
                "mcp__MiniMax__understand_image",
                # Context7 MCP 工具 (文档查找)
                "mcp__context7__get-context7-library-docs",
                "mcp__context7__get-library-description",
            ],
            # 启用完整流式输出
            include_partial_messages=True,
            # 启用文件检查点功能，支持文件修改追踪和恢复
            enable_file_checkpointing=True,
            # 使用 acceptEdits 模式允许所有操作
            permission_mode="acceptEdits",
            # 配置 MCP 服务器
            mcp_servers={
                "playwright": {
                    "command": "npx",
                    "args": ["-y", "@playwright/mcp@latest"]
                },
                "context7": {
                    "command": "npx",
                    "args": ["-y", "@context7/mcp-server"]
                }
            },
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
        tool_call_count = 0
        tool_results: dict[str, str] = {}  # tool_use_id -> result
        session_id = None
        try:
            async with ClaudeSDKClient(options=options) as client:
                await client.query(user_prompt)

                async for message in client.receive_response():
                    # 处理流事件 - 实时显示 AI 思考过程和工具调用
                    if isinstance(message, StreamEvent):
                        event = message.event
                        event_type = event.get("type", "")

                        if event_type == "content_block_start":
                            # 工具开始调用
                            content_block = event.get("content_block", {})
                            block_type = content_block.get("type", "")
                            if block_type == "tool_use":
                                tool_name = content_block.get("name", "unknown")
                                tool_call_count += 1
                                print(f"\n🔧 Tool #{tool_call_count}: {tool_name}", flush=True)

                        elif event_type == "content_block_delta":
                            # 增量内容 - 实时文本或工具输入或工具结果
                            delta = event.get("delta", {})
                            delta_type = delta.get("type", "")

                            if delta_type == "text_delta":
                                # 实时文本输出（AI思考或工具结果）
                                text = delta.get("text", "")
                                print(text, end="", flush=True)

                            elif delta_type == "input_json_delta":
                                # 工具输入增量
                                partial_json = delta.get("partial_json", "")
                                if partial_json:
                                    print(partial_json, end="", flush=True)

                            elif delta_type == "content_block_stop":
                                print()  # 换行

                        elif event_type == "message_delta":
                            # 消息级别的更新
                            delta = event.get("delta", {})
                            stop_reason = delta.get("stop_reason", "")
                            if stop_reason:
                                print(f"\n[Stop Reason: {stop_reason}]")

                        elif event_type == "message_stop":
                            # 消息流结束
                            pass

                    # 处理 AssistantMessage - 完整消息
                    elif isinstance(message, AssistantMessage):
                        content = message.content
                        if isinstance(content, list):
                            for block in content:
                                block_type = getattr(block, 'type', None)
                                if block_type == "tool_use":
                                    tool_call_count += 1
                                    tool_name = getattr(block, 'name', 'unknown')
                                    tool_input = getattr(block, 'input', {})
                                    tool_id = getattr(block, 'id', '')
                                    # 简化显示输入内容
                                    input_str = json.dumps(tool_input, ensure_ascii=False, indent=2)
                                    if len(input_str) > 500:
                                        input_str = input_str[:500] + "..."
                                    print(f"\n🔧 Tool #{tool_call_count}: {tool_name}", flush=True)
                                    print(f"   Input: {input_str[:300]}...", flush=True)
                                elif block_type == "tool_result":
                                    # 工具结果 - 流式输出
                                    tool_use_id = getattr(block, 'tool_use_id', '')
                                    result_content = getattr(block, 'content', '')
                                    is_error = getattr(block, 'is_error', False)

                                    # 流式输出结果
                                    prefix = "❌" if is_error else "📤"
                                    print(f"   {prefix} Result:", end=" ", flush=True)

                                    if isinstance(result_content, list):
                                        for item in result_content:
                                            print(str(item), end="", flush=True)
                                    else:
                                        print(str(result_content), end="", flush=True)
                                    print()  # 换行

                                    # 保存完整结果
                                    if isinstance(result_content, list):
                                        result_str = " ".join([str(item) for item in result_content])
                                    else:
                                        result_str = str(result_content)
                                    tool_results[tool_use_id] = result_str

                                elif block_type == "text":
                                    # 文本内容 - 流式输出
                                    text = getattr(block, 'text', '')
                                    if text:
                                        print(f"\n🤖 {text}", end="", flush=True)
                                elif block_type == "thinking":
                                    # 思考过程 - 流式输出
                                    thinking = getattr(block, 'thinking', '')
                                    if thinking:
                                        print(f"\n💭 {thinking[:200]}...", end="", flush=True)

                    # 处理 UserMessage - 工具结果（来自工具执行）
                    elif isinstance(message, UserMessage):
                        content = message.content
                        if isinstance(content, list):
                            for block in content:
                                block_type = getattr(block, 'type', None)
                                if block_type == "tool_result":
                                    tool_use_id = getattr(block, 'tool_use_id', '')
                                    result_content = getattr(block, 'content', '')
                                    is_error = getattr(block, 'is_error', False)

                                    # 流式输出工具结果
                                    prefix = "❌" if is_error else "📤"
                                    print(f"   {prefix} Result:", end=" ", flush=True)

                                    if isinstance(result_content, list):
                                        for item in result_content:
                                            print(str(item), end="", flush=True)
                                    else:
                                        print(str(result_content), end="", flush=True)
                                    print()

                    # 处理 ResultMessage - 最终结果
                    elif isinstance(message, ResultMessage):
                        result_text = str(message.result or '')
                        is_error = message.is_error
                        num_turns = message.num_turns
                        stop_reason = message.stop_reason
                        session_id = message.session_id
                        print(f"\n✅ Final Result (turns: {num_turns}, stop: {stop_reason}): {result_text[:500]}...")

                    # 处理其他消息类型
                    else:
                        # 处理 system 消息
                        msg_type = getattr(message, 'type', None)
                        if msg_type == "system":
                            subtype = getattr(message, 'subtype', '')
                            if subtype == "task_started":
                                desc = getattr(message, 'description', '')
                                print(f"\n[系统] 任务开始: {desc}")
                            elif subtype == "task_progress":
                                desc = getattr(message, 'description', '')
                                last_tool = getattr(message, 'last_tool_name', '')
                                print(f"[系统] 进度: {desc} (工具: {last_tool})")
                            elif subtype == "task_notification":
                                status = getattr(message, 'status', '')
                                summary = getattr(message, 'summary', '')
                                print(f"[系统] 任务通知: {status} - {summary[:100]}")

        except CLINotFoundError as e:
            print(f"Error: Claude Code not found. Please install Claude Code.")
            return {
                "task_id": task_id,
                "status": "error",
                "message": f"Claude Code not found: {e}"
            }
        except CLIConnectionError as e:
            print(f"Error: Cannot connect to Claude Code. Please check your connection.")
            return {
                "task_id": task_id,
                "status": "error",
                "message": f"Connection error: {e}"
            }
        except ProcessError as e:
            print(f"Error: Claude Code process failed with exit code {e.exit_code}")
            return {
                "task_id": task_id,
                "status": "error",
                "message": f"Process error: {e}"
            }
        except ClaudeSDKError as e:
            print(f"SDK error: {e}")
            return {
                "task_id": task_id,
                "status": "error",
                "message": f"SDK error: {e}"
            }
        except Exception as e:
            print(f"SDK execution error: {e}")
            return {
                "task_id": task_id,
                "status": "error",
                "message": str(e)
            }

        return {
            "task_id": task_id,
            "status": "completed",
            "message": result_text[:500] if result_text else "Task completed",
            "session_id": session_id,
            "tool_call_count": tool_call_count
        }

    def execute_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """同步包装器 - 执行任务"""
        try:
            return asyncio.run(self.execute_task_with_sdk(task))
        except Exception as e:
            print(f"Error in execute_task: {e}")
            return {
                "task_id": task.get("id"),
                "status": "error",
                "message": str(e)
            }

    def verify_task(self, task: Dict[str, Any]) -> bool:
        """验证任务完成度"""
        # 简化验证：检查是否有文件修改
        task_id: str = task.get("id", "")
        git_status = self.git_helper.get_status()

        # 如果有变更，认为任务基本完成
        has_changes = bool(git_status.strip())

        if has_changes and task_id:
            self.task_selector.mark_task_completed(task_id)
            print(f"Task {task_id} verified - changes detected")
            return True
        else:
            print(f"Task {task_id} - no changes detected")
            return False

    def handle_error(self, error: str, task: Optional[Dict[str, Any]] = None) -> None:
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

    def complete_session(self, summary: Optional[Dict[str, Any]] = None) -> None:
        """完成会话"""
        state = self.state_manager.load_state()
        session_id = state.get("current_session", {}).get("id")

        if session_id:
            history = self.state_manager.load_session_history()
            for session in history.get("sessions", []):
                if session.get("id") == session_id:
                    session["end_time"] = datetime.now().isoformat()
                    session["status"] = "completed"
                    session["summary"] = summary or {}
            self.state_manager.save_session_history(history)

        commit_message = f"Session {session_id}: {summary.get('message', 'Progress update') if summary else 'Progress update'}"
        self.git_helper.stage_and_commit(commit_message)

        self._write_progress_summary()
        print(f"\nSession {session_id} completed")

    def _write_progress_summary(self) -> None:
        """写进度总结"""
        pending = self.task_selector.get_pending_count()
        completed = self.task_selector.get_completed_count()
        total = self.task_selector.get_total_count()

        entry = f"\n## {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
        entry += f"- Tasks: {completed}/{total} completed, {pending} pending\n"

        self.state_manager.append_progress(entry)

    def extract_and_save_experience(self, task: Dict[str, Any], result: Dict[str, Any]) -> None:
        """提取并保存经验教训"""
        memory_file = self.state_manager.agent_dir / "MEMORY.md"

        # 读取当前记忆
        current_content = ""
        if memory_file.exists():
            with open(memory_file, "r", encoding="utf-8") as f:
                current_content = f.read()

        # 生成新的经验条目
        task_id = task.get("id")
        task_name = task.get("name")
        task_description = task.get("description")

        # 提取关键信息
        new_entry = f"""
### {datetime.now().strftime('%Y-%m-%d')} - {task_name} ({task_id})

**任务描述**: {task_description}

**执行结果**: {result.get('status', 'unknown')}
**执行消息**: {result.get('message', '')[:200]}

**学到的经验**:
- [待填写]

**改进建议**:
- [待填写]
"""

        # 添加到记忆文件
        updated_content = current_content + new_entry

        with open(memory_file, "w", encoding="utf-8") as f:
            f.write(updated_content)

        print(f"\n经验已记录到 {memory_file}")

    def run_agent_loop(self, max_iterations: int = 10, resume_session_id: Optional[str] = None) -> Dict[str, Any]:
        """运行Agent循环

        Args:
            max_iterations: 最大迭代次数
            resume_session_id: 要恢复的会话ID（如果需要恢复之前的会话）
        """
        init_info = self.initialize_session("coder")
        print(f"Session initialized: {init_info['session_id']}")
        if resume_session_id:
            print(f"Resuming from session: {resume_session_id}")
        print(f"Pending tasks: {init_info['pending_tasks']}")

        # 保存会话ID用于可能的恢复
        current_sdk_session_id = resume_session_id

        summary = {
            "completed": 0,
            "errors": 0,
            "iterations": 0,
            "session_id": init_info["session_id"]
        }

        for i in range(max_iterations):
            print(f"\n--- Iteration {i + 1} ---")

            context = self.gather_context()

            if not context["current_task"]:
                print("No pending tasks. Exiting.")
                break

            task = context["current_task"]
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
                else:
                    summary["errors"] += 1

                # 提取并保存经验
                self.extract_and_save_experience(task, result)

            except Exception as e:
                print(f"Error executing task: {e}")
                self.handle_error(str(e), task)
                summary["errors"] += 1

            summary["iterations"] += 1

        self.complete_session(summary)
        return summary
