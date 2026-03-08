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
7. **First principles thinking**: You cannot always assume that the person assigning a task knows exactly what they want or how to achieve it. Exercise critical judgment and ground your approach in the fundamental needs and core problems. If the motivations and objectives are ambiguous, prioritize gathering accurate and relevant context by all available means. If the goal is clear but the proposed path is suboptimal, take the initiative to adjust it and implement a more efficient solution.

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

# Run tests with coverage
pytest tests/ --cov=agent --cov-report=term-missing
pytest tests/ --cov=agent --cov-report=html  # HTML report in htmlcov/

# Type checking
mypy agent/agent_core.py

# Run agent
python main.py run --iterations 3

# List tasks
python main.py list

# Check status
python main.py status

# Initialize project
python main.py init

# Template management
python main.py template list              # List all prompt templates
python main.py template show <name>       # Show template content
python main.py template scaffold          # Export templates to .agent/prompt_templates/
python main.py template reset <name>      # Reset template to built-in default

# Prompt preset management
python main.py prompt list                # List prompt presets
python main.py prompt set <key>           # Set active prompt
```

## Architecture

### Core Modules

| Module | Responsibility |
|--------|----------------|
| `agent/agent_core.py` | Core agent logic, SDK integration, task execution |
| `agent/prompt_manager.py` | Template engine, prompt presets, user-overridable prompt templates |
| `agent/session_manager.py` | Session lifecycle, context management |
| `agent/state_manager.py` | State persistence to JSON files in `.agent/` |
| `agent/task_selector.py` | Priority-based task selection |
| `agent/human_intervention.py` | Human intervention when error threshold exceeded |
| `agent/git_helper.py` | Git status, branch, and diff operations |
| `agent/test_runner.py` | Test execution wrapper |
| `agent/performance_monitor.py` | Performance metrics tracking |
| `agent/config_reloader.py` | Configuration hot reload |
| `agent/metrics.py` | Prometheus metrics collection and export |
| `agent/webhook.py` | Webhook notification system |
| `agent/email_notifier.py` | Email notification service with SMTP support |
| `agent/slack_notifier.py` | Slack notification service with Block Kit formatting |
| `agent/logging_.py` | Structured logging with structlog (JSON for file, console for terminal) |
| `agent/console.py` | Rich console utilities for interactive CLI output |
| `main.py` | CLI entry point |
| `api.py` | FastAPI REST API server |

### Data Flow

```
main.py → AgentCore.run_agent_loop()
         → TaskSelector.select_next_task() → execute_task()
         → ClaudeSDKClient (SDK) → StreamEvent handling
         → StateManager (persist)
```

### Configuration (`.agent/`)

- `config.json` - Model, API, tools, context_files, verify_command, mcp_servers
- `feature_list.json` - Task list with priorities
- `prompts.json` - Named prompt presets (active prompt selection)
- `prompt_templates/` - User-overridable prompt templates (`.md` files)
- `state.json` - Current session state
- `session_history.json` - Completed sessions
- `MEMORY.md` - Accumulated experience

### Prompt Template System

All prompts use a template engine with `{{variable}}` substitution:
- **Template resolution**: User override (`.agent/prompt_templates/<name>.md`) → Built-in defaults
- **Available templates**: `system`, `task`, `self_review`, `memory_cleanup`, `claude_md_cleanup`
- **System prompt variants**: `default`, `coder`, `researcher`, `reviewer` (set via `session_type` in config)
- **Key variables**: `{{project_name}}`, `{{project_structure}}`, `{{task_name}}`, `{{task_description}}`, `{{context_files_list}}`
- **Config-driven SDK options**: `allowed_tools`, `mcp_servers`, `verify_command`, `context_files` all read from config.json

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

## Best Practices

### Error Handling
- **NEVER** use `except Exception: pass` - this silently swallows errors
- Always log exceptions with `logger.warning()` or `logger.error()`
- Include exception type and message in logs for debugging
- Use `logger.debug()` for expected runtime errors (e.g., no event loop) to avoid log noise
- Good examples: `webhook.py`, `email_notifier.py`, `git_helper.py`, `test_runner.py`

### Type Annotations
- Use `TYPE_CHECKING` to avoid circular imports
- Use `type: ignore[valid-type]` for third-party library type issues
- Use `cast()` for complex type narrowing
- Use explicit `Dict[str, Any]` for heterogeneous dictionaries
- Run `mypy agent/ --ignore-missing-imports` to check types

### Documentation Maintenance
- Update MEMORY.md after completing important tasks
- Keep CLAUDE.md in sync with architecture changes
- Maintain clear `context_files` in feature_list.json tasks
- Ensure feature_list.json reflects current project state

### Post-Task Actions (Critical)
After completing any task, the agent MUST:
1. Review feature_list.json - manually adjust priorities, remove obsolete tasks, add new tasks if needed
2. Update MEMORY.md - extract key learnings from this task
3. Update CLAUDE.md - add important patterns or insights discovered
4. Commit and push changes - save progress with git and push to remote

## Environment Variables

```bash
ANTHROPIC_AUTH_TOKEN    # API token (required)
ANTHROPIC_BASE_URL      # API endpoint (default: https://api.minimaxi.com/anthropic)
```

## Current Tasks

Run `python main.py list` to see pending refactoring tasks in `.agent/feature_list.json`.

## Self-Improvement Features

### Task Plan Auto-Review (Agent-Driven)

After each task completion, the system generates a **self-review task** for the Agent to:
- Read `.agent/feature_list.json` and analyze pending tasks
- Decide which tasks are obsolete (dependencies completed)
- Adjust priorities based on current system state
- Add new tasks if needed
- Merge duplicate tasks

**The Agent makes decisions, not automatic scripts.**

### MEMORY.md & CLAUDE.md Refinement (Agent-Driven)

Instead of auto-deleting content, the system provides suggestions:
- Every 5 iterations: outputs cleanup suggestions for MEMORY.md
- Every 10 iterations: outputs cleanup suggestions for CLAUDE.md

The Agent then decides whether and how to clean up - never automatic deletion.

