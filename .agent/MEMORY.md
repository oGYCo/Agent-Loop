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

### 2026-03-07: Prompt Management System

Added a comprehensive prompt management system to allow easy customization of prompts for different task types:

1. **New Module**: Created `agent/prompt_manager.py` with:
   - `PromptManager` class: Manages prompts stored in `.agent/prompts.json`
   - Methods: `load_prompts()`, `save_prompts()`, `get_active_prompt()`, `list_prompts()`, `add_prompt()`, `update_prompt()`, `delete_prompt()`, `set_active_prompt()`

2. **New Configuration File**: Created `.agent/prompts.json` with:
   - Default prompts: `default`, `coder`, `researcher`, `reviewer`
   - Active prompt selection stored in config

3. **CLI Integration**: Added `prompt` subcommand to `main.py`:
   - `python main.py prompt list` - List all prompts
   - `python main.py prompt show [key]` - Show prompt content
   - `python main.py prompt set <key>` - Set active prompt
   - `python main.py prompt add <key> <name> -d "description" -s "system prompt"` - Add new prompt
   - `python main.py prompt delete <key>` - Delete a prompt

4. **Integration**: Modified `agent_core.py`:
   - Added `PromptManager` import and initialization
   - Changed `get_system_prompt()` to use `self.prompt_manager.get_active_prompt()`

**Key Insight**: The prompt manager is automatically created on first access, with default prompts generated if the config file doesn't exist. This ensures backward compatibility and easy onboarding for new users.

### 2026-03-07: Performance Monitoring

Added performance monitoring functionality to track task execution time, session duration, and system resource usage:

1. **New Module**: Created `agent/performance_monitor.py` with:
   - `PerformanceMetrics` class: Collects task timings and session stats
   - `PerformanceMonitor` class: Provides context manager and decorator for tracking operations
   - Uses Python's `resource` module for system metrics (CPU time, memory usage)
   - Logs performance data via `agent_core.performance` logger

2. **Integration with AgentCore**:
   - Added `perf_monitor` instance to `AgentCore.__init__`
   - Session start/end tracking in `initialize_session` and `complete_session`
   - Task execution tracking in `execute_task` with automatic duration calculation
   - Performance stats saved to session history

3. **Usage Patterns**:
   - Context manager: `with monitor.track_operation("operation_name", task_id):`
   - Decorator: `@monitor.track_function`
   - Direct recording: `metrics.record_task(task_id, task_name, duration, status)`
   - Get system metrics: `monitor.get_system_metrics()`

4. **Key Insight**: Use Python's built-in `resource` module instead of external `psutil` for system metrics to avoid additional dependencies.

### 2026-03-07: Task Retry Mechanism

Added a retry mechanism to the task execution in `agent_core.py`:

1. **Retry Configuration**: Added `retry` config in `config.json` with:
   - `max_retries`: Maximum number of retry attempts (default: 3)
   - `retry_interval`: Seconds to wait between retries (default: 5)
   - `retry_on_errors`: List of error types that should trigger retry

### 2026-03-07: Graceful Shutdown Handling

Added graceful shutdown mechanism to handle SIGINT/SIGTERM signals:

1. **Signal Handler in main.py**: Added `_signal_handler` function that:
   - Catches SIGINT (Ctrl+C) and SIGTERM signals
   - Sets a global `_shutdown_requested` flag
   - Prints user-friendly message

2. **Shutdown Check in Agent Loop**:
   - Added `shutdown_flag` parameter to `run_agent_loop()` method
   - Pass lambda function that checks the global flag
   - Loop checks flag at start of each iteration
   - Allows current task to complete before exiting

3. **Implementation Details**:
   - Uses Python's `signal` module
   - Signal handlers are registered in `run_agent()` function
   - Agent loop completes current iteration before checking flag

2. **Implementation**: Modified `execute_task` method to:
   - Check result status after each execution
   - Retry on error status up to `max_retries` times
   - Log retry attempts and reasons
   - Return retry count and reasons in the result

3. **Key Pattern**: Use a while loop with retry counter to handle retries, with proper error tracking in the result dictionary.

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

### Claude Agent SDK Patterns

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
- When using `dict.get(key, {}).get(nested_key)`, the result is `Any` - use `cast(str, ...)` to satisfy type checkers

### Unused Import Detection

- Manually check imports by searching for usage patterns (e.g., `os\.`, `Path\(`)
- Common unused imports: `os`, `Path`, `json` (if only used in one place but not needed)
- Unused variables: Check if assigned but never used (e.g., `project_root`, `test_pattern`)
- Use `python -m py_compile` to verify syntax after changes

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

---

### 2026-03-07: Fix Type Annotation Errors in prompt_manager.py

When fixing mypy type annotation errors for methods that access nested dicts from JSON data:

1. **The issue**: Lines 166 and 181 in `prompt_manager.py` - `get_active_prompt()` and `get_active_prompt_name()` use chained `.get()` calls on dicts loaded from JSON, returning `Any` instead of `str`.

2. **The fix**: Wrap the return values with `cast(str, ...)`:
   ```python
   # Before:
   return prompts.get(active_key, {}).get("system", self.DEFAULT_PROMPTS["system"])

   # After:
   return cast(str, prompts.get(active_key, {}).get("system", self.DEFAULT_PROMPTS["system"]))
   ```

3. **Key insight**: When accessing nested dictionaries from JSON-loaded data, chained `.get()` calls return `Any` type. Use `cast()` from `typing` to explicitly tell mypy the expected return type.

4. **Verification**: Run `python -m mypy agent/prompt_manager.py --ignore-missing-imports` to confirm no errors.

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


---

2026-03-07 - Add more unit tests for task_selector (self-010)

**任务描述**: 增加 agent/task_selector.py 的单元测试覆盖率，测试优先级选择逻辑。

**执行结果**: completed
**执行消息**: ## Summary

Successfully completed task `self-010`: Add more unit tests for task_selector.


---

Changes Made
- Added **8 new tests** to `tests/test_task_selector.py`, increasing test count from 11 to 19 tests
- All tests pass


---

New Tests Added
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



---


---

2026-03-07 - Add tests for session_manager.py (self-022)

**任务描述**: 为 agent/session_manager.py 添加单元测试，测试会话创建、状态管理和历史记录功能。

**执行结果**: completed
**执行消息**: ## Summary

The task `self-022` (Add tests for session_manager.py) has been completed.


---

Findings

The test file `tests/test_session_manager.py` already existed with **17 comprehensive tests** covering:

1. **Session Creation** - via `test_should_resume_session_incomplete` tests
2. **State Management** - via `test_get_session_stats`, `test_create_and_load_checkpoint`, `test_cleanup_checkpoints`
3. **History Records** - via `test_get_session_summary`, `test_get_session_stats`, and integration 

---


---

2026-03-07 - Add task retry mechanism (self-026)

**任务描述**: 为任务执行添加重试机制。当任务失败时，根据配置的重试次数和间隔自动重试。记录重试次数和原因。

**执行结果**: completed
**执行消息**: ## Summary

I've successfully implemented the task retry mechanism for the Agent-Loop project. Here's what was done:


---

Changes Made

1. **Added retry configuration to `config.json`**:
   ```json
   "retry": {
     "max_retries": 3,
     "retry_interval": 5,
     "retry_on_errors": ["connection_error", "timeout", "process_error"]
   }
   ```

2. **Implemented retry logic in `execute_task` method** in `agent/agent_core.py`:
   - Retries on task failure (status="error") up to `max_retries` times

---


---

2026-03-07 - Add graceful shutdown handling (self-027)

**任务描述**: 为 agent 添加优雅关闭机制。处理 SIGINT/SIGTERM 信号，确保正在执行的任务能够安全完成或保存状态后再退出。

**执行结果**: completed
**执行消息**: ## Summary

I've successfully implemented graceful shutdown handling for the Agent-Loop project. Here's what was done:


---

Changes Made

1. **main.py** - Added signal handling:
   - Imported `signal` module
   - Added global `_shutdown_requested` flag
   - Added `_signal_handler()` function to catch SIGINT/SIGTERM
   - Registered signal handlers in `run_agent()` function
   - Passed shutdown lambda to agent loop

2. **agent/agent_core.py** - Added shutdown check:
   - Added optional `shutdown_flag` parameter to `run_agent_loop()`
   - Loop checks flag at start of each iteration


---

2026-03-07: Improving CLI Help with argparse

When improving CLI help in main.py:

1. **Use subparsers**: Create a hierarchical command structure with `parser.add_subparsers()` for better organization.

2. **Add examples**: Use `epilog` parameter with `formatter_class=argparse.RawDescriptionHelpFormatter` to show usage examples.

3. **Version flag**: Add `__version__` variable and `--version` argument for quick version checking.

4. **Improve descriptions**: Add both `help` (short) and `description` (long) for each subcommand.

5. **Add useful options**: Consider what options users actually need (e.g., `--max-restarts`, `--filter`, `--verbose`).

6. **Maintain backward compatibility**: Keep deprecated flags (like `--init`/`--run`) but mark them as deprecated.

---


---

2026-03-07 - Improve main.py CLI help (self-013)

**任务描述**: 改进 main.py 的命令行参数解析，添加更好的帮助信息和子命令支持。

**执行结果**: completed
**执行消息**: ## Summary

I've successfully improved the main.py CLI help with better argument parsing and subcommand support. Here's what was done:


---

Changes Made to `main.py`:
1. **Added version support** - Added `__version__` variable and `--version` flag
2. **Improved main help** - Added descriptive `description` and `epilog` with usage examples
3. **Added new options per subcommand**:
   - `run`: Added `--max-restarts` option (default: 3)
   - `list`: Added `--filter` option (all/pending/completed)
  

---


---

2026-03-07 - Optimize imports and remove unused code (self-024)

**任务描述**: 审查所有模块的导入语句，移除未使用的导入。检查并删除未使用的函数、变量和常量。使用 isort 优化导入顺序。

**执行结果**: completed
**执行消息**: ## Summary

I have successfully completed the task of optimizing imports and removing unused code. Here's what was done:


---

Changes Made

1. **agent/state_manager.py**: Removed unused `os` import

2. **agent/human_intervention.py**: Removed unused `Path` import

3. **agent/test_runner.py**: 
   - Removed unused `os` import
   - Removed unused variables `project_root` and `test_pattern` in `run_test_for_feature` method
   - Simplified `verify_feature` method to return `False` when no `verify_co

---


---

2026-03-07 - Add configuration hot reload (self-030)

**任务描述**: 添加配置热重载功能。在不重启 agent 的情况下重新加载配置文件（config.json, feature_list.json）。使用文件监控或手动触发。

**执行结果**: completed
**执行消息**: Successfully implemented configuration hot reload feature.

---

Changes Made

1. **Created `agent/config_reloader.py`** - A new configuration reloader module with:
   - `ConfigReloader` class: Handles configuration reloading
   - `ConfigWatcher` class: Optional file watching (polling-based)
   - Manual trigger via `reload()` method
   - File change detection via modification time checking
   - Callback support for reload notifications

2. **Added `reload` command to main.py**:
   - `python main.py reload` - Reload config files if changed
   - `python main.py reload --force` - Force reload even without changes

3. **Key Features**:
   - Configuration caching with invalidation
   - File modification time tracking
   - Supports both manual and automatic reload modes
   - No external dependencies required

4. **Usage**:
   ```bash
   # Reload config files
   python main.py reload

   # Force reload even if no changes
   python main.py reload --force
   ```

5. **Key Insight**: Use Python's built-in `stat().st_mtime` for file modification time checking - no external watchdog library needed for basic polling-based monitoring.

---


---

2026-03-07 - Add performance monitoring (self-028)

**任务描述**: 添加性能监控功能，跟踪任务执行时间、会话时长、系统资源使用等指标。添加日志记录关键性能数据。

**执行结果**: completed
**执行消息**: The performance monitoring feature is now complete. Here's a summary of what was implemented:

## Summary


---

Changes Made

1. **Created `agent/performance_monitor.py`** - A new performance monitoring module with:
   - `PerformanceMetrics` class: Collects task timings and session statistics
   - `PerformanceMonitor` class: Provides context manager and decorator for tracking operations
   - Uses Python's built-in `resource` module for system metrics (CPU time, memory usage)
   - Logs performance

---


---

2026-03-07 - Add configuration hot reload (self-030)

**任务描述**: 添加配置热重载功能。在不重启 agent 的情况下重新加载配置文件（config.json, feature_list.json）。使用文件监控或手动触发。

**执行结果**: completed
**执行消息**: ## Summary

Successfully implemented configuration hot reload feature (self-030):


---

Changes Made

1. **Created `agent/config_reloader.py`** - New module with:
   - `ConfigReloader` class for handling configuration reloading
   - `ConfigWatcher` class for optional file watching (polling-based)
   - File modification time tracking for change detection
   - Callback support for reload notifications
   - No external dependencies required

2. **Added `reload` command to main.py**:
   ```bash
   # 

---


---

2026-03-07 - Add feature (feature-033)

**任务描述**: 给项目增加一个能够非常方便的进行管理和自定义各种提示词的功能，以便整个项目能够适配各种不同类型的任务和工作，请先认真获取了所有必要的上下文之后再进行具体的执行

**执行结果**: completed
**执行消息**: The prompt management feature has been successfully implemented. Here's a summary:

## Implementation Summary


---

New Module: `agent/prompt_manager.py`
- Created a comprehensive `PromptManager` class for managing prompts
- Supports loading/saving prompts from/to `.agent/prompts.json`
- Provides methods: `get_active_prompt()`, `list_prompts()`, `add_prompt()`, `update_prompt()`, `delete_prompt()`, `set_active_prompt()`


---

New Configuration: `.agent/prompts.json`
- Auto-created on first access


---


---

2026-03-07: Git Push After Commit

Added automatic git push after commit in `git_helper.py`:

1. **Modified `stage_and_commit` method**:
   - Added optional `push` parameter (default: True)
   - Automatically calls `push()` after successful commit

2. **Added new `push` method**:
   - Pushes commits to remote repository
   - Handles edge cases gracefully:
     - No remote configured: prints message and returns True (not an error)
     - No upstream branch: prints message and returns True (not an error)
     - Other push failures: prints error and returns False

3. **Test results**: All 165 tests pass

4. **Key Insight**: When implementing automatic push, always handle the case where there's no remote configured or no upstream branch - these are not errors, just cases where push cannot be performed but the commit still succeeded.

---


---

2026-03-07 - Code Review: Production-Grade Analysis (feature-035)

**任务描述**: 请先仔细的review当前项目的所有的文件，检查是否存在什么问题，要用工业生产级的标准来进行审查，然后制定一系列的后续的优化和迭代任务

**执行结果**: completed

## Code Review Summary


---

Issues Found (Fixed and New Tasks Created)

#### 1. Type Annotation Errors (Priority 1)
- **agent_core.py (line 1653)**: Using built-in `callable` instead of `typing.Callable`
- **prompt_manager.py (lines 166, 181)**: Methods return `Any` but declared as `str`

#### 2. Test Infrastructure (Priority 2)
- **TestRunner class name conflict**: pytest warns about `TestRunner` class being detected as a test class
- Missing tests for: prompt_manager.py, config_reloader.py, performance_monitor.py

#### 3. Code Quality Issues (Priority 3)
- Mixed Chinese/English docstrings - inconsistent documentation language
- Long methods in agent_core.py (run_agent_loop is 100+ lines)
- No input validation for file paths (path traversal risk)

#### 4. Production Features Missing (Priority 3-4)
- No configuration file backup mechanism
- No request/response logging to file
- No API rate limiting
- No custom exception hierarchy
- No health check mechanism


---

Key Production-Grade Standards Applied

1. **Type Safety**: All code should pass mypy type checking
2. **Test Coverage**: All modules should have comprehensive unit tests
3. **Security**: Input validation for file paths to prevent path traversal
4. **Reliability**: Backup mechanisms for configuration files
5. **Observability**: Logging for debugging and monitoring
6. **Maintainability**: Consistent documentation language, readable code structure


---

New Tasks Created (15 tasks)

| Task ID | Description | Priority |
|---------|-------------|----------|
| feature-036 | Fix type errors in agent_core.py | 1 |
| feature-037 | Fix type errors in prompt_manager.py | 1 |
| feature-038 | Rename TestRunner class | 2 |
| feature-039 | Add tests for prompt_manager.py | 2 |
| feature-040 | Add tests for config_reloader.py | 2 |
| feature-041 | Add tests for performance_monitor.py | 2 |
| feature-042 | Unify code documentation language | 3 |
| feature-043 | Add input validation for file paths | 2 |
| feature-044 | Add configuration backup mechanism | 3 |
| feature-045 | Add request/response logging | 3 |
| feature-046 | Refactor long methods in agent_core.py | 3 |
| feature-047 | Add API rate limiting | 3 |
| feature-048 | Create custom exception hierarchy | 3 |
| feature-049 | Add health check mechanism | 4 |
| feature-050 | Add integration test suite | 3 |


---

Key Insight

When doing a production-grade code review:
1. Run mypy for type checking issues
2. Check test coverage for all modules
3. Look for security issues like path traversal
4. Consider production requirements: backup, logging, monitoring
5. Maintain code quality: consistent style, readable structure

---


---

2026-03-07: Fix Type Annotation Error in agent_core.py

When fixing mypy type annotation errors:

1. **The issue**: Line 1653 used Python's built-in `callable` instead of `typing.Callable`, which caused mypy type checking to fail.

2. **The fix**:
   - Added `Callable` to the imports from `typing`: `from typing import Optional, Dict, Any, List, cast, Callable`
   - Changed the parameter type from `Optional[callable]` to `Optional[Callable[[], bool]]`

3. **Key insight**: Python's built-in `callable()` checks if an object is callable, while `typing.Callable` is used for type annotations to specify the signature of a callable (e.g., `Callable[[], bool]` means a function that takes no arguments and returns a bool).

4. **Verification**: Run `python -m mypy agent/agent_core.py --ignore-missing-imports` to check for type errors.

---


---

2026-03-07 - task and plan (feature-035)

**任务描述**: 请先仔细的review当前项目的所有的文件，检查是否存在什么问题，要用工业生产级的标准来进行审查，然后制定一系列的后续的优化和迭代任务，注意任务描述一定要足够的清楚和详细

**执行结果**: completed
**执行消息**: ## 代码审查完成 (feature-035)

我已完成对 Agent-Loop 项目的全面代码审查，以工业生产级标准进行检查。以下是审查结果：


---

审查发现的问题

#### 1. 类型注解错误 (优先级 1)
| 文件 | 问题 | 行号 |
|------|------|------|
| `agent_core.py` | 使用内置 `callable` 而非 `typing.Callable` | 1653 |
| `prompt_manager.py` | 方法返回 `Any` 但声明为 `str` | 166, 181 |

#### 2. 测试基础设施 (优先级 2)
- `TestRunner` 类名与 pytest 测试发现冲突，产生警告
- 缺少测试的模块：`prompt_manager.py`、`config_reloader.py`、`performance_monitor.py`

#### 3. 代码质量问题 (优先级 3)
- 中英文混用的 docstrings - 文档风格不一致
- `agent_core.py` 中 `run_agent_l

---


---

2026-03-07 - Fix type annotation errors in agent_core.py (feature-036)

**任务描述**: 修复 agent_core.py 中的 mypy 类型错误：第1653行使用内置 callbale 而非 typing.Callable，导致类型检查失败。需要将 shutdown_flag 参数类型从 Optional[callable] 改为 Optional[Callable[[], bool]]。

**执行结果**: completed
**执行消息**: ## Task Complete

I've successfully fixed the type annotation error in `agent_core.py`. Here's a summary:


---

Changes Made

1. **Added `Callable` to imports** (line 13):
   ```python
   from typing import Optional, Dict, Any, List, cast, Callable
   ```

2. **Fixed type annotation** (line 1653):
   - Before: `shutdown_flag: Optional[callable] = None`
   - After: `shutdown_flag: Optional[Callable[[], bool]] = None`


---

Verification

- Ran mypy type checking - the error on line 1653 is now fixed

---

### 2026-03-07 - Fix type annotation errors in prompt_manager.py (feature-037)

**任务描述**: 修复 prompt_manager.py 中的 mypy 类型错误：get_active_prompt() 和 get_active_prompt_name() 方法返回类型声明为 str 但实际返回 Any。需要添加正确的类型转换或使用 cast() 处理。

**执行结果**: completed
**执行消息**: ## Task Complete

I've successfully fixed the mypy type annotation errors in `prompt_manager.py`:

### Changes Made
1. **Line 166**: Added `cast(str, ...)` around the return value of `get_active_prompt()`
2. **Line 181**: Added `cast(str, ...)` around the return value of `get_active_prompt_name()`

### Root Cause
The issue was that `prompts.get(active_key, {}).get("system", ...)` returns `Any` because:
- `prompts` is typed as `dict[str, Any]` (from JSON loading)
- Chained `.get()` calls on a `di
### 2026-03-07 - Rename TestRunner class to avoid pytest warning (feature-038)

**任务描述**: 重命名 agent/test_runner.py 中的 TestRunner 类为 TestRunnerModule 或 AgentTestRunner，避免 pytest 将其识别为测试类并产生警告。

**执行结果**: completed

**执行的更改**:
1. **agent/test_runner.py**: 将 `class TestRunner` 重命名为 `class AgentTestRunner`
2. **agent/__init__.py**: 更新导入和导出为 `AgentTestRunner`
3. **tests/test_test_runner.py**: 更新所有引用

**关键洞察**:
- pytest 默认会收集以 "Test" 开头的类作为测试类，即使它们有 `__init__` 构造函数
- 初次尝试重命名为 `TestRunnerModule` 仍然产生警告，因为它仍然以 "Test" 开头
- 最终使用 `AgentTestRunner` 作为新名称，成功消除了警告

**验证**: 运行 `pytest tests/ -v 2>&1 | grep -i 'warning'` 确认无警告输出
