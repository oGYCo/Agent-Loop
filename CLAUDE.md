# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Agent-Loop** is a production-ready autonomous AI agent system built on Claude Agent SDK with MiniMax API backend. It automates task execution with real-time streaming, session management, and human intervention.

## Development Principles (Critical)

1. **Production-grade code**: All code must meet production standards - no fake logic or mock implementations in real code
2. **Real data testing**: Tests must use real data and environments, not mocked responses
3. **No hardcoding**: Avoid hardcoded values; use configuration files and environment variables
4. **Research first**: Always gather sufficient context before implementing - check documentation and existing code
5. **System integration**: New modules must integrate properly with the existing system, not just work in isolation
6. **No TODO shortcuts**: Never use TODO comments to reduce workload - complete all requirements genuinely

## Common Commands

```bash
# Install dependencies (uv)
uv sync

# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_agent_core.py -v

# Quick test with fail-fast
pytest tests/ -x -q

# Type checking
mypy agent_core.py

# Run agent
python main.py run --iterations 3

# List tasks
python main.py list

# Check status
python main.py status

# Initialize project
python main.py init
```

## Architecture

### Core Modules

| Module | Responsibility |
|--------|----------------|
| `agent/agent_core.py` | Core agent logic, SDK integration, task execution |
| `agent/session_manager.py` | Session lifecycle, context management |
| `agent/state_manager.py` | State persistence to JSON files in `.agent/` |
| `agent/task_selector.py` | Priority-based task selection |
| `agent/human_intervention.py` | Human intervention when error threshold exceeded |
| `agent/git_helper.py` | Git operations wrapper |
| `agent/test_runner.py` | Test execution wrapper |
| `main.py` | CLI entry point |

### Data Flow

```
main.py → AgentCore.run_agent_loop()
         → TaskSelector.select_next_task() → execute_task()
         → ClaudeSDKClient (SDK) → StreamEvent handling
         → GitHelper (commit) → StateManager (persist)
```

### Configuration (`.agent/`)

- `config.json` - Model, API, documentation URLs
- `feature_list.json` - Task list with priorities
- `state.json` - Current session state
- `session_history.json` - Completed sessions
- `MEMORY.md` - Accumulated experience

### SDK Integration Pattern

```python
# Use ClaudeSDKClient for fine control
async with ClaudeSDKClient(options=options) as client:
    await client.query(user_prompt)
    async for message in client.receive_response():
        # Handle StreamEvent, AssistantMessage, ResultMessage
```

Key SDK features used:
- `include_partial_messages=True` for streaming
- `HookMatcher` for PreToolUse, PostToolUse hooks
- `permission_mode="acceptEdits"` for auto-approval
- `enable_file_checkpointing=True` for file recovery

## Important References

Before implementing features, always check:

1. **Claude Agent SDK Docs**: https://platform.claude.com/docs/en/agent-sdk/overview
2. **Python SDK**: https://platform.claude.com/docs/en/agent-sdk/python
3. **Hooks Guide**: https://platform.claude.com/docs/en/agent-sdk/hooks
4. **Streaming Output**: https://platform.claude.com/docs/en/agent-sdk/streaming-output
5. **Sessions**: https://platform.claude.com/docs/en/agent-sdk/sessions

Configuration URLs are also available in `.agent/config.json` under `documentation_urls`.

## Testing Guidelines

- Tests use real files and subprocesses, not mocks
- Each module has corresponding test file in `tests/`
- Temporary directories created via `tempfile.TemporaryDirectory()`
- Git operations tested with real git commands in temp dirs
- State isolation ensured via fixture replacement

## Environment Variables

```bash
ANTHROPIC_AUTH_TOKEN    # API token (required)
ANTHROPIC_BASE_URL      # API endpoint (default: https://api.minimaxi.com/anthropic)
```

## Current Tasks

Run `python main.py list` to see pending refactoring tasks in `.agent/feature_list.json`.
