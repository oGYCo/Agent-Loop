# Agent-Loop

> A production-ready autonomous AI agent system powered by Claude Agent SDK

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)

Agent-Loop is an autonomous AI agent system that automates task execution with real-time visibility, session management, and intelligent error recovery. Built on Claude Agent SDK with MiniMax API backend.

## Why Agent-Loop?

- **Full Transparency**: Real-time streaming of AI thinking process and tool executions
- **Resilient**: Automatic session resume and file checkpointing for failure recovery
- **Extensible**: Powerful hook system for monitoring and custom integrations
- **Production-Ready**: Type-safe, tested, and well-documented

## Features

| Feature | Description |
|---------|-------------|
| **Streaming Output** | Live visibility into AI decision-making and tool calls |
| **Session Management** | Resume, fork, and checkpoint agent sessions |
| **Hook System** | PreToolUse, PostToolUse, Notification, Stop hooks |
| **Human-in-the-Loop** | Automatic pause when error threshold exceeded |
| **Git Integration** | Auto-commit after each session for version control |
| **MCP Support** | Built-in Playwright browser automation |

## Quick Start

### 1. Install

```bash
# Clone the repository
git clone https://github.com/your-repo/agent-loop.git
cd agent-loop

# Install dependencies with uv
uv sync
```

### 2. Configure

```bash
export ANTHROPIC_AUTH_TOKEN="your-api-token"
export ANTHROPIC_BASE_URL="https://api.minimaxi.com/anthropic"
```

### 3. Run

```bash
# Initialize project
python main.py init

# Run agent (default: 10 iterations)
python main.py run

# Or specify iterations
python main.py run --iterations 3
```

## CLI Reference

```bash
python main.py init                    # Initialize project structure
python main.py run                     # Start agent loop (default: 10 iterations)
python main.py run --iterations N      # Run N iterations
python main.py list                    # List all tasks
python main.py add --name "Task" --description "Desc" --priority 1  # Add new task
python main.py status                  # Show project status
python main.py --project-dir /path    # Specify project directory
```

### Command Options

| Command | Options | Description |
|---------|---------|-------------|
| `init` | | Initialize project and create config files |
| `run` | `--iterations N` | Run agent for N iterations (default: 10) |
| `list` | | List all tasks with status |
| `add` | `--name`, `--description`, `--priority`, `--id` | Add new task to feature list |
| `status` | | Show project status, git info, and task stats |

### Backwards Compatibility

```bash
python main.py --init    # Equivalent to: python main.py init
python main.py --run     # Equivalent to: python main.py run
```

## Usage Examples

### Basic Workflow

```bash
# 1. Initialize the project (creates .agent/ directory with configs)
python main.py init

# 2. Check existing tasks
python main.py list

# 3. Run the agent
python main.py run --iterations 5

# 4. Check status
python main.py status
```

### Adding New Tasks

```bash
# Add a new feature with priority (lower = higher priority)
python main.py add --name "Add user authentication" --description "Implement login/logout" --priority 1

# Add with custom ID
python main.py add --id "feat-101" --name "New Feature" --priority 2
```

### Project Configuration

Tasks are managed in `.agent/feature_list.json`:

```json
{
  "features": [
    {
      "id": "self-001",
      "name": "Task Name",
      "description": "Task description",
      "priority": 1,
      "status": "pending",
      "passes": false,
      "verify_command": "pytest tests/",
      "context_files": ["file1.py", "file2.py"],
      "created_at": "2026-03-07",
      "updated_at": "2026-03-07"
    }
  ]
}
```

Task selection criteria:
- `status` must be `"pending"`
- `passes` must be `false`
- Tasks are selected by priority (lower number = higher priority)

### Custom Project Directory

```bash
# Run agent on a different project
python main.py --project-dir /path/to/project run --iterations 3

# Check status of a specific project
python main.py --project-dir /path/to/project status
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        main.py                               │
│                      CLI Entry Point                         │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                     AgentCore                                │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────────┐   │
│  │ TaskSelector │ │StateManager  │ │  GitHelper       │   │
│  └──────────────┘ └──────────────┘ └──────────────────┘   │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                 ClaudeSDKClient                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Streaming │ Hooks │ Sessions │ File Checkpointing  │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### Core Modules

| Module | Responsibility |
|--------|----------------|
| `agent_core.py` | Agent logic, SDK integration, task execution |
| `session_manager.py` | Session lifecycle, context management |
| `state_manager.py` | State persistence to JSON |
| `task_selector.py` | Priority-based task selection |
| `human_intervention.py` | Error threshold monitoring |
| `git_helper.py` | Git operations wrapper |
| `test_runner.py` | Test execution wrapper |

## SDK Usage Example

```python
from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions
from claude_agent_sdk.types import StreamEvent, ResultMessage

# Configure with streaming and hooks
options = ClaudeAgentOptions(
    model="MiniMax-M2.5-highspeed",
    system_prompt="You are a helpful coding assistant.",
    env={
        "ANTHROPIC_AUTH_TOKEN": "your-token",
        "ANTHROPIC_BASE_URL": "https://api.minimaxi.com/anthropic",
    },
    allowed_tools=["Read", "Write", "Bash", "Glob", "Grep"],
    include_partial_messages=True,
    permission_mode="acceptEdits",
)

# Execute with streaming
async with ClaudeSDKClient(options=options) as client:
    await client.query("Write a hello world program")
    async for message in client.receive_response():
        if isinstance(message, StreamEvent):
            # Handle streaming events
            pass
        elif isinstance(message, ResultMessage):
            print(f"Session: {message.session_id}")
```

## Task Management

Tasks are defined in `.agent/feature_list.json`:

```json
{
  "features": [
    {
      "id": "feat-001",
      "name": "Feature Name",
      "description": "Feature description",
      "priority": 1,
      "status": "pending",
      "passes": false
    }
  ]
}
```

- Lower `priority` = higher priority
- Only `status=pending` and `passes=false` tasks are selected

## Testing

```bash
# All tests
pytest tests/ -v

# Specific module
pytest tests/test_agent_core.py -v

# With coverage
pytest tests/ --cov=. --cov-report=term-missing
```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `ANTHROPIC_AUTH_TOKEN` | API token | Required |
| `ANTHROPIC_BASE_URL` | API endpoint | `https://api.minimaxi.com/anthropic` |

### config.json

```json
{
  "project_name": "agent-loop",
  "model": "MiniMax-M2.5-highspeed",
  "max_errors_before_intervention": 3,
  "test_command": "pytest"
}
```

## Documentation

- [Claude Agent SDK](https://platform.claude.com/docs/en/agent-sdk/overview)
- [Python SDK Reference](https://platform.claude.com/docs/en/agent-sdk/python)
- [Hooks Guide](https://platform.claude.com/docs/en/agent-sdk/hooks)
- [Streaming Output](https://platform.claude.com/docs/en/agent-sdk/streaming-output)
- [Session Management](https://platform.claude.com/docs/en/agent-sdk/sessions)
- [MCP Protocol](https://modelcontextprotocol.io/introduction)

## Project Structure

```
agent-loop/
├── agent/                  # Core package
│   ├── __init__.py
│   ├── agent_core.py       # Core agent logic
│   ├── session_manager.py  # Session management
│   ├── state_manager.py    # State persistence
│   ├── task_selector.py    # Task selection
│   ├── human_intervention.py
│   ├── git_helper.py       # Git operations
│   └── test_runner.py      # Test execution
├── tests/                  # Unit tests
├── main.py                 # CLI entry
├── pyproject.toml         # Project config (uv)
├── README.md               # English documentation
├── README.zh-CN.md         # Chinese documentation
└── .agent/                 # Configuration directory
```

## License

MIT License - see [LICENSE](LICENSE) for details.
