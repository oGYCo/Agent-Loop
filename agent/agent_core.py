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
from typing import Optional, Dict, Any, List, cast

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


# ========== Hooks 实现 ==========

async def pre_tool_hook(input_data: Any, tool_use_id: str | None, context: Any) -> AsyncHookJSONOutput:
    """工具执行前调用 - 记录工具调用信息"""
    tool_name = input_data.get("tool_name", "unknown")
    tool_input = input_data.get("tool_input", {})

    logger.debug(f"PreToolUse: {tool_name}")
    # 显示简化后的输入
    input_preview = json.dumps(tool_input, ensure_ascii=False)
    if len(input_preview) > 300:
        input_preview = input_preview[:300] + "..."
    # Keep print for user feedback
    print(f"\n[PreToolUse] {tool_name}", flush=True)
    print(f"  Input: {input_preview}", flush=True)

    return {"async_": True}  # 允许执行


async def post_tool_hook(input_data: Any, tool_use_id: str | None, context: Any) -> AsyncHookJSONOutput:
    """工具执行后调用 - 流式输出结果"""
    import sys

    tool_name = input_data.get("tool_name", "unknown")
    result = input_data.get("tool_response", {})

    # 检查结果是否为文本类型
    if isinstance(result, str):
        # 文本结果直接打印（流式）
        text_content = result
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

    return {"async_": True}


async def notification_hook(input_data: Any, tool_use_id: str | None, context: Any) -> AsyncHookJSONOutput:
    """处理通知消息"""
    message = input_data.get("message", "")
    notification_type = input_data.get("notification_type", "")

    logger.info(f"Notification: {notification_type}: {message[:200]}")
    print(f"\n[Notification] {notification_type}: {message[:200]}", flush=True)

    return {"async_": True}


async def stop_hook(input_data: Any, tool_use_id: str | None, context: Any) -> AsyncHookJSONOutput:
    """处理停止事件"""
    session_id = input_data.get("session_id", "")
    logger.info(f"Session {session_id} ended")
    print(f"\n[Stop] Session {session_id} ended", flush=True)

    return {"async_": True}

from .state_manager import StateManager
from .task_selector import TaskSelector
from .git_helper import GitHelper
from .human_intervention import HumanIntervention


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

        # 缓存 CLAUDE.md 内容
        self._claude_md_cache: Optional[str] = None

        # 代码变更检测
        self._last_known_files: Dict[str, float] = {}
        self._code_changed: bool = False
        self._initial_file_state()

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

        for f in agent_dir.glob("*.py"):
            f_path = str(f)
            current_mtime = f.stat().st_mtime
            if f_path in self._last_known_files:
                if current_mtime > self._last_known_files[f_path]:
                    self._code_changed = True
                    return True
            else:
                # 新文件
                self._code_changed = True
                return True

        return False

    def needs_reload(self) -> bool:
        """检查是否需要重新加载（代码变更或配置变更）"""
        return self._code_changed or self.check_code_changes()

    def reload_modules(self) -> bool:
        """热更新 Python 模块，重新加载修改过的代码"""
        import importlib

        modules_to_reload = [
            "agent.agent_core",
            "agent.state_manager",
            "agent.task_selector",
            "agent.session_manager",
            "agent.git_helper",
            "agent.human_intervention",
            "agent.test_runner",
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
            # 更新文件状态
            self._initial_file_state()
            self._code_changed = False
            logger.info(f"Hot reload successful: {len(reloaded)} modules reloaded")
            return True
        else:
            logger.error(f"Hot reload failed: {failed}")
            return False

    def _reinitialize_components(self) -> None:
        """重新初始化组件（热更新后）"""
        self.state_manager = StateManager()
        self.task_selector = TaskSelector(self.state_manager)
        self.config = self.state_manager.load_config()
        # 清除 CLAUDE.md 缓存
        self._claude_md_cache = None
        logger.info("Components reinitialized after hot reload")

    def graceful_restart(self) -> None:
        """优雅重启：保存状态后退出，让外部进程重启"""
        logger.info("Code changes detected, preparing for graceful restart...")

        # 保存当前状态
        state = self.state_manager.load_state()
        state["needs_restart"] = True
        state["restart_reason"] = "code_changed"
        self.state_manager.save_state(state)

        print("\n" + "=" * 60)
        print("CODE CHANGES DETECTED")
        print("=" * 60)
        print("The agent has modified its own code and needs to restart.")
        print("Please restart the agent to continue with updated code.")
        print("=" * 60 + "\n")

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
4. **Commit after each task** - Use git to save progress (simple messages only, NO Co-Authored-By)
5. **Extract lessons** - Update MEMORY.md with what you learned

## Important Rules

- NEVER assume or guess - always use tools to verify
- NEVER use hardcoded values - use config files
- NEVER skip tests - always verify with real data
- ALWAYS provide enough context for the next agent
- ALWAYS think about how your changes integrate with the system
- 完成后更新 feature_list.json 中的任务状态
- 提取经验教训并更新 .agent/MEMORY.md"""

    def get_task_prompt(self, task: Dict[str, Any]) -> str:
        """获取任务提示词 - 包含完整上下文"""
        git_status = self.git_helper.get_status()
        current_branch = self.git_helper.get_current_branch()
        project_root = self.project_root

        # 读取 CLAUDE.md 关键内容
        claude_md = self.read_claude_md()
        # 提取关键部分（项目概述、技术栈、开发原则）
        key_sections = self._extract_key_claude_sections(claude_md)

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

## Project Guidelines (from CLAUDE.md)
{key_sections}

## Your Task Context

This is an atomic task in a self-improving agent system. Before starting:

1. **READ CLAUDE.md** - Use Read tool to understand project guidelines
2. **READ relevant source files** - Understand the code you'll modify
3. **Plan your change** - Keep it minimal and focused
4. **Implement** - Make the smallest possible change
5. **Test** - Run tests to verify
6. **Commit** - Save progress with git (DO NOT add Co-Authored-By, use simple commit messages)
7. **Update MEMORY.md** - Record what you learned

## Key Instructions

- This task should take 5-15 minutes
- Make ONE small atomic change
- If task is too large, complete only a part and update status to "in_progress"
- Always provide context for the next agent
- Run tests before marking as complete
- Use simple commit messages like "fix: description" or "feat: description", NO Co-Authored-By

## Verification
{self._get_verify_command(task)}

## Post-Task Actions
After completing this task, you MUST:
1. Review and update feature_list.json - check if any pending tasks need priority adjustments, removal, or new tasks added based on the work just completed
2. Update MEMORY.md - extract key learnings from this task and add to .agent/MEMORY.md
3. Consider if CLAUDE.md needs updates - if you discovered important patterns or insights, add them to CLAUDE.md

Start by reading CLAUDE.md and the relevant source files for this task."""

        return prompt

    def _get_verify_command(self, task: Dict[str, Any]) -> str:
        """获取验证命令"""
        if task.get('verify_command'):
            return f"Run: `{task.get('verify_command')}`"
        return "Run: `pytest tests/ -x -q`"

    def _build_self_review_prompt(self, completed_task: Dict[str, Any]) -> str:
        """构建任务完成后自省的 prompt

        让 Agent 在当前会话中分析 feature_list.json 并决定需要做的修改。

        Args:
            completed_task: 刚完成的任务

        Returns:
            自省用的 prompt
        """
        # 读取当前任务列表统计
        data = self.state_manager.load_feature_list()
        features = data.get("features", [])
        completed_count = sum(1 for f in features if f.get("status") == "completed")
        pending_count = sum(1 for f in features if f.get("status") == "pending")
        failed_count = sum(1 for f in features if f.get("status") == "failed")

        prompt = f"""## 任务完成自省

你刚刚完成了任务: **{completed_task.get('name', 'N/A')}**

当前项目状态:
- 已完成任务: {completed_count} 个
- 待办任务: {pending_count} 个
- 失败任务: {failed_count} 个

### 自省任务

请执行以下分析（直接在当前会话中完成，不要创建新任务）:

1. 读取 `.agent/feature_list.json` 文件
2. 分析所有 pending 状态的任务
3. 判断哪些任务已经过时（因为依赖已完成或不再需要）
4. 判断哪些任务优先级需要调整（考虑项目当前状态）
5. 判断是否需要新增任务
6. 判断是否有重复任务需要合并

重要:
- 如果需要修改 feature_list.json，请直接使用 Edit 或 Write 工具修改
- 不要创建新的 self-review 任务
- 只修改真正需要变更的部分
- 完成后请总结你做了哪些修改

请开始自省分析。"""

        return prompt

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

    def _extract_insight_from_result(self, task: Dict[str, Any], result: Dict[str, Any]) -> Optional[str]:
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

    def refine_claude_md(self, force: bool = False) -> str:
        """生成 CLAUDE.md 清理任务

        不自动删除内容，而是生成一个自省任务让 Agent 自主判断如何清理

        Args:
            force: 是否强制生成（即使内容较少）

        Returns:
            清理建议文本
        """
        return self.suggest_claude_md_cleanup()

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
                        user_content = message.content
                        if isinstance(user_content, list):
                            for block in user_content:
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
                        logger.info(f"Final Result (turns: {num_turns}, stop: {stop_reason}): {result_text[:500]}...")

                        # 任务完成后执行自省（仅当任务成功时）
                        if not is_error and session_id:
                            logger.info("Starting post-task self-review...")
                            review_prompt = self._build_self_review_prompt(task)
                            await client.query(review_prompt, session_id=session_id)

                            # 处理自省响应
                            async for review_msg in client.receive_response():
                                # 处理自省过程中的流事件和消息
                                if isinstance(review_msg, StreamEvent):
                                    event = review_msg.event
                                    event_type = event.get("type", "")
                                    if event_type == "content_block_delta":
                                        delta = event.get("delta", {})
                                        if delta.get("type") == "text_delta":
                                            print(delta.get("text", ""), end="", flush=True)
                                elif isinstance(review_msg, AssistantMessage):
                                    content = review_msg.content
                                    if isinstance(content, list):
                                        for block in content:
                                            block_type = getattr(block, 'type', None)
                                            if block_type == "text":
                                                text = getattr(block, 'text', '')
                                                if text:
                                                    print(f"\n🤖 {text}", end="", flush=True)
                                elif isinstance(review_msg, ResultMessage):
                                    review_result = str(review_msg.result or '')
                                    logger.info(f"Self-review completed: {review_result[:300]}...")
                                    break

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
            logger.error(f"Error in execute_task: {e}")
            error_msg = str(e) if str(e) else f"Task execution failed: {type(e).__name__}"
            return {
                "task_id": task.get("id"),
                "status": "error",
                "message": error_msg
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
            logger.info(f"Task {task_id} verified - changes detected")
            return True
        else:
            logger.info(f"Task {task_id} - no changes detected")
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

        with open(memory_file, "w", encoding="utf-8") as f:
            f.write(updated_content)

        logger.info(f"经验已更新到 {memory_file}")

    def _merge_experience(self, content: str, task: Dict[str, Any], result: Dict[str, Any]) -> str:
        """解析现有内容，合并新经验，去除重复"""
        import re

        task_id = task.get("id")
        task_name = task.get("name")
        task_description = task.get("description")
        status = result.get('status', 'unknown')
        message = result.get('message', '')[:500] if result.get('message') else ''

        # 定义分隔符：静态内容和任务记录
        static_sections = []
        task_records = []

        # 分离静态部分（项目概述、技术栈、模式等）和任务记录
        if "## Task Experience Records" in content:
            parts = content.split("## Task Experience Records")
            static_sections.append(parts[0].strip())
            task_section = parts[1] if len(parts) > 1 else ""
        else:
            # 没有任务记录部分，全部作为静态内容
            static_sections.append(content.strip())
            task_section = ""

        # 解析现有任务记录
        if task_section:
            # 按 ### 分割任务记录
            entries = re.split(r'\n### ', task_section)
            for entry in entries:
                if not entry.strip():
                    continue
                # 检查是否是重复任务
                entry_match = re.match(r'(\d{4}-\d{2}-\d{2}) - (.+?) \((\w+)\)', entry)
                if entry_match:
                    existing_id = entry_match.group(3)
                    # 只保留非重复的，或内容更完整的
                    if existing_id != task_id:
                        task_records.append(entry)
                    else:
                        # 检查现有条目是否有实际经验内容
                        if "**学到的经验**:" in entry and "[待填写]" not in entry:
                            task_records.append(entry)
                        # 如果新结果有实际内容，则用新的替换
                        elif status == 'completed' and message:
                            pass  # 跳过旧条目，用新的
                        else:
                            task_records.append(entry)
                else:
                    task_records.append(entry)

        # 生成新条目
        new_entry_lines = [
            f"### {datetime.now().strftime('%Y-%m-%d')} - {task_name} ({task_id})",
            "",
            f"**任务描述**: {task_description}",
            "",
            f"**执行结果**: {status}",
        ]

        if message:
            new_entry_lines.append(f"**执行消息**: {message}")

        # 从执行结果中提取经验（如果任务完成）
        if status == 'completed' and message:
            # 尝试从消息中提取关键学习点
            learned = self._extract_learned_from_message(message)
            if learned:
                new_entry_lines.extend(["", f"**学到的经验**:", learned])

        new_entry = "\n".join(new_entry_lines)

        # 添加新条目
        task_records.append(new_entry)

        # 限制保留最近的任务记录（最多50条）
        if len(task_records) > 50:
            task_records = task_records[-50:]

        # 重组内容
        static_content = "\n\n".join(static_sections)
        task_content = "\n\n---\n\n".join(task_records)

        return f"{static_content}\n\n## Task Experience Records\n\n{task_content}"

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

    def run_agent_loop(self, max_iterations: int = 10, resume_session_id: Optional[str] = None) -> Dict[str, Any]:
        """运行Agent循环

        Args:
            max_iterations: 最大迭代次数
            resume_session_id: 要恢复的会话ID（如果需要恢复之前的会话）
        """
        init_info = self.initialize_session("coder")
        logger.info(f"Session initialized: {init_info['session_id']}")
        if resume_session_id:
            logger.info(f"Resuming from session: {resume_session_id}")
        logger.info(f"Pending tasks: {init_info['pending_tasks']}")

        # 保存会话ID用于可能的恢复
        current_sdk_session_id = resume_session_id

        summary = {
            "completed": 0,
            "errors": 0,
            "iterations": 0,
            "session_id": init_info["session_id"]
        }

        for i in range(max_iterations):
            logger.info(f"--- Iteration {i + 1} ---")

            context = self.gather_context()

            if not context["current_task"]:
                logger.info("No pending tasks. Exiting.")
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

                # 更新 CLAUDE.md
                self.update_claude_md(task, result)

                # 自主制定后续计划
                self._auto_plan_next_steps()

                # 审查并更新任务计划（任务完成后的自我调整）
                # 注意: 自省现在在 execute_task_with_sdk 内部执行，保持上下文不丢失

                # 输出文档清理建议（让 Agent 自主决定是否处理）
                if summary["iterations"] > 0 and summary["iterations"] % 5 == 0:
                    memory_suggestion = self.refine_memory(force=False)
                    if memory_suggestion:
                        logger.info(memory_suggestion)

                if summary["iterations"] > 0 and summary["iterations"] % 10 == 0:
                    claude_suggestion = self.refine_claude_md(force=False)
                    if claude_suggestion:
                        logger.info(claude_suggestion)

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

            summary["iterations"] += 1

        self.complete_session(summary)
        return summary
