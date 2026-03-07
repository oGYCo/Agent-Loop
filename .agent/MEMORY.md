# Agent-Loop Memory

This file stores accumulated experience and lessons learned from the Agent-Loop project.

## Project Overview

- **Project Name**: Agent-Loop
- **Purpose**: Autonomous agent that executes tasks incrementally
- **Framework**: Claude Agent SDK with MiniMax API
- **Repository**: `/Users/ogyco/learn/agent`

## Technical Stack

- **Language**: Python 3.13
- **SDK**: claude-agent-sdk
- **API**: MiniMax (compatible with Anthropic API)
- **Model**: MiniMax-M2.5-highspeed

## Key Files

| File | Description |
|------|-------------|
| `agent_core.py` | Core agent logic, SDK integration |
| `session_manager.py` | Session management, context handling |
| `state_manager.py` | State persistence (JSON files in `.agent/`) |
| `task_selector.py` | Task selection based on priority |
| `human_intervention.py` | Human intervention when errors exceed threshold |
| `git_helper.py` | Git operations wrapper |
| `test_runner.py` | Test execution wrapper |
| `main.py` | CLI entry point |

## Configuration Files (`.agent/`)

- `config.json` - Agent configuration and documentation URLs
- `feature_list.json` - Task list with priorities
- `progress.txt` - Progress log
- `session_history.json` - Session records
- `state.json` - Current state
- `MEMORY.md` - Accumulated experience

## Important Documentation URLs

Before implementing new features, always check these docs first:

1. **Agent SDK Overview**: https://platform.claude.com/docs/en/agent-sdk/overview
2. **Python SDK Reference**: https://platform.claude.com/docs/en/agent-sdk/python
3. **Hooks Guide**: https://platform.claude.com/docs/en/agent-sdk/hooks
4. **Streaming Output**: https://platform.claude.com/docs/en/agent-sdk/streaming-output
5. **Session Management**: https://platform.claude.com/docs/en/agent-sdk/sessions
6. **File Checkpointing**: https://platform.claude.com/docs/en/agent-sdk/file-checkpointing

## agent_core.py 结构分析 (self-002)

### 文件概览
- **行数**: 770 行
- **主要功能**: 核心 Agent 逻辑，使用 Claude Agent SDK 执行任务

### 核心组件

#### 1. Hooks 回调 (第 27-87 行)
- `pre_tool_hook`: 工具执行前调用，记录工具调用信息
- `post_tool_hook`: 工具执行后调用，流式输出结果
- `notification_hook`: 处理通知消息
- `stop_hook`: 处理停止事件

#### 2. AgentCore 类 (第 95-771 行)

**初始化方法**:
- `__init__`: 初始化 StateManager, TaskSelector, GitHelper, HumanIntervention

**提示词生成**:
- `get_system_prompt()`: 返回 Agent 系统提示词 (第 110-168 行)
- `get_task_prompt()`: 构建任务特定提示词 (第 170-241 行)
- `_get_verify_command()`: 获取验证命令 (第 243-247 行)

**任务执行**:
- `execute_task_with_sdk()`: 使用 Claude Agent SDK 异步执行任务 (核心方法，第 249-543 行)
- `execute_task()`: 同步包装器 (第 545-555 行)
- `verify_task()`: 验证任务完成度 (第 557-572 行)
- `handle_error()`: 错误处理与人干预 (第 574-588 行)

**会话管理**:
- `initialize_session()`: 创建新会话 (第 590-620 行)
- `gather_context()`: 收集当前任务和状态 (第 622-637 行)
- `complete_session()`: 完成会话并提交 (第 639-657 行)
- `extract_and_save_experience()`: 记录经验到 MEMORY.md (第 670-707 行)

**主循环**:
- `run_agent_loop()`: Agent 主循环 (第 709-770 行)

### SDK 集成方式

使用 `ClaudeAgentOptions` 配置:

1. **模型配置**: `model`, `system_prompt`, `env` (API 密钥和基础 URL)
2. **工具权限**: `allowed_tools` 列出所有允许的工具
3. **流式输出**: `include_partial_messages=True`
4. **文件检查点**: `enable_file_checkpointing=True`
5. **权限模式**: `permission_mode="acceptEdits"`
6. **MCP 服务器**: `mcp_servers` 配置 Playwright 和 Context7
7. **Hooks 注册**: 通过 `hooks` 字典注册 PreToolUse, PostToolUse, Notification, Stop

### 任务执行流程

1. **选择任务**: TaskSelector.select_next_task()
2. **构建提示词**: get_task_prompt() 包含项目结构、Git 状态
3. **执行任务**: 使用 ClaudeSDKClient 异步执行
4. **流式处理**: 遍历 receive_response() 处理消息
   - `StreamEvent`: 实时事件 (工具调用、文本增量)
   - `AssistantMessage`: AI 响应 (工具调用、工具结果)
   - `UserMessage`: 工具执行结果
   - `ResultMessage`: 最终结果
5. **验证任务**: verify_task() 检查 Git 变更
6. **记录经验**: extract_and_save_experience() 保存到 MEMORY.md

### 关键设计模式

- **异步迭代器**: 使用 `async for` 处理流式响应
- **上下文管理器**: `async with ClaudeSDKClient()` 管理连接
- **状态管理**: StateManager 持久化到 JSON
- **Git 集成**: 每次会话自动提交
7. **MCP Protocol**: https://modelcontextprotocol.io/introduction

## Key Patterns

### Agent Loop
1. Gather Context → 2. Take Action → 3. Verify Work → 4. Repeat

### Session Management
- Each session has a unique ID (timestamp-based)
- State persisted in `.agent/` directory
- Git commits after each session for recovery
- SDK `session_id` can be used for resume

### Task Management
- Features stored in `feature_list.json`
- Only `passes` and `status` fields can be modified
- Priority-based task selection (lower number = higher priority)

## Claude Agent SDK Patterns

### ClaudeAgentOptions Configuration
```python
options = ClaudeAgentOptions(
    model="MiniMax-M2.5-highspeed",
    system_prompt="...",
    env={
        "ANTHROPIC_AUTH_TOKEN": "...",
        "ANTHROPIC_BASE_URL": "https://api.minimaxi.com/anthropic",
    },
    allowed_tools=["Read", "Write", "Bash", ...],
    include_partial_messages=True,  # Enable streaming
    permission_mode="acceptEdits",
    hooks={...},
    mcp_servers={...},
)
```

### ClaudeSDKClient Pattern (Recommended)
```python
async with ClaudeSDKClient(options=options) as client:
    await client.query(user_prompt)
    async for message in client.receive_response():
        if isinstance(message, StreamEvent):
            # Handle streaming events
        elif isinstance(message, AssistantMessage):
            # Handle assistant messages
        elif isinstance(message, ResultMessage):
            # Handle final result
```

### Streaming Events
- `content_block_start`: Tool call begins
- `content_block_delta`: Incremental text/tool input
- `content_block_stop`: Tool call ends
- `message_delta`: Message-level updates

### Hooks Implementation
```python
async def pre_tool_hook(input_data, tool_use_id, context):
    tool_name = input_data.get("tool_name")
    tool_input = input_data.get("tool_input", {})
    # Log or block tool execution
    return {}  # Allow

options = ClaudeAgentOptions(
    hooks={
        "PreToolUse": [HookMatcher(hooks=[pre_tool_hook])],
        "PostToolUse": [HookMatcher(hooks=[post_tool_hook])],
    }
)
```

### Exception Handling
```python
from claude_agent_sdk import (
    CLINotFoundError,
    CLIConnectionError,
    ProcessError,
    ClaudeSDKError,
)
```

## Available Tools

### Built-in Tools
- Read, Write, Edit, Bash, Glob, Grep
- WebSearch, WebFetch, AskUserQuestion

### MCP Tools (Browser)
- browser_navigate, browser_snapshot
- browser_click, browser_type
- browser_evaluate, browser_search
- browser_tabs, browser_hover

### MiniMax MCP
- mcp__MiniMax__web_search
- mcp__MiniMax__understand_image

## API Configuration

Set via environment variables:
```bash
export ANTHROPIC_AUTH_TOKEN="your-token"
export ANTHROPIC_BASE_URL="https://api.minimaxi.com/anthropic"
```

Or via `env` parameter in ClaudeAgentOptions.

## Development Workflow

1. **Check Documentation**: Always check docs first at https://platform.claude.com/docs/en/agent-sdk/
2. **Run Tests**: `pytest tests/ -x -q`
3. **Check Types**: `mypy agent_core.py`
4. **Run Agent**: `python main.py run --iterations 1`

## Lessons Learned

### Claude Agent SDK
- Use `ClaudeSDKClient` instead of simple `query()` for more control
- Must unset `CLAUDECODE` env var when running nested sessions
- Set `include_partial_messages=True` for streaming output
- Use hooks for logging, blocking, and notifications

### API Configuration
- MiniMax uses Anthropic-compatible API
- Set correct base URL: `https://api.minimaxi.com/anthropic`

### MCP Servers
- Configure via `mcp_servers` option in ClaudeAgentOptions
- MCP tools named as `mcp__<server>__<action>`

### Permission Modes
- `default`: Ask for permission
- `acceptEdits`: Auto-approve edits
- `bypassPermissions`: No permission prompts

### File Checkpointing
- Enable with `enable_file_checkpointing=True` in ClaudeAgentOptions
- Supports file modification tracking and recovery
- Default value is `False`

## 2026-03-07 - refactor-006: File Checkpointing

**Task**: Implement file checkpointing with `enable_file_checkpointing=True`

**Implementation**:
- Added `enable_file_checkpointing=True` parameter to ClaudeAgentOptions in agent_core.py (line 241)
- This enables SDK's built-in file modification tracking and recovery capabilities

**Verification**:
- All 106 tests passed
- Command: `python -m pytest tests/ -v`

**Key Insight**:
- Use `python -c "import inspect; print(inspect.signature(ClaudeAgentOptions))"` to discover available SDK parameters
- File checkpointing helps track file changes during agent execution for recovery purposes

### 2026-03-07 - Implement file checkpointing (refactor-006)

**任务描述**: 实现文件检查点功能：enable_file_checkpointing=True，支持文件修改追踪和恢复

**执行结果**: completed
**执行消息**: ## 任务完成总结

已成功实现文件检查点功能（refactor-006）。

### 修改内容

**文件**: `agent/agent_core.py`
- 在 `ClaudeAgentOptions` 中添加了 `enable_file_checkpointing=True` 参数（第241行）

### 验证结果
- 所有 106 个测试通过 ✅

### 任务状态更新
- `featu

**学到的经验**:
- [待填写]

**改进建议**:
- [待填写]

### 2026-03-07 - Run full test suite (self-014)

**任务描述**: 运行完整的测试套件，确保所有测试通过，分析失败的测试并尝试修复。

**执行结果**: completed

**问题分析**:
- 最初测试结果：1 failed, 93 passed, 12 errors
- 问题1: `test_agent_core.py` 中的 patch 路径错误 - 使用了 `agent_core.GitHelper` 但实际应该是 `agent.agent_core.GitHelper`
- 问题2: TaskSelector 导入路径错误 - 使用了 `from task_selector import` 但应该是 `from agent.task_selector import`
- 问题3: `test_get_system_prompt` 期望中文提示词但实际代码已改为英文

**修复内容**:
- 将所有 `patch('agent_core.*')` 改为 `patch('agent.agent_core.*')`
- 将 `from task_selector import` 改为 `from agent.task_selector import`
- 将期望的中文字符串改为英文字符串

**验证结果**:
- 所有 106 个测试通过 ✅

**学到的经验**:
- 测试文件中的模块路径必须与实际模块路径一致，agent 目录下的模块需要使用完整的 `agent.xxx` 路径
- 当代码更改时（如系统提示词从中文改为英文），对应的测试也需要同步更新

**改进建议**:
- 无

### 2026-03-07 - Fix MCP tool authorization (refactor-007)

**任务描述**: 修复 MCP 工具授权：正确配置 allowed_tools 包含所有 MCP 工具

**执行结果**: completed
**执行消息**: ## 任务完成

我已成功修复 MCP 工具授权问题。主要修改如下：

### 修改内容

1. **更新 `allowed_tools` 配置** (`agent/agent_core.py`):
   - 添加了完整的 Playwright MCP 工具列表（包括 browser_console_messages, browser_resize, browser_select_option, 

**学到的经验**:
- [待填写]

**改进建议**:
- [待填写]

### 2026-03-07 - Read and understand CLAUDE.md (self-001)

**任务描述**: 读取 CLAUDE.md 文件，理解项目开发原则和架构，然后读取 README.md 了解项目概览。确保完全理解项目的开发规范。

**执行结果**: completed
**执行消息**: I have read both CLAUDE.md and README.md. Let me summarize what I've understood:

## Project Summary

**Agent-Loop** is a production-ready autonomous AI agent system built on Claude Agent SDK with Min

**学到的经验**:
- [待填写]

**改进建议**:
- [待填写]

### 2026-03-07 - Analyze agent_core.py structure (self-002)

**任务描述**: 读取 agent/agent_core.py 文件，理解核心 Agent 逻辑、SDK 集成方式和任务执行流程。

**执行结果**: completed
**执行消息**: Task completed successfully. Here's the analysis summary:

## agent_core.py 结构分析总结

### 文件信息
- **路径**: `agent/agent_core.py`
- **行数**: 770 行

### 核心组件

| 组件 | 行号 | 功能 |
|------|------|------|
| **Hook

**学到的经验**:
- [待填写]

**改进建议**:
- [待填写]

### 2026-03-07 - Run full test suite (self-014)

**任务描述**: 运行完整的测试套件，确保所有测试通过。分析失败的测试并尝试修复。

**执行结果**: completed
**执行消息**: ## Summary

Successfully ran the full test suite and fixed all failing tests.

### Test Results
- **Before fix**: 1 failed, 93 passed, 12 errors
- **After fix**: **106 passed**, 2 warnings

### Issues

**学到的经验**:
- [待填写]

**改进建议**:
- [待填写]

### 2026-03-07 - Verify project runs correctly (self-015)

**任务描述**: 实际运行项目，验证 Agent 可以正常启动和执行任务。测试 init 和 list 命令。

**执行结果**: completed

**验证结果**:
- `python main.py list` - 成功列出所有任务 ✅
- `python main.py init` - 成功初始化项目 ✅
- `python main.py status` - 成功显示状态信息 ✅

**学到的经验**:
- 项目 CLI 结构完整，支持子命令：init, run, list, add, status
- main.py 使用 argparse 子命令模式实现 CLI
- 任务列表使用 feature_list.json 存储，格式包含 id, name, description, priority, status, passes 等字段
- 命令验证比运行完整测试更快用于基本验证

**改进建议**:
- 无

### 2026-03-07 - Verify project runs correctly (self-015)

**任务描述**: 实际运行项目，验证 Agent 可以正常启动和执行任务。测试 init 和 list 命令。

**执行结果**: completed
**执行消息**: ## Task Complete

I successfully verified that the project runs correctly by testing the `init` and `list` commands.

### Verification Results

| Command | Status |
|---------|--------|
| `python main

**学到的经验**:
- [待填写]

**改进建议**:
- [待填写]

### 2026-03-07 - Add logging instead of print statements (self-003)

**任务描述**: 将 agent_core.py 中的 print 语句替换为 Python logging 模块，创建统一的日志配置。

**执行结果**: completed

**修改内容**:
1. 添加 `import logging` 到文件头部
2. 创建 `setup_logging()` 函数配置日志记录器
3. 创建模块级 `logger` 实例
4. 将大部分 print 语句替换为 logging 调用：
   - `logger.info()`: 任务开始/完成、会话状态
   - `logger.debug()`: 详细调试信息
   - `logger.error()`: 错误信息

**保留的 print 语句**:
- 流式输出（hooks 和 SDK 响应处理中的实时用户反馈）
- 这些需要直接输出到 stdout 以提供实时反馈

**验证结果**:
- `grep -c 'import logging' agent/agent_core.py` 返回 1
- Python 导入测试通过

**学到的经验**:
- 日志模块应该保留流式输出使用 print，因为这些是面向用户的实时反馈
- 使用适当的日志级别：info 用于一般状态，debug 用于详细调试，error 用于错误
- logging 支持格式化输出，比 print 更灵活

**改进建议**:
- 可以考虑将日志配置移到单独的配置模块中，实现更统一的日志管理
- 可以添加日志文件输出而非仅控制台输出

### 2026-03-07 - Add logging instead of print statements (self-003)

**任务描述**: 将 agent_core.py 中的 print 语句替换为 Python logging 模块。创建统一的日志配置。

**执行结果**: completed
**执行消息**: Task completed successfully. Here's a summary:

## Summary

### Changes Made
1. **Added logging import** at the top of `agent/agent_core.py`
2. **Created logging configuration**:
   - Added `setup_log

**学到的经验**:
- [待填写]

**改进建议**:
- [待填写]

### 2026-03-07 - Add type annotations to state_manager.py (self-004)

**任务描述**: 使用 mypy 检查 agent/state_manager.py 的类型错误，然后添加完整的类型注解。

**执行结果**: completed

**问题分析**:
- mypy 报错：`Returning Any from function declared to return "dict[str, Any]"`
- 原因：`json.load()` 返回 `Any` 类型，但函数声明返回 `dict[str, Any]`

**修复内容**:
- 添加 `from typing import cast` 导入
- 对所有 `json.load()` 调用使用 `cast(dict[str, Any], json.load(f))` 包装
- 共修复 5 处类型错误

**验证结果**:
- `python -m mypy agent/state_manager.py` - state_manager.py 错误已修复 ✅
- `pytest tests/test_state_manager.py -v` - 所有 19 个测试通过 ✅

**学到的经验**:
- `json.load()` 返回 `Any` 类型，需要使用 `typing.cast()` 显式转换为目标类型
- 这是处理 JSON 反序列化类型注解的标准 Python 模式

**改进建议**:
- 无
