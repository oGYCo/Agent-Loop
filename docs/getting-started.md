# Getting Started with Agent-Loop

This guide will help you get Agent-Loop up and running in 5 minutes.

## Prerequisites

- Python 3.11 or higher
- uv (package manager)
- API credentials for Claude Agent SDK (MiniMax API)

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/oGYCo/agent-loop.git
cd agent-loop
```

### 2. Install Dependencies

```bash
# Install using uv (recommended)
uv sync

# Or with pip
pip install -e .
```

### 3. Configure API Credentials

Create a `.env` file in the project root:

```bash
# Required: API Authentication
ANTHROPIC_AUTH_TOKEN=your-api-token-here
ANTHROPIC_BASE_URL=https://api.minimaxi.com/anthropic

# Optional: Logging Configuration
LOG_LEVEL=INFO
LOG_FILE=./logs/agent.log
```

Or export as environment variables:

```bash
export ANTHROPIC_AUTH_TOKEN="your-api-token"
export ANTHROPIC_BASE_URL="https://api.minimaxi.com/anthropic"
```

### 4. Initialize the Project

```bash
uv run python main.py init
```

This creates the `.agent/` directory with default configuration files.

## Quick Start

### Run Your First Agent Loop

```bash
# Run with default settings (10 iterations)
uv run python main.py run

# Or specify the number of iterations
uv run python main.py run --iterations 3
```

### Check Project Status

```bash
uv run python main.py status
```

### List All Tasks

```bash
uv run python main.py list
```

## Adding Tasks

### Via CLI

```bash
uv run python main.py add "Implement user auth" -d "Add login/logout functionality" -p 1
```

### Via JSON File

Edit `.agent/feature_list.json`:

```json
{
  "features": [
    {
      "id": "feat-001",
      "name": "My New Task",
      "description": "Task description here",
      "priority": 1,
      "status": "pending",
      "passes": false,
      "created_at": "2026-03-08",
      "updated_at": "2026-03-08"
    }
  ]
}
```

## Starting the API Server

For programmatic access or the web dashboard:

```bash
# Start API server (default port: 8000)
uv run python api.py

# Start on custom port
uv run python api.py --port 8080
```

Then open:
- **Dashboard**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## Next Steps

- [Configuration Guide](configuration.md) - Customize Agent-Loop behavior
- [API Reference](api-reference.md) - Complete REST API documentation
- [Notification Setup](notification-setup.md) - Configure email/Slack/webhook notifications
- [Deployment Guide](deployment.md) - Production deployment with Docker
- [Architecture Overview](architecture.md) - Understand the system design

## Common Commands Reference

```bash
# Initialize project
uv run python main.py init

# Run agent
uv run python main.py run
uv run python main.py run --iterations 5

# Task management
uv run python main.py list
uv run python main.py add "Task name" -d "Description" -p 1
uv run python main.py status

# Prompt management
uv run python main.py prompt list
uv run python main.py prompt set default

# Template management
uv run python main.py template scaffold
uv run python main.py template reset system

# API server
uv run python api.py
```

## Troubleshooting

See [Troubleshooting Guide](troubleshooting.md) for common issues and solutions.
