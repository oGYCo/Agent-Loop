# Configuration Reference

Complete reference for all configuration options in Agent-Loop.

## Configuration File Location

The main configuration file is located at `.agent/config.json`. It is created automatically when you run `uv run python main.py init`.

## Environment Variables

| Variable | Description | Required | Default |
| -------- | ----------- | -------- | -------- |
| `ANTHROPIC_AUTH_TOKEN` | API token for authentication | Yes | - |
| `ANTHROPIC_BASE_URL` | API endpoint URL | No | `https://api.minimaxi.com/anthropic` |
| `LOG_LEVEL` | Logging level (DEBUG, INFO, WARNING, ERROR) | No | `INFO` |
| `LOG_FILE` | Path to log file | No | - |
| `PROJECT_DIR` | Custom project directory | No | Current directory |

## config.json Structure

### Core Settings

```json
{
  "project_name": "my-project",
  "project_type": "python",
  "model": "MiniMax-M2.5-highspeed",
  "session_type": "coder",
  "active_provider": "default",
  "context_window_limit": 100000,
  "verify_command": "pytest tests/ -x -q",
  "test_command": "pytest tests/ -v",
  "test_pattern": "test_*.py",
  "max_errors_before_intervention": 3,
  "context_files": ["README.md", "CLAUDE.md"],
  "allowed_tools": ["Read", "Write", "Edit", "Bash", "Glob", "Grep", "MultiEdit"],
  "mcp_servers": []
}
```

### Configuration Options

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `project_name` | string | No | - | Project name used in prompts |
| `project_type` | string | No | `generic` | Project type (python, node, generic) |
| `model` | string | No | `MiniMax-M2.5-highspeed` | Model to use |
| `session_type` | string | No | `coder` | Session type (default, coder, researcher, reviewer) |
| `active_provider` | string | No | `default` | Active API provider |
| `context_window_limit` | int | No | 100000 | Maximum token limit for context |
| `verify_command` | string | No | - | Command to verify task completion |
| `test_command` | string | No | - | Command to run tests |
| `test_pattern` | string | No | `test_*.py` | Pattern to match test files |
| `max_errors_before_intervention` | int | No | 3 | Errors before human intervention |
| `context_files` | string[] | No | [] | Files to include in system prompt |
| `allowed_tools` | string[] | No | [] | SDK tools the agent can use |
| `mcp_servers` | object[] | No | [] | MCP server configurations |

### Providers Configuration

```json
{
  "providers": {
    "default": {
      "provider": "minimax",
      "model": "MiniMax-M2.5-highspeed",
      "api_key_env": "ANTHROPIC_AUTH_TOKEN",
      "base_url_env": "ANTHROPIC_BASE_URL"
    }
  }
}
```

| Option | Type | Description |
|--------|------|-------------|
| `provider` | string | Provider name (minimax, anthropic) |
| `model` | string | Model identifier |
| `api_key_env` | string | Environment variable for API key |
| `base_url_env` | string | Environment variable for base URL |

### Retry Configuration

```json
{
  "retry": {
    "max_retries": 3,
    "retry_interval": 5,
    "retry_on_errors": ["connection_error", "timeout", "process_error"]
  }
}
```

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `max_retries` | int | 3 | Maximum retry attempts |
| `retry_interval` | int | 5 | Seconds between retries |
| `retry_on_errors` | string[] | - | Error types to retry on |

### Email Notification Configuration

```json
{
  "email": {
    "enabled": false,
    "smtp_host": "smtp.gmail.com",
    "smtp_port": 587,
    "smtp_user": "your-email@gmail.com",
    "smtp_password": "your-app-password",
    "use_tls": true,
    "from_name": "Agent-Loop",
    "from_email": "agent-loop@example.com",
    "to_emails": ["admin@example.com"],
    "events": ["task_completed", "task_failed", "human_intervention"],
    "timeout": 30
  }
}
```

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `enabled` | boolean | false | Enable email notifications |
| `smtp_host` | string | - | SMTP server hostname |
| `smtp_port` | int | 587 | SMTP server port |
| `smtp_user` | string | - | SMTP username |
| `smtp_password` | string | - | SMTP password / app password |
| `use_tls` | boolean | true | Use TLS encryption |
| `from_name` | string | - | Sender display name |
| `from_email` | string | - | Sender email address |
| `to_emails` | string[] | - | Recipient email addresses |
| `events` | string[] | - | Events to notify on |
| `timeout` | int | 30 | Connection timeout in seconds |

### Slack Notification Configuration

```json
{
  "slack": {
    "enabled": false,
    "webhook_url": "",
    "channel": "#agent-loop",
    "username": "Agent-Loop",
    "icon_emoji": ":robot_face:",
    "events": ["task_completed", "task_failed", "human_intervention"],
    "timeout": 10,
    "retry_count": 3,
    "retry_interval": 2
  }
}
```

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `enabled` | boolean | false | Enable Slack notifications |
| `webhook_url` | string | - | Slack webhook URL |
| `channel` | string | - | Slack channel (overrides webhook default) |
| `username` | string | - | Bot username |
| `icon_emoji` | string | - | Bot icon emoji |
| `events` | string[] | - | Events to notify on |
| `timeout` | int | 10 | Request timeout in seconds |
| `retry_count` | int | 3 | Number of retry attempts |
| `retry_interval` | int | 2 | Seconds between retries |

### Webhook Configuration

```json
{
  "webhook": {
    "enabled": false,
    "url": "https://your-server.com/webhook",
    "secret": "your-webhook-secret",
    "timeout": 10,
    "events": ["task_completed", "task_failed", "human_intervention"],
    "retry_count": 3,
    "retry_interval": 2
  }
}
```

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `enabled` | boolean | false | Enable webhook notifications |
| `url` | string | - | Webhook endpoint URL |
| `secret` | string | - | Webhook secret for signing |
| `timeout` | int | 10 | Request timeout in seconds |
| `events` | string[] | - | Events to notify on |
| `retry_count` | int | 3 | Number of retry attempts |
| `retry_interval` | int | 2 | Seconds between retries |

### API Key Configuration

```json
{
  "api_keys": {
    "enabled": false,
    "keys": ["your-api-key-1", "your-api-key-2"]
  }
}
```

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `enabled` | boolean | false | Enable API key authentication |
| `keys` | string[] | - | List of valid API keys |

### Rate Limiting Configuration

```json
{
  "rate_limit": {
    "enabled": true,
    "default_limit": "100/minute",
    "endpoints": {
      "/run": "10/minute",
      "/tasks": "30/minute"
    }
  }
}
```

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `enabled` | boolean | true | Enable rate limiting |
| `default_limit` | string | - | Default rate limit |
| `endpoints` | object | - | Endpoint-specific limits |

### CORS Configuration

```json
{
  "cors": {
    "enabled": true,
    "allow_origins": [],
    "allow_credentials": false,
    "allow_methods": ["GET", "POST", "PATCH", "DELETE"],
    "allow_headers": ["*"]
  }
}
```

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `enabled` | boolean | true | Enable CORS |
| `allow_origins` | string[] | [] | Allowed origins |
| `allow_credentials` | boolean | false | Allow credentials |
| `allow_methods` | string[] | - | Allowed HTTP methods |
| `allow_headers` | string[] | - | Allowed headers |

## Example Complete Configuration

```json
{
  "project_name": "my-awesome-project",
  "project_type": "python",
  "model": "MiniMax-M2.5-highspeed",
  "session_type": "coder",
  "active_provider": "default",
  "providers": {
    "default": {
      "provider": "minimax",
      "model": "MiniMax-M2.5-highspeed",
      "api_key_env": "ANTHROPIC_AUTH_TOKEN",
      "base_url_env": "ANTHROPIC_BASE_URL"
    }
  },
  "test_command": "pytest tests/ -v",
  "test_pattern": "test_*.py",
  "max_errors_before_intervention": 3,
  "context_window_limit": 100000,
  "api_keys": {
    "enabled": true,
    "keys": ["secret-key-123", "another-key-456"]
  },
  "rate_limit": {
    "enabled": true,
    "default_limit": "100/minute",
    "endpoints": {
      "/run": "10/minute",
      "/tasks": "30/minute"
    }
  },
  "retry": {
    "max_retries": 3,
    "retry_interval": 5,
    "retry_on_errors": ["connection_error", "timeout", "process_error"]
  },
  "webhook": {
    "enabled": true,
    "url": "https://my-server.com/webhook",
    "secret": "my-secret",
    "events": ["task_completed", "task_failed"]
  },
  "email": {
    "enabled": true,
    "smtp_host": "smtp.gmail.com",
    "smtp_port": 587,
    "smtp_user": "my-email@gmail.com",
    "smtp_password": "app-password",
    "use_tls": true,
    "from_name": "Agent-Loop",
    "from_email": "agent@mycompany.com",
    "to_emails": ["team@mycompany.com"],
    "events": ["task_completed", "task_failed", "human_intervention"]
  },
  "context_files": ["README.md", "CLAUDE.md", "pyproject.toml"],
  "verify_command": "pytest tests/ -x -q",
  "allowed_tools": ["Read", "Write", "Edit", "Bash", "Glob", "Grep", "MultiEdit", "WebSearch", "WebFetch"],
  "mcp_servers": [],
  "schema_version": "1.2"
}
```

## Hot Reload Configuration

Agent-Loop supports configuration hot reload without restart:

```bash
# Manual reload
uv run python main.py config reload

# Or use file watcher (enabled by default)
# Edit .agent/config.json - changes are applied automatically
```

See [Config Reloader](../agent/config_reloader.py) for implementation details.
