<p align="center">
  <img src="assets/logo.svg" alt="Agent-Loop" width="180" />
</p>

<h1 align="center">Agent-Loop</h1>

<p align="center">
  <em>Production-ready autonomous AI agent system powered by Claude Agent SDK</em>
</p>

<p align="center">
  <a href="https://www.python.org/"><img src="https://img.shields.io/badge/python-3.11+-blue.svg" alt="Python 3.11+" /></a>
  <a href="https://opensource.org/licenses/MIT"><img src="https://img.shields.io/badge/License-MIT-green.svg" alt="License: MIT" /></a>
  <a href="https://github.com/oGYCo/agent-loop/stargazers"><img src="https://img.shields.io/github/stars/oGYCo/agent-loop" alt="Stars" /></a>
</p>

<p align="center">
  <a href="#quick-start"><strong>Get Started</strong></a> ·
  <a href="#cli-reference"><strong>CLI Reference</strong></a> ·
  <a href="#docker-deployment"><strong>Docker</strong></a> ·
  <a href="#configuration"><strong>Configuration</strong></a>
</p>

---

Agent-Loop is an autonomous AI agent system that automates task execution with real-time streaming, session management, intelligent error recovery, and performance monitoring. Built on Claude Agent SDK with MiniMax API as the backend.</p>

## Why Agent-Loop?

| Benefit               | Description                                                         |
| --------------------- | ------------------------------------------------------------------- |
| **Full Transparency** | Real-time streaming of AI thinking process and tool executions      |
| **Resilient**         | Automatic session resume, file checkpointing, and graceful shutdown |
| **Extensible**        | Powerful hook system for monitoring and custom integrations         |
| **Self-Improving**    | Automatic task plan review and documentation refinement             |
| **Production-Ready**  | Type-safe, tested, well-documented, and monitored                   |

## Features

| Feature                    | Description                                                     |
| -------------------------- | --------------------------------------------------------------- |
| **Streaming Output**       | Live visibility into AI decision-making and tool calls          |
| **Session Management**     | Resume, fork, and checkpoint agent sessions                     |
| **Hook System**            | PreToolUse, PostToolUse, Notification, Stop hooks               |
| **Human-in-the-Loop**      | Automatic pause when error threshold exceeded                   |
| **Git Integration**        | Agent-driven git commit and push after each task                |
| **Task Retry**             | Configurable retry mechanism for failed tasks                   |
| **Performance Monitoring** | Track task execution time, session duration, and resource usage |
| **Config Hot Reload**      | Reload configuration without restart (manual or file watch)     |
| **Graceful Shutdown**      | Handle SIGINT/SIGTERM signals safely                            |
| **Self-Review**            | Automatic task plan review after each task completion           |
| **Customizable Prompts**   | Template-based prompt system with `{{variable}}` substitution   |
| **Email Notifications**    | Send email alerts on task completion, failure, or intervention |
| **Slack Notifications**    | Send Slack messages with Block Kit formatting                   |
| **Webhook Notifications**  | HTTP POST notifications to external services                    |
| **Structured Logging**      | JSON logging with structlog for log analysis tools              |
| **Task Board UI**          | Visual Kanban-style task board with drag-and-drop support       |
| **API Key Authentication** | Secure API access with configurable API keys                    |
| **Grafana Dashboard**      | Pre-built Grafana dashboard template for monitoring             |
| **Enhanced Error Handling**| Improved error recovery and graceful degradation                |

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
uv run python main.py init

# Run agent (default: 10 iterations)
uv run python main.py run

# Or specify iterations
uv run python main.py run --iterations 3
```

## CLI Reference

```bash
# Core commands
uv run python main.py init                          # Initialize project structure
uv run python main.py run                           # Start agent loop (default: 10 iterations)
uv run python main.py run --iterations N           # Run N iterations
uv run python main.py list                         # List all tasks
uv run python main.py status                       # Show project status
uv run python main.py add "Task Name" -d "Desc" -p 1  # Add new task

# Prompt management
uv run python main.py prompt list                  # List all prompt presets
uv run python main.py prompt show <key>            # Show prompt details
uv run python main.py prompt set <key>             # Set active prompt
uv run python main.py prompt add <key> -n "Name"   # Add new prompt preset
uv run python main.py prompt delete <key>          # Delete a prompt preset

# Template management
uv run python main.py template list                # List all templates
uv run python main.py template show <name>         # Show template content
uv run python main.py template scaffold            # Export all templates to .agent/prompt_templates/
uv run python main.py template reset <name>        # Reset template to built-in default

# Options
uv run python main.py --project-dir /path          # Specify project directory
uv run python main.py --help                       # Show help message
```

### Command Details

| Command  | Shortcut | Description                                   |
| -------- | -------- | --------------------------------------------- |
| `init`   | `--init` | Initialize project and create config files    |
| `run`    | `--run`  | Start agent loop (default: 10 iterations)     |
| `list`   |          | List all tasks with status and priority       |
| `status` |          | Show project status, git info, and task stats |
| `add`    |          | Add new task to feature list                  |
| `prompt` |          | Manage prompt presets (list/show/set/add/delete) |
| `template` |        | Manage prompt templates (list/show/scaffold/reset) |

### Add Command Options

```bash
# Add task with all options
uv run python main.py add "Add user auth" -d "Implement login/logout" -p 1 --id "feat-101"

# Add task with just name (priority defaults to 3)
uv run python main.py add "New Feature"
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

<p align="center">
  <img src="assets/logo.svg" alt="Agent-Loop" width="48" />
</p>

### Core Modules

| Module                   | Responsibility                                       |
| ------------------------ | ---------------------------------------------------- |
| `agent_core.py`          | Core agent logic, SDK integration, task execution    |
| `prompt_manager.py`      | Template engine, prompt presets, user-overridable templates |
| `session_manager.py`     | Session lifecycle, context management, history       |
| `state_manager.py`       | State persistence to JSON, config validation         |
| `task_selector.py`       | Priority-based task selection                        |
| `human_intervention.py`  | Error threshold monitoring, intervention triggers    |
| `git_helper.py`          | Git operations wrapper, status and branch management |
| `test_runner.py`         | Test execution wrapper                               |
| `performance_monitor.py` | Performance metrics tracking                         |
| `config_reloader.py`     | Configuration hot reload                             |
| `metrics.py`             | Prometheus metrics collection and export             |
| `webhook.py`             | Webhook notification service                         |
| `email_notifier.py`      | Email notification service with SMTP support         |
| `slack_notifier.py`      | Slack notification with Block Kit formatting         |
| `logging_.py`            | Structured logging with structlog (JSON/console)     |

## Usage Examples

### Basic Workflow

```bash
# 1. Initialize the project
uv run python main.py init

# 2. Check existing tasks
uv run python main.py list

# 3. Run the agent
uv run python main.py run --iterations 5

# 4. Check status
uv run python main.py status
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
uv run python main.py --project-dir /path/to/project run --iterations 3

# Check status of a specific project
uv run python main.py --project-dir /path/to/project status

# List tasks in another project
uv run python main.py --project-dir /path/to/project list
```

## Configuration

### Environment Variables

| Variable               | Description                  | Required | Default                              |
| ---------------------- | ---------------------------- | -------- | ------------------------------------ |
| `ANTHROPIC_AUTH_TOKEN` | API token for authentication | Yes      | -                                    |
| `ANTHROPIC_BASE_URL`   | API endpoint URL             | No       | `https://api.minimaxi.com/anthropic` |

### config.json

```json
{
  "project_name": "my-project",
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
  "session_type": "coder",
  "context_files": ["README.md", "CLAUDE.md"],
  "verify_command": "uv run pytest tests/ -x -q",
  "allowed_tools": ["Read", "Write", "Edit", "Bash", "Glob", "Grep", "MultiEdit"],
  "mcp_servers": []
}
```

### Configuration Options

| Option                           | Type     | Description                                 |
| -------------------------------- | -------- | ------------------------------------------- |
| `project_name`                   | string   | Project name used in prompt templates       |
| `max_errors_before_intervention` | int      | Errors before triggering human intervention |
| `retry.max_retries`              | int      | Maximum retry attempts for failed tasks     |
| `retry.retry_interval`           | int      | Seconds between retry attempts              |
| `context_window_limit`           | int      | Token limit for context window              |
| `model`                          | string   | Model name to use                           |
| `context_files`                  | string[] | Files to include in system prompt context   |
| `verify_command`                 | string   | Command to verify task completion           |
| `allowed_tools`                  | string[] | SDK tools the agent is allowed to use       |
| `mcp_servers`                    | object[] | MCP server configurations                   |

### Email Configuration

```json
{
  "email": {
    "enabled": true,
    "smtp_host": "smtp.gmail.com",
    "smtp_port": 587,
    "smtp_user": "your-email@gmail.com",
    "smtp_password": "your-app-password",
    "use_tls": true,
    "from_name": "Agent-Loop",
    "from_email": "agent-loop@example.com",
    "to_emails": ["admin@example.com", "team@example.com"],
    "events": ["task_completed", "task_failed", "human_intervention"],
    "timeout": 30
  }
}
```

### Webhook Configuration

```json
{
  "webhook": {
    "enabled": true,
    "url": "https://your-server.com/webhook",
    "secret": "your-webhook-secret",
    "timeout": 10,
    "events": ["task_completed", "task_failed", "human_intervention"],
    "retry_count": 3,
    "retry_interval": 2
  }
}
```

### API Key Configuration

```json
{
  "api_keys": {
    "enabled": true,
    "keys": ["your-api-key-1", "your-api-key-2"]
  }
}
```

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

## Prompt Customization

Agent-Loop uses a template-based prompt system. All prompts support `{{variable}}` substitution and can be fully customized.

### Template Resolution Order

1. **User override**: `.agent/prompt_templates/<name>.md` (highest priority)
2. **Built-in default**: Embedded in source code (fallback)

### Available Templates

| Template            | Description                                    |
| ------------------- | ---------------------------------------------- |
| `system`            | Main system prompt (identity, tools, workflow) |
| `task`              | Task execution prompt with project context     |
| `self_review`       | Post-task plan review prompt                   |
| `memory_cleanup`    | MEMORY.md cleanup suggestions prompt           |
| `claude_md_cleanup` | CLAUDE.md cleanup suggestions prompt           |

### System Prompt Variants

| Variant      | Description                                        |
| ------------ | -------------------------------------------------- |
| `default`    | General-purpose autonomous agent                   |
| `coder`      | Software development focused                       |
| `researcher` | Research and documentation focused                 |
| `reviewer`   | Code review and quality assurance focused          |

Set the variant via `session_type` in config.json.

### Customizing Templates

```bash
# Export all templates to .agent/prompt_templates/
uv run python main.py template scaffold

# Edit any template file, e.g.:
# .agent/prompt_templates/system.md
# .agent/prompt_templates/task.md

# Available variables in templates:
# {{project_name}}       - From config.json
# {{project_structure}}  - Auto-scanned project tree
# {{task_name}}          - Current task name
# {{task_description}}   - Current task description
# {{context_files_list}} - Files listed in config context_files
# {{current_date}}       - Today's date
# {{feature_list_path}}  - Path to feature_list.json

# Reset a template to built-in default
uv run python main.py template reset system
```

## Testing

```bash
# Run all tests
uv run pytest tests/ -v

# Run specific module
uv run pytest tests/test_agent_core.py -v

# With coverage
uv run pytest tests/ --cov=agent --cov-report=term-missing

# Quick test (fail-fast)
uv run pytest tests/ -x -q
```

## Project Structure

```
agent-loop/
├── agent/                      # Core package
│   ├── __init__.py
│   ├── agent_core.py           # Core agent logic
│   ├── prompt_manager.py       # Template engine & prompt management
│   ├── session_manager.py      # Session management
│   ├── state_manager.py        # State persistence
│   ├── task_selector.py        # Task selection
│   ├── human_intervention.py   # Human intervention
│   ├── git_helper.py           # Git operations
│   ├── test_runner.py          # Test execution
│   ├── performance_monitor.py  # Performance tracking
│   ├── config_reloader.py      # Config hot reload
│   ├── email_notifier.py       # Email notification service
│   ├── webhook.py              # Webhook notification service
│   ├── metrics.py              # Metrics collection
│   └── console.py              # Console UI
├── tests/                      # Unit tests
│   ├── test_agent_core.py
│   ├── test_state_manager.py
│   ├── test_task_selector.py
│   ├── test_email_notifier.py
│   ├── test_webhook.py
│   └── ...
├── dashboards/                  # Grafana dashboard templates
│   └── agent-loop-dashboard.json
├── static/                     # Web dashboard static files
│   └── index.html
├── api.py                      # REST API server
├── main.py                     # CLI entry point
├── pyproject.toml              # Project config (uv)
├── README.md                   # English documentation
├── README.zh-CN.md            # Chinese documentation
└── .agent/                    # Configuration directory
    ├── config.json             # Project configuration
    ├── feature_list.json       # Task list
    ├── prompts.json            # Prompt presets
    ├── state.json              # Current state
    ├── session_history.json    # Session history
    ├── MEMORY.md               # Accumulated experience
    └── prompt_templates/       # User-customizable prompt templates
        ├── system.md
        ├── task.md
        └── ...
```

## Documentation Links

- [Claude Agent SDK](https://platform.claude.com/docs/en/agent-sdk/overview)
- [Python SDK Reference](https://platform.claude.com/docs/en/agent-sdk/python)
- [Hooks Guide](https://platform.claude.com/docs/en/agent-sdk/hooks)
- [Streaming Output](https://platform.claude.com/docs/en/agent-sdk/streaming-output)
- [Session Management](https://platform.claude.com/docs/en/agent-sdk/sessions)
- [MCP Protocol](https://modelcontextprotocol.io/introduction)

## Docker Deployment

Agent-Loop can be deployed using Docker and Docker Compose for a complete containerized environment with monitoring.

### Prerequisites

- Docker 20.10+
- Docker Compose 2.0+
- At least 2GB RAM available

### Quick Start

```bash
# 1. Clone the repository
git clone https://github.com/your-repo/agent-loop.git
cd agent-loop

# 2. Copy environment template
cp .env.example .env

# 3. Edit .env with your API credentials
nano .env

# 4. Build and start all services
docker-compose up -d

# 5. Check service status
docker-compose ps

# 6. View logs
docker-compose logs -f
```

### Services

The Docker Compose stack includes:

| Service     | Port | Description                          |
| ----------- | ---- | ------------------------------------ |
| `agent-loop` | -    | Main Agent CLI (runs agent loop)     |
| `agent-api`  | 8000 | FastAPI server with web dashboard    |
| `prometheus` | 9090 | Metrics collection and monitoring    |
| `grafana`    | 3000 | Visualization dashboard              |

### Configuration

Edit the `.env` file to configure:

```bash
# Required: API Authentication
ANTHROPIC_AUTH_TOKEN=your-api-token-here
ANTHROPIC_BASE_URL=https://api.minimaxi.com/anthropic

# Optional: Logging
LOG_LEVEL=INFO
LOG_FILE=/app/logs/agent.log

# Optional: Grafana
GRAFANA_USER=admin
GRAFANA_PASSWORD=admin
```

### Accessing Services

- **API Dashboard**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **Prometheus**: http://localhost:9090
- **Grafana**: http://localhost:3000 (admin/admin)

### Common Commands

```bash
# Start all services
docker-compose up -d

# Stop all services
docker-compose down

# Rebuild images
docker-compose build --no-cache

# View logs for specific service
docker-compose logs -f agent-api

# View logs for all services
docker-compose logs -f

# Restart a specific service
docker-compose restart agent-api

# Scale agent-loop (run multiple instances)
docker-compose up -d --scale agent-loop=2
```

### Data Persistence

The `.agent/` directory is persisted using Docker volumes:

- `agent-data` volume stores task lists, configuration, and session history
- Logs are stored in `./logs` directory on host

### Health Checks

- **agent-api**: HTTP GET `http://localhost:8000/health`
- **prometheus**: Scrapes `/metrics` endpoint every 10 seconds
- **grafana**: Pre-configured with Agent-Loop dashboard

### Customization

#### Custom Grafana Dashboard

1. Log into Grafana (http://localhost:3000)
2. Import `dashboards/agent-loop-dashboard.json`
3. Configure data source to Prometheus (`http://prometheus:9090`)

#### Running Only the API Server

```bash
docker build -t agent-loop .
docker run -p 8000:8000 --env-file .env agent-loop
```

### Troubleshooting

```bash
# Check container health
docker inspect agent-api | grep -A 20 Health

# View container logs
docker-compose logs agent-api

# Access container shell
docker exec -it agent-api /bin/bash

# Check disk usage
docker system df

# Clean up unused images
docker image prune -f
```

### Security Notes

- The container runs as a non-root user (`agent`)
- Secrets are loaded from `.env` file
- No credentials are baked into the image
- Use Docker secrets in production deployments

---

<p align="center">
  <img src="assets/logo.svg" alt="Agent-Loop" width="64" />
</p>

<p align="center">
  <strong>Agent-Loop</strong> · Built with Claude Agent SDK
</p>

<p align="center">
  <a href="https://github.com/oGYCo/agent-loop">GitHub</a> ·
  <a href="https://github.com/oGYCo/agent-loop/issues">Issues</a> ·
  <a href="https://github.com/oGYCo/agent-loop/blob/main/LICENSE">License</a>
</p>
