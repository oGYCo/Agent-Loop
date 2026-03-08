# Agent-Loop Memory

Accumulated experience and lessons learned from task execution. This file contains high-value insights organized by theme.

---

## Core Architecture Knowledge

### 1. Agent Core & SDK Integration
- **AgentCore** (`agent/agent_core.py`) orchestrates the entire execution flow: task selection → SDK execution → state persistence
- **SDK Pattern**: Use `ClaudeSDKClient(options=options)` with `async with` for proper resource management
- **Hook System**: PreToolUse, PostToolUse, Notification, Stop hooks for extensibility
- **Task Execution**: Exponential backoff retry (5s→10s→20s), max retries configurable

### 2. State Management
- **StateManager** persists to JSON files in `.agent/` directory
- **Atomic Writes**: Use `tempfile.NamedTemporaryFile` + `os.replace()` to prevent data corruption
- **File Locking**: Use `portalocker` for cross-platform file locking (prevents concurrent access corruption)
- **Round-trip Validation**: Read back after write to verify JSON integrity
- **Schema Versioning**: Add `schema_version` field to config for future migrations

### 3. Configuration System
- **Pydantic BaseSettings** with `env_prefix="AGENT_LOOP_"` for environment variable override
- Nested config via `env_nested_delimiter="__"` (e.g., `AGENT_LOOP_PROVIDERS__DEFAULT__MODEL`)
- **Config Migration Engine**: Chain-based migration with backward compatibility

---

## API & Web Services

### 4. REST API Design (FastAPI)
- **Versioning**: Add `/api/v1/` prefix, redirect legacy routes with 301
- **Middleware**: Request logging (method, path, status, duration_ms, request_id)
- **Error Format**: `{"error_code": "E1001", "message": "...", "detail": "..."}`
- **Pagination**: `page` (default 1), `per_page` (default 20, max 100)
- **Endpoints**: /api/v1/status, /api/v1/tasks, /api/v1/sessions, /api/v1/metrics, /health

### 5. WebSocket Real-time Push
- FastAPI `@app.websocket("/ws")` decorator for async handlers
- **ConnectionManager**: Handles connect/disconnect/broadcast lifecycle
- **Event Types**: log, status, task_progress, iteration
- Auto-reconnect with exponential backoff (1s→2s→4s→8s→16s→30s max)

### 6. Web Dashboard
- Single-page vanilla JS (no framework) for simplicity
- **CSS Variables** for theming (dark/light mode toggle)
- **Chart.js** for performance monitoring charts
- Debounced search input for filtering
- Incremental DOM updates for performance

---

## Notifications

### 7. Webhook System
- Supports: task_completed, task_failed, human_intervention events
- **Async/Sync Handling**: Use `asyncio.create_task()` if event loop exists, else `asyncio.run()`
- Retry logic with configurable count and interval
- Secret signature verification for security

### 8. Email & Slack Notifications
- **Email**: Use `aiosmtplib` for async SMTP, HTML templates with inline CSS
- **Slack**: Block Kit message formatting, color-coded attachments
- Lazy imports to avoid circular dependencies
- Unified notification interface across channels

---

## Observability

### 9. Structured Logging
- **structlog** for JSON output to file, human-readable to console
- **Correlation ID**: Track requests across services with `correlation_context()`
- **Sensitive Data Redaction**: Regex patterns for API keys, passwords, tokens
- **Audit Logging**: Separate logger for state changes

### 10. Prometheus Metrics
- Singleton `MetricsCollector` with thread-safe double-check locking
- Key metrics: task_completed_total, tasks_pending, session_duration, api_calls_total
- Provider-specific metrics: failover events, response times, health status
- Export via `/metrics` endpoint in Prometheus format

---

## Security

### 11. Security Best Practices (OWASP Top 10)
- **Rate Limiting**: `slowapi` with configurable limits per endpoint
- **CORS**: Strict same-origin by default, configurable allowed_origins
- **Input Validation**: Pydantic validators for all user inputs
- **XSS Sanitization**: Use `bleach` library for HTML content
- **CSP Headers**: Content-Security-Policy, X-Frame-Options, etc.
- **File Permissions**: 0o600 for state files

### 12. Exception Hierarchy
- Base `AgentLoopError` with: message, error_code, detail, is_retryable, original_exception
- **Error Code Ranges**: E1xxx (Config), E2xxx (Task), E3xxx (Provider), E4xxx (Notification), E5xxx (Session), E6xxx (State), E9xxx (General)
- Use `raise ... from e` to preserve exception chain

---

## Testing & Quality

### 13. Test Patterns
- **Fixtures**: `tempfile.TemporaryDirectory()` for isolation
- **Mock Strategy**: Mock external deps (API, SDK), use real for internal logic
- **Async Testing**: `pytest-asyncio` for async functions
- **Console Output**: `rich.console.Console(file=io.StringIO())` for capture
- **CLI E2E**: `subprocess.run()` with `--project-dir` for integration tests

### 14. Type Annotations
- `TYPE_CHECKING` to avoid circular imports
- `type: ignore[valid-type]` for third-party types
- `cast()` for complex type narrowing
- Explicit `Dict[str, Any]` for heterogeneous dictionaries

---

## Deployment & DevOps

### 15. Docker Containerization
- **Multi-stage build**: `python:3.11-slim` base, copy only necessary files
- **Security**: Non-root user (`USER agent`), minimal image size
- **Health Checks**: HTTP against `/health` endpoint
- **Docker Compose**: Agent service + API + Prometheus + Grafana

### 16. Task Dependencies (DAG)
- Topological sort (Kahn's algorithm) for execution order
- `depends_on` field in task structure
- Circular dependency detection with clear error messages
- CLI `--tree` visualization

---

## Key Patterns & Anti-Patterns

### Patterns to Follow
- ✅ Use `except Exception as e: logger.warning(...)` - never silent catch
- ✅ Use config files over hardcoded values
- ✅ Use `async with` for resource management
- ✅ Use Pydantic for data validation
- ✅ Use atomic writes for file operations

### Anti-Patterns to Avoid
- ❌ `except Exception: pass` - silently swallows errors
- ❌ Bare `except:` - catches KeyboardInterrupt/SystemExit
- ❌ Hardcoded values in code
- ❌ Direct file writes without locking

---

## File Structure Reference

```
Agent-Loop/
├── agent/
│   ├── agent_core.py       # Core execution logic
│   ├── state_manager.py   # State persistence
│   ├── session_manager.py # Session lifecycle
│   ├── task_selector.py   # Task selection (priority + dependencies)
│   ├── prompt_manager.py  # Template engine
│   ├── model_provider.py  # Multi-provider support
│   ├── config_model.py    # Pydantic config
│   ├── config_reloader.py # Hot reload
│   ├── metrics.py         # Prometheus metrics
│   ├── logging_.py        # Structured logging
│   ├── webhook.py         # Webhook notifications
│   ├── email_notifier.py  # Email notifications
│   ├── slack_notifier.py  # Slack notifications
│   ├── console.py         # Rich CLI output
│   ├── exceptions.py      # Exception hierarchy
│   ├── human_intervention.py
│   ├── git_helper.py
│   └── test_runner.py
├── api.py                  # FastAPI REST API
├── main.py                 # CLI entry point
├── static/                 # Web dashboard
├── dashboards/             # Grafana templates
└── tests/                  # Test suite
```

---

## Configuration Reference (config.json)

```json
{
  "schema_version": "1.2",
  "active_provider": "default",
  "providers": {
    "default": {
      "provider": "minimax",
      "model": "MiniMax-M2.5-highspeed",
      "api_key_env": "ANTHROPIC_AUTH_TOKEN"
    }
  },
  "rate_limit": { "enabled": true, "default_limit": "100/minute" },
  "cors": { "enabled": true, "allow_origins": [] },
  "webhook": { "enabled": false, "url": "", "events": ["task_completed", "task_failed"] },
  "email": { "enabled": false, "smtp_host": "smtp.gmail.com", "smtp_port": 587 },
  "slack": { "enabled": false, "webhook_url": "" },
  "api_keys": { "enabled": false, "keys": [] }
}
```

---

*Last Updated: 2026-03-08*
*Total Features Completed: 51*
*Test Suite: 800+ tests*

## Task Experience Records

### 2026-03-08 - MEMORY.md整理等等 (feature-050)

**任务描述**: 对当前的MEMORY.md进行系统性整理，并建立结构化的知识管理机制。具体包括：

1) **MEMORY.md清理整合**：
   - 合并重复的经验教训（如多个feature都提到的测试模式、JSON处理等）
   - 按主题分组整理（架构决策、测试经验、错误处理模式、性能优化、集成经验）
   - 删除过时的信息（如已修复的bug记录）
   - 将28个独立的task记录提炼为10-15条核心知识点
   - 目标：从当前内容精简到300行以内，信息密度更高，只保留那些重要的经验等等
2) **结构化知识索引**：在.agent/目录创建knowledge_index.json，按主题和标签索引MEMORY.md中的知识点，支持快速检索。
 5) **CLAUDE.md同步更新**：确保CLAUDE.md中的架构描述、模块列表、命令示例与当前代码完全一致。
 **关键指令**：执行此任务前必须完整阅读当前MEMORY.md和CLAUDE.md的内容以及仓库中的所有的相关内容。清理时保留高价值洞察，删除流水账式记录。

**执行结果**: completed
**执行消息**:
任务已完成！以下是所做更改的摘要：

## 完成的工作

### 1. MEMORY.md 清理整合
- **原始行数**: 2349 行
- **清理后行数**: 210 行（目标 < 300 行）✅
- **组织方式**: 按16个主题分组整理
  - 核心架构（Agent Core、状态管理、配置系统）
  - API与Web服务（REST API、WebSocket、Dashboard）
  - 通知系统（Webhook、Email、Slack）
  - 可观测性（日志、Metrics、Grafana）
  - 安全（异常体系、错误码）
  - 测试与质量（测试模式、类型注解）
  - 部署（Docker、任务依赖）

### 2. 创建 knowledge_index.json
- 创建了 `.agent/knowledge_index.json` 文件
- 包含18个主题标签，便于快速检索
- 包含常用命令速查表

### 3. CLAUDE.md 同步更新
- 添加了新模块：`notification_router.py`、`notification_queue.py`、
