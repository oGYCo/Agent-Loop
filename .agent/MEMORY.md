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

## Lessons Learned

### 2026-03-07: Improving Error Messages

When improving error messages in the codebase:

1. **Custom exception classes**: Add `__init__` methods to custom exceptions to store the message for later retrieval with a `.message` attribute.

2. **Generic exception handling**: When catching generic `Exception`, always handle the case where `str(e)` is empty - use `type(e).__name__` to provide useful information about what went wrong.

3. **Error message patterns**:
   - Before: `return False, f"Test execution failed: {str(e)}"` - fails if e has no message
   - After: `error_msg = str(e) if str(e) else f"Unexpected error: {type(e).__name__}"`

### 2026-03-07: Adding Comprehensive Unit Tests

When adding tests for `agent_core.py`:

1. **Mock setup matters**: The test fixture sets up git_helper with mocked methods. Tests that need to verify specific return values must override the mock after the fixture is created.

2. **Method behavior differs from expectations**:
   - `verify_task` checks git status string for changes
   - `_get_session_stats` loads from session_history, not features
   - `gather_context` doesn't include timestamp field

3. **Test approach**: When testing with mocks, configure the mock within the test to return specific values rather than relying on real git operations.

4. **All 37 tests now pass** covering edge cases for initialize_session, gather_context, complete_session, execute_task, verify_task.

## Important Documentation URLs

Before implementing new features, always check these docs first:

1. **Agent SDK Overview**: https://platform.claude.com/docs/en/agent-sdk/overview
2. **Python SDK Reference**: https://platform.claude.com/docs/en/agent-sdk/python
3. **Hooks Guide**: https://platform.claude.com/docs/en/agent-sdk/hooks
4. **Streaming Output**: https://platform.claude.com/docs/en/agent-sdk/streaming-output
5. **Session Management**: https://platform.claude.com/docs/en/agent-sdk/sessions
6. **File Checkpointing**: https://platform.claude.com/docs/en/agent-sdk/file-checkpointing

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
    include_partial_messages=True,
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
- Hook functions should return `AsyncHookJSONOutput` (e.g., `{"async_": True}`)
- Hook input types: `PreToolUseHookInput`, `PostToolUseHookInput`, `NotificationHookInput`, `StopHookInput`
- For type annotations, use `Any` for hook inputs to avoid complex union type issues with HookMatcher

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

### Type Annotations (mypy)
- Use `dict[str, Any]` instead of bare `dict` for generic dicts
- Use explicit type annotation for dict literals: `context: Dict[str, Any] = {...}`
- Use `cast()` from typing to handle JSON-loaded dicts
- Empty list `[]` is inferred as `list[str]`, use `list[str] = []` to specify type
- `re.findall()` returns `list[str]`, annotate explicitly when needed
- Use `Any` for SDK hook inputs to avoid complex union type issues with HookMatcher

---

## Task Experience Records







2026-03-07: Task Plan Self-Review

When reviewing the task plan (feature_list.json):

1. **Obsolete tasks**: Check if pending tasks depend on completed tasks that are no longer relevant. None found in current review.

2. **Priority adjustments**: Consider production-critical features:
   - Retry mechanism (self-026): Critical for production reliability - bumped from priority 3 to 2
   - Graceful shutdown (self-027): Critical for production reliability - bumped from priority 3 to 2

3. **Task independence**: The current pending tasks are all independent improvements - no duplicates or blockers.

4. **Project health**: 22 completed tasks with 0 failures indicates good project stability.



---


---

2026-03-07 - Self-review: Optimize task plan (self-review-20260307160526)

**任务描述**: 请仔细审查当前任务计划。

刚完成的任务: Test Task

当前状态:
- 已完成: 22 个
- 待完成: 10 个
- 失败: 0 个

请执行以下自省任务:
1. 读取 .agent/feature_list.json 分析所有待办任务
2. 判断哪些任务已经过时（因为依赖的任务已完成或系统已改变）
3. 判断哪些任务优先级需要调整
4. 判断是否需要新增任务
5. 判断是否有重复任务需要合并

重要: 你需要自主判断并直接修改 feature_list.json，而不是简单执行脚本。
只修改真正需要变更的部分，保留合理的任务。

**执行结果**: completed
**执行消息**: ## Summary

I completed the self-review task with the following findings:


---

Analysis Results

**Current Status:**
- Completed: 23 tasks
- Pending: 10 tasks  
- Failed: 0 tasks

**No obsolete tasks found** - All 10 pending tasks are independent improvements that remain relevant:
- Test coverage (5 tasks)
- CLI improvement (1 task)
- Code quality (1 task)
- Production features (3 tasks)
- Performance monitoring & Config hot reload (low priority)


---

Priority Adjustments Made

| Task | Before |
---


---

2026-03-07 - Self-review: Optimize task plan (self-review-20260307160905)

**任务描述**: 请仔细审查当前任务计划。

刚完成的任务: Self-review: Optimize task plan

当前状态:
- 已完成: 23 个
- 待完成: 10 个
- 失败: 0 个

请执行以下自省任务:
1. 读取 .agent/feature_list.json 分析所有待办任务
2. 判断哪些任务已经过时（因为依赖的任务已完成或系统已改变）
3. 判断哪些任务优先级需要调整
4. 判断是否需要新增任务
5. 判断是否有重复任务需要合并

**执行结果**: completed
**执行消息**: ## Summary


---

Analysis Results

**Current Status:**
- Completed: 22 tasks (after cleanup)
- Pending: 11 tasks (including current self-review)

**Changes Made:**

1. **Removed obsolete task**: Deleted completed self-review task (self-review-20260307160526) to keep the list clean

2. **Priority adjustments for test tasks**:
   - self-009 (state_manager tests): 3 → 2
   - self-010 (task_selector tests): 3 → 2
   - self-022 (session_manager tests): 3 → 2
   - self-023 (human_intervention tests): 3 → 2

**Rationale**: Test coverage is critical for production quality. The project already has comprehensive tests for agent_core (37 tests passing), but other modules need similar test coverage. These tests should be higher priority to ensure code quality.

**Pending tasks summary (by priority):**
- Priority 1: Self-review (recurring)
- Priority 2: Tests (4), Retry mechanism, Graceful shutdown
- Priority 3: CLI help, Optimize imports
- Priority 4: Performance monitoring, Config hot reload


---


---

2026-03-07 - Self-review: Optimize task plan (self-review-20260307160905)

**任务描述**: 请仔细审查当前任务计划。

刚完成的任务: Self-review: Optimize task plan

当前状态:
- 已完成: 23 个
- 待完成: 10 个
- 失败: 0 个

请执行以下自省任务:
1. 读取 .agent/feature_list.json 分析所有待办任务
2. 判断哪些任务已经过时（因为依赖的任务已完成或系统已改变）
3. 判断哪些任务优先级需要调整
4. 判断是否需要新增任务
5. 判断是否有重复任务需要合并

重要: 你需要自主判断并直接修改 feature_list.json，而不是简单执行脚本。
只修改真正需要变更的部分，保留合理的任务。

**执行结果**: completed
**执行消息**: ## Summary

I completed the self-review task with the following analysis and actions:


---

Analysis Results

**Current Status:**
- Completed: 23 tasks
- Pending: 10 tasks
- Failed: 0 tasks


---

Changes Made

1. **Removed obsolete task**: Deleted completed self-review task (self-review-20260307160526) to keep the list clean

2. **Priority adjustments for test tasks** (from priority 3 to 2):
   - self-009: Add more unit tests for state_manager
   - self-010: Add more unit tests for task_selector


---

2026-03-07: Adding Unit Tests for state_manager

When adding comprehensive unit tests for `state_manager.py`:

1. **Test coverage areas added**:
   - Validation tests for `validate_config`: missing fields, invalid types, invalid values, empty documentation_urls
   - Validation tests for `validate_feature_list`: missing features key, invalid types, empty list, missing fields, invalid priority/status, duplicate IDs
   - Error handling tests: corrupted JSON files (verifies JSONDecodeError is raised)
   - Boundary condition tests: empty strings, new file creation, multiple sessions
   - Partial update tests: updating only passes or only status field

2. **Test patterns**:
   - Use `pytest.raises(Exception)` to verify exception behavior for error conditions
   - Test file-based validation by passing None to load from file
   - Verify partial updates don't modify unrelated fields

3. **Results**: Increased test coverage from 20 to 46 tests, all passing.
 

---


---

2026-03-07 - Add more unit tests for state_manager (self-009)

**任务描述**: 增加 agent/state_manager.py 的单元测试覆盖率，测试边界情况和错误处理。

**执行结果**: completed
**执行消息**: ## Summary

Successfully completed task `self-009`: Add more unit tests for state_manager.


---

Changes Made
- Added **26 new tests** to `tests/test_state_manager.py`, increasing test count from 20 to 46 tests
- All tests pass


---

Test Categories Added
1. **Validation Tests for `validate_config`** (5 tests):
   - Valid config success case
   - Missing required fields
   - Invalid field types
   - Invalid values (e.g., max_errors <= 0)
   - Empty documentation_urls

2. **Validation Tests for `va

---


---

2026-03-07 - Add more unit tests for task_selector (self-010)

**任务描述**: 增加 agent/task_selector.py 的单元测试覆盖率，测试优先级选择逻辑。

**执行结果**: completed


---

Changes Made
- Added **8 new tests** to `tests/test_task_selector.py`, increasing test count from 11 to 19 tests
- All tests pass


---

Test Categories Added
1. **Completed Count Tests**:
   - `test_get_completed_count_with_passes_true`: Tests that passes=True counts as completed even when status is "pending"

2. **Priority Selection Tests**:
   - `test_missing_priority_field`: Tests that missing priority defaults to 999
   - `test_same_priority_selection`: Tests behavior when multiple tasks have same priority

3. **Status Filtering Tests**:
   - `test_in_progress_status_skipped`: Tests in_progress tasks are excluded
   - `test_failed_status_not_selected`: Tests failed tasks are excluded
   - `test_all_tasks_failed`: Tests None return when all tasks failed

4. **Edge Case Tests**:
   - `test_passes_none_vs_false`: Tests that passes=None is treated as falsy
   - `test_get_pending_count_with_passes_true`: Tests pending excludes passes=True
   - `test_mark_task_failed_not_found`: Tests marking non-existent task as failed


---

Key Insights
- The priority selection logic: selects pending tasks where passes=False, sorted by priority (lower = higher priority)
- Missing priority defaults to 999 (lowest priority)
- passes=True marks a task as completed regardless of status

---

### 2026-03-07 - Add more unit tests for task_selector (self-010)

**任务描述**: 增加 agent/task_selector.py 的单元测试覆盖率，测试优先级选择逻辑。

**执行结果**: completed
**执行消息**: ## Summary

Successfully completed task `self-010`: Add more unit tests for task_selector.

### Changes Made
- Added **8 new tests** to `tests/test_task_selector.py`, increasing test count from 11 to 19 tests
- All tests pass

### New Tests Added
1. **Completed Count Tests**:
   - `test_get_completed_count_with_passes_true`: Tests that passes=True counts as completed even when status is "pending"

2. **Priority Selection Tests**:
   - `test_missing_priority_field`: Tests that missing priority defaults to 999

3. **Status Filtering Tests**:
   - `test_in_progress_status_skipped`: Tests in_progress tasks are excluded
   - `test_failed_status_not_selected`: Tests failed tasks are excluded
   - `test_all_tasks_failed`: Tests None return when all tasks failed

4. **Edge Case Tests**:
   - `test_passes_none_vs_false`: Tests passes=None is treated as falsy
   - `test_get_pending_count_with_passes_true`: Tests pending excludes passes=True
   - `test_mark_task_failed_not_found`: Tests marking non-existent task as failed


---

## Task Experience Records

### 2026-03-07: Add tests for session_manager.py (self-022)

**任务**: 为 agent/session_manager.py 添加单元测试，测试会话创建、状态管理和历史记录功能。

**执行结果**: completed

**验证**: 17 tests pass - `pytest tests/test_session_manager.py -v`

**发现**: 测试文件 `tests/test_session_manager.py` 已存在并包含全面的测试，覆盖:
- 会话创建/恢复 (`should_resume_session` 测试)
- 状态管理 (`get_session_stats`, `create/load_checkpoint`, `cleanup_checkpoints`)
- 历史记录 (`get_session_summary`, `add_session` 集成测试)

所有 17 个测试均已通过。