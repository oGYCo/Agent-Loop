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
