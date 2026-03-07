<p align="center">
  <img src="assets/logo.svg" alt="Agent-Loop" width="280" />
</p>

<h1 align="center">Agent-Loop</h1>

<p align="center">
  <em>A production-ready autonomous AI agent system powered by Claude Agent SDK with MiniMax API backend</em>
</p>

<p align="center">
  <a href="https://www.python.org/"><img src="https://img.shields.io/badge/python-3.11+-blue.svg" alt="Python 3.11+" /></a>
  <a href="https://opensource.org/licenses/MIT"><img src="https://img.shields.io/badge/License-MIT-green.svg" alt="License: MIT" /></a>
  <a href="https://pypi.org/project/claude-agent-sdk/"><img src="https://img.shields.io/pypi/v/claude-agent-sdk?color=purple" alt="PyPI" /></a>
  <a href="https://github.com/agent-loop/agent-loop/actions/workflows/test.yml"><img src="https://img.shields.io/github/actions/workflow/status/agent-loop/agent-loop/test.yml?branch=main" alt="Tests" /></a>
  <a href="https://github.com/agent-loop/agent-loop/stargazers"><img src="https://img.shields.io/github/stars/agent-loop/agent-loop" alt="Stars" /></a>
  <a href="https://github.com/agent-loop/agent-loop/fork"><img src="https://img.shields.io/github/forks/agent-loop/agent-loop" alt="Forks" /></a>
</p>

<p align="center">
  <a href="https://agent-loop.dev"><strong>Documentation</strong></a> ·
  <a href="#quick-start"><strong>Get Started</strong></a> ·
  <a href="#cli-reference"><strong>CLI Reference</strong></a> ·
  <a href="#configuration"><strong>Configuration</strong></a>
</p>

---

Agent-Loop is an autonomous AI agent system that automates task execution with real-time streaming, session management, intelligent error recovery, and performance monitoring. Built on Claude Agent SDK with MiniMax API as the backend.</p>

## Why Agent-Loop?

| Benefit | Description |
|---------|-------------|
| **Full Transparency** | Real-time streaming of AI thinking process and tool executions |
| **Resilient** | Automatic session resume, file checkpointing, and graceful shutdown |
| **Extensible** | Powerful hook system for monitoring and custom integrations |
| **Self-Improving** | Automatic task plan review and documentation refinement |
| **Production-Ready** | Type-safe, tested, well-documented, and monitored |

## Features

| Feature | Description |
|---------|-------------|
| **Streaming Output** | Live visibility into AI decision-making and tool calls |
| **Session Management** | Resume, fork, and checkpoint agent sessions |
| **Hook System** | PreToolUse, PostToolUse, Notification, Stop hooks |
| **Human-in-the-Loop** | Automatic pause when error threshold exceeded |
| **Git Integration** | Auto-commit after each session for version control |
| **Task Retry** | Configurable retry mechanism for failed tasks |
| **Performance Monitoring** | Track task execution time, session duration, and resource usage |
| **Config Hot Reload** | Reload configuration without restart (manual or file watch) |
| **Graceful Shutdown** | Handle SIGINT/SIGTERM signals safely |
| **Self-Review** | Automatic task plan review after each task completion |

## Quick Start

### 1. Clone and Install

```bash
# Clone the repository
git clone https://github.com/your-repo/agent-loop.git
cd agent-loop

# Install dependencies with uv
uv sync
```

### 2. Configure

Create a `.env` file or set environment variables:

```bash
export ANTHROPIC_AUTH_TOKEN="your-api-token"
export ANTHROPIC_BASE_URL="https://api.minimaxi.com/anthropic"
```

### 3. Run

```bash
# Initialize project (creates .agent/ directory)
python main.py init

# Run agent (default: 10 iterations)
python main.py run

# Or specify iterations
python main.py run --iterations 3
```

## CLI Reference

```bash
# Core commands
python main.py init                          # Initialize project structure
python main.py run                           # Start agent loop (default: 10 iterations)
python main.py run --iterations N           # Run N iterations
python main.py list                         # List all tasks
python main.py status                       # Show project status
python main.py add "Task Name" -d "Desc" -p 1  # Add new task

# Options
python main.py --project-dir /path          # Specify project directory
python main.py --help                       # Show help message
```

### Command Details

| Command | Shortcut | Description |
|---------|----------|-------------|
| `init` | `--init` | Initialize project and create config files |
| `run` | `--run` | Start agent loop (default: 10 iterations) |
| `list` | | List all tasks with status and priority |
| `status` | | Show project status, git info, and task stats |
| `add` | | Add new task to feature list |

### Add Command Options

```bash
# Add task with all options
python main.py add "Add user auth" -d "Implement login/logout" -p 1 --id "feat-101"

# Add task with just name (priority defaults to 3)
python main.py add "New Feature"
```

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         main.py                                  │
│                      CLI Entry Point                             │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  Signal Handling │ Argument Parsing │ Command Dispatch   │   │
│  └─────────────────────────────────────────────────────────┘   │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                       AgentCore                                  │
│  ┌──────────────┐ ┌──────────────┐ ┌────────────────────────┐  │
│  │TaskSelector │ │StateManager  │ │ PerformanceMonitor     │  │
│  ├──────────────┤ ├──────────────┤ ├────────────────────────┤  │
│  │SessionManager│ │  GitHelper   │ │  ConfigReloader       │  │
│  ├──────────────┤ ├──────────────┤ ├────────────────────────┤  │
│  │HumanInterven│ │AgentTestRunner│ │ ClaudeSDKClient      │  │
│  └──────────────┘ └──────────────┘ └────────────────────────┘  │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                   ClaudeSDKClient                                │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Streaming │ Hooks │ Sessions │ File Checkpointing      │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### Core Modules

| Module | Responsibility |
|--------|----------------|
| `agent_core.py` | Core agent logic, SDK integration, task execution |
| `session_manager.py` | Session lifecycle, context management, history |
| `state_manager.py` | State persistence to JSON, config validation |
| `task_selector.py` | Priority-based task selection |
| `human_intervention.py` | Error threshold monitoring, intervention triggers |
| `git_helper.py` | Git operations wrapper, auto-commit |
| `test_runner.py` | Test execution wrapper |
| `performance_monitor.py` | Performance metrics tracking |
| `config_reloader.py` | Configuration hot reload |

## Usage Examples

### Basic Workflow

```bash
# 1. Initialize the project
python main.py init

# 2. Check existing tasks
python main.py list

# 3. Run the agent
python main.py run --iterations 5

# 4. Check status
python main.py status
```

### Task Management

Tasks are managed in `.agent/feature_list.json`:

```json
{
  "features": [
    {
      "id": "self-001",
      "name": "Read project docs",
      "description": "Read CLAUDE.md and README.md to understand project",
      "priority": 1,
      "status": "pending",
      "passes": false,
      "verify_command": "cat CLAUDE.md | head -20",
      "context_files": ["CLAUDE.md", "README.md"],
      "created_at": "2026-03-07",
      "updated_at": "2026-03-07"
    }
  ]
}
```

**Task Selection Criteria:**
- `status` must be `"pending"`
- `passes` must be `false`
- Tasks are selected by priority (lower number = higher priority)

### Custom Project Directory

```bash
# Run agent on a different project
python main.py --project-dir /path/to/project run --iterations 3

# Check status of a specific project
python main.py --project-dir /path/to/project status

# List tasks in another project
python main.py --project-dir /path/to/project list
```

## Configuration

### Environment Variables

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `ANTHROPIC_AUTH_TOKEN` | API token for authentication | Yes | - |
| `ANTHROPIC_BASE_URL` | API endpoint URL | No | `https://api.minimaxi.com/anthropic` |

### config.json

```json
{
  "project_name": "agent-loop",
  "project_type": "generic",
  "test_command": "pytest",
  "test_pattern": "test_*.py",
  "max_errors_before_intervention": 3,
  "retry": {
    "max_retries": 3,
    "retry_interval": 5,
    "retry_on_errors": ["connection_error", "timeout", "process_error"]
  },
  "context_window_limit": 100000,
  "model": "MiniMax-M2.5-highspeed",
  "session_type": "coder"
}
```

### Configuration Options

| Option | Type | Description |
|--------|------|-------------|
| `max_errors_before_intervention` | int | Errors before triggering human intervention |
| `retry.max_retries` | int | Maximum retry attempts for failed tasks |
| `retry.retry_interval` | int | Seconds between retry attempts |
| `context_window_limit` | int | Token limit for context window |
| `model` | string | Model name to use |

## SDK Usage

```python
from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions
from claude_agent_sdk.types import StreamEvent, ResultMessage

# Configure with streaming and hooks
options = ClaudeAgentOptions(
    model="MiniMax-M2.5-highspeed",
    system_prompt="You are a helpful coding assistant.",
    env={
        "ANTHROPIC_AUTH_TOKEN": os.environ["ANTHROPIC_AUTH_TOKEN"],
        "ANTHROPIC_BASE_URL": "https://api.minimaxi.com/anthropic",
    },
    allowed_tools=["Read", "Write", "Bash", "Glob", "Grep"],
    include_partial_messages=True,
    permission_mode="acceptEdits",
    enable_file_checkpointing=True,
)

# Execute with streaming
async with ClaudeSDKClient(options=options) as client:
    await client.query("Write a hello world program")
    async for message in client.receive_response():
        if isinstance(message, StreamEvent):
            print(f"Event: {message.type}")
        elif isinstance(message, ResultMessage):
            print(f"Completed: {message.session_id}")
```

## Testing

```bash
# Run all tests
pytest tests/ -v

# Run specific module
pytest tests/test_agent_core.py -v

# With coverage
pytest tests/ --cov=agent --cov-report=term-missing

# Quick test (fail-fast)
pytest tests/ -x -q
```

## Project Structure

```
agent-loop/
├── agent/                      # Core package
│   ├── __init__.py
│   ├── agent_core.py           # Core agent logic
│   ├── session_manager.py      # Session management
│   ├── state_manager.py        # State persistence
│   ├── task_selector.py        # Task selection
│   ├── human_intervention.py   # Human intervention
│   ├── git_helper.py           # Git operations
│   ├── test_runner.py          # Test execution
│   ├── performance_monitor.py  # Performance tracking
│   └── config_reloader.py      # Config hot reload
├── tests/                      # Unit tests
│   ├── test_agent_core.py
│   ├── test_state_manager.py
│   ├── test_task_selector.py
│   └── ...
├── main.py                     # CLI entry point
├── pyproject.toml              # Project config (uv)
├── README.md                   # English documentation
├── README.zh-CN.md            # Chinese documentation
└── .agent/                    # Configuration directory
    ├── config.json             # Project configuration
    ├── feature_list.json       # Task list
    ├── state.json              # Current state
    ├── session_history.json    # Session history
    └── MEMORY.md              # Accumulated experience
```

## Documentation Links

- [Claude Agent SDK](https://platform.claude.com/docs/en/agent-sdk/overview)
- [Python SDK Reference](https://platform.claude.com/docs/en/agent-sdk/python)
- [Hooks Guide](https://platform.claude.com/docs/en/agent-sdk/hooks)
- [Streaming Output](https://platform.claude.com/docs/en/agent-sdk/streaming-output)
- [Session Management](https://platform.claude.com/docs/en/agent-sdk/sessions)
- [MCP Protocol](https://modelcontextprotocol.io/introduction)

## License

MIT License - see [LICENSE](LICENSE) for details.
