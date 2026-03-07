# Agent-Loop Memory

Accumulated experience and lessons learned from task execution.

---

## 2026-03-08 - API Key Authentication (feature-013)

**Task Description**: 为API服务添加API Key认证机制，支持配置多个密钥，实现基本的访问控制。

**Lessons Learned:**

1. **Configuration**:
   - Added `api_keys` section to `.agent/config.json`:
     ```json
     "api_keys": {
       "enabled": false,
       "keys": []
     }
     ```
   - Note: config.json is in .gitignore (local config), won't be committed

2. **FastAPI Authentication**:
   - Used FastAPI's `Depends()` for dependency injection
   - Added `Header` and `Depends` imports from fastapi
   - Created `get_api_key()` dependency that validates X-API-Key header

3. **API Key Validation**:
   - Returns 401 if API key is required but not provided
   - Returns 403 if API key is invalid
   - Allows access if authentication is disabled (enabled=false)

4. **Endpoints Protected**:
   - GET /status, /tasks, /sessions, /metrics
   - POST /tasks, /run, /webhook/test
   - GET / (dashboard)
   - WebSocket /ws (via query parameter)
   - Health endpoint /health remains public

5. **WebSocket Authentication**:
   - WebSocket doesn't support Depends(), so handled manually
   - API key passed via query parameter: `ws://host:port/ws?api_key=your-key`
   - Closes with code 4001 if key missing, 4003 if invalid

6. **Testing**:
   - All 201 tests pass
   - Tested without auth: 401/403 as expected
   - Tested with valid key: 200 OK

7. **Commit**: Pushed as `feat: add API key authentication for API service`

---

## 2026-03-08 - Prometheus Metrics Export (feature-006)

**Task Description**: 添加 /metrics 端点暴露Prometheus格式的指标，包括：任务完成数、错误数、会话时长、API调用次数等。需要先了解prometheus-client库的使用方式。

**Lessons Learned:**

1. **Prometheus Client Library**:
   - Used `prometheus-client` library for Python
   - Added dependency: `prometheus-client>=0.19.0` to pyproject.toml

2. **Metrics Implemented**:
   - `agent_tasks_completed_total`: Counter with status label (success/error)
   - `agent_tasks_pending`: Gauge for pending tasks
   - `agent_tasks_total`: Gauge for total tasks
   - `agent_session_duration_seconds`: Histogram for session duration
   - `agent_sessions_active`: Gauge for active sessions
   - `agent_sessions_total`: Counter for total sessions
   - `agent_errors_total`: Counter with error type label
   - `agent_api_calls_total`: Counter with endpoint label
   - `agent_api_duration_seconds`: Histogram for API request duration
   - `agent_status`: Gauge (0=idle, 1=running, 2=error)
   - `agent_iterations_total`: Counter for agent iterations
   - `agent_task_duration_seconds`: Histogram for task execution duration

3. **API Integration**:
   - Added GET /metrics endpoint in api.py
   - Returns Prometheus text format with Content-Type: text/plain
   - Automatically updates task counts from StateManager
   - Increments API call counter for /metrics itself

4. **Singleton Pattern**:
   - Created MetricsCollector class with singleton pattern
   - Thread-safe with double-check locking
   - Provides methods for incrementing/updating all metrics

5. **Verification**:
   - All 248 tests pass
   - Tested: curl http://localhost:8000/metrics returns Prometheus format
   - Metrics include: agent_tasks_pending, agent_tasks_total, agent_status, etc.

6. **Commit**: Pushed as `feat: add Prometheus metrics endpoint (/metrics)`

---

## 2026-03-08 - Webhook Notification System (feature-005)

**Task Description**: 实现Webhook通知功能：当任务完成/失败/需要人工干预时，发送HTTP POST请求到配置的URL。需要阅读agent/human_intervention.py了解干预触发机制。

**Lessons Learned:**

1. **Webhook Implementation**:
   - Created new `agent/webhook.py` module with `WebhookNotifier` class
   - Supports three event types: `task_completed`, `task_failed`, `human_intervention`
   - Configurable via `webhook` section in config.json

2. **Configuration**:
   - Added webhook configuration to `.agent/config.json`:
     ```json
     "webhook": {
       "enabled": false,
       "url": "",
       "secret": "",
       "timeout": 10,
       "events": ["task_completed", "task_failed", "human_intervention"],
       "retry_count": 3,
       "retry_interval": 2
     }
     ```

3. **API Integration**:
   - Added `POST /webhook/test` endpoint in api.py for testing webhook configuration
   - Verified: `curl -X POST http://localhost:8000/webhook/test`

4. **Agent Integration**:
   - Integrated webhook notifications in `agent_core.py` - sends notifications on task completion/failure
   - Integrated webhook notifications in `human_intervention.py` - sends notification when human intervention is required
   - Used lazy imports to avoid circular dependencies
   - Used sync wrapper with asyncio.run() for proper async handling in sync contexts

5. **Async/Sync Handling**:
   - Webhook notifications are async by default
   - In sync contexts (like run_agent_loop), used wrapper functions that detect running event loop
   - If event loop exists, schedule task with create_task; otherwise run in new event loop

6. **Testing**:
   - Created `tests/test_webhook.py` with 16 test cases covering:
     - Configuration loading
     - Event filtering
     - Notification sending with mocked HTTP client
     - Secret handling
     - Retry logic

7. **Verification**:
   - All 239 tests pass
   - API endpoint returns correct message when webhook is not configured

8. **Commit**: Pushed as `feat: add webhook notification system`

---

## 2026-03-08 - Basic Web Dashboard Interface (feature-004)

**Task Description**: 创建简单的Web Dashboard展示：1) Agent当前状态 2) 任务列表和进度 3) 实时日志输出。可以使用HTML+JavaScript实现，需要先了解API端点设计。

**Lessons Learned:**

1. **API Endpoints Already Exist**:
   - The api.py already had all the endpoints needed for the dashboard
   - GET /status - Returns agent status (project info, git, tasks, current session)
   - GET /tasks - Returns task list with optional status filter
   - WebSocket /ws - Already implemented for real-time event streaming
   - GET /health - Health check endpoint

2. **Implementation Approach**:
   - Created static/ directory for web dashboard files
   - Created index.html with vanilla HTML/CSS/JavaScript (no frameworks needed)
   - Added FileResponse route at "/" to serve the dashboard

3. **Dashboard Features**:
   - **Status Panel**: Shows project name, type, git branch, changes, task progress
   - **Task List**: Shows all tasks with priority badges and status badges
   - **Real-time Logs**: Connects to WebSocket for live log streaming
   - **Auto-refresh**: Status every 30s, tasks every 10s

4. **WebSocket Integration**:
   - Dashboard connects to /ws endpoint for real-time updates
   - Handles event types: status, log, task_progress, iteration
   - Auto-reconnect on disconnect with 3-second delay

5. **FastAPI Static File Serving**:
   - Added import for `FileResponse` and `Path` from fastapi.responses
   - Added route `@app.get("/")` to serve static/index.html

6. **Verification**:
   - Tested: http://localhost:8000/ - Dashboard loads correctly
   - Tested: http://localhost:8000/status - Returns JSON with project info
   - Tested: http://localhost:8000/tasks - Returns task list
   - Tested: http://localhost:8000/health - Returns health status

7. **Commit**: Pushed as `feat: add basic web dashboard interface`

---

## 2026-03-08 - WebSocket Real-time Push Integration (feature-003)

**Task Description**: 实现WebSocket端点 /ws 用于实时推送Agent运行状态、任务进度、日志

**Lessons Learned:**

1. **WebSocket Implementation in FastAPI**:
   - FastAPI provides WebSocket support via `@app.websocket("/ws")` decorator
   - Need to import `WebSocket` and `WebSocketDisconnect` from fastapi
   - WebSocket connections are async and require `async def` handlers

2. **Existing Code Structure**:
   - The api.py already had ConnectionManager and EventPusher classes implemented
   - The `/ws` endpoint was added in previous commit
   - ConnectionManager handles connection lifecycle (connect, disconnect, broadcast)
   - EventPusher is a singleton for pushing events to all connected clients

3. **Integration with agent_core.py**:
   - Used lazy import in _get_event_pusher() to avoid circular dependency (api.py imports agent_core.py for /run endpoint)
   - Added async _push_log_async for use in async hooks
   - Added sync _push_log_sync wrapper for sync code paths with event loop handling

4. **Event Push Integration Points**:
   - pre_tool_hook: Pushes tool call start events
   - post_tool_hook: Pushes tool call completion events
   - notification_hook: Pushes notification messages
   - stop_hook: Pushes session end events
   - run_agent_loop: Pushes session start, iteration start, task start/completion, session completion

5. **Event Types**:
   - `log`: Log messages with level (info, warning, error) and source (tool, session, task, etc.)

6. **Verification**:
   - Tested WebSocket connection: `ws://localhost:8000/ws`
   - Server successfully accepts connections and sends welcome message
   - All 223 existing tests pass
   - No circular import issues

7. **Commit**: Pushed as `feat: integrate EventPusher into agent_core for WebSocket event push`

---

## 2026-03-08 - WebSearch and WebFetch Abilities (feature-015)

**Task Description**: 确认系统是否具有能够成功进行WebSearch和WebFetch的功能，同时，要在默认的提示词中加入这两个能力应该是在执行任务之前用来查阅任务相关的各种必要的文档信息

**Lessons Learned:**

1. **WebSearch/WebFetch Already Exist in Code**:
   - agent_core.py already has WebSearch and WebFetch in the default tools list
   - prompt_manager.py already mentions them in the system prompt

2. **Config.json Was Missing WebSearch/WebFetch**:
   - The .agent/config.json had allowed_tools without WebSearch and WebFetch
   - Added both tools to config.json allowed_tools: `["Read", "Write", "Edit", "Bash", "Glob", "Grep", "MultiEdit", "WebSearch", "WebFetch"]`
   - Note: config.json is in .gitignore so changes won't be committed (intentional - it's local config)

3. **Updated System Prompt**:
   - Added explicit instruction to use WebSearch/WebFetch before executing tasks
   - Added "Use Web Tools to Research" section in the "Before Starting Any Task" section
   - Updated workflow to include web research as step 2
   - Updated Web Tools description to emphasize documentation research

4. **Verification**: All 223 tests pass.

5. **Commit**: Pushed as `feat: add WebSearch/WebFetch to system prompt for documentation lookup`

---

## 2026-03-08 - REST API Service with FastAPI (feature-002)

**Task Description**: 使用FastAPI搭建REST API服务，提供以下端点：GET /status (Agent状态), GET /tasks (任务列表), POST /tasks (添加任务), POST /run (启动Agent), GET /sessions (会话历史)。需要先阅读agent/state_manager.py了解状态管理机制，阅读main.py了解CLI命令结构。

**Lessons Learned:**

1. **Project Analysis Process**:
   - Read agent/state_manager.py to understand state management (feature lists, sessions, config)
   - Read main.py to understand CLI command structure and how to add new commands
   - Read agent/session_manager.py to understand session history handling

2. **Implementation Details**:
   - Created new api.py file with FastAPI application
   - Added FastAPI and uvicorn dependencies to pyproject.toml
   - Integrated with existing StateManager, TaskSelector, SessionManager, GitHelper classes
   - Added CLI server command to main.py for easy server startup

3. **Endpoints Implemented**:
   - GET /status: Returns agent status (project info, git, tasks, current session)
   - GET /tasks: Returns task list with optional status filter
   - POST /tasks: Creates new task with name, description, priority
   - POST /run: Starts the agent (placeholder - not fully implemented)
   - GET /sessions: Returns session history
   - GET /health: Health check endpoint

4. **CLI Integration**:
   - Added `server` subcommand: `python main.py server [--host HOST] [--port PORT]`
   - Server defaults to 0.0.0.0:8000

5. **Key Design Decisions**:
   - Used Pydantic models for request/response validation
   - Reused existing StateManager and related classes for consistency
   - API runs on uvicorn ASGI server
   - Error handling with proper HTTPException responses

6. **Verification**:
   - All 187 tests pass
   - Tested all endpoints with curl:
     - GET /status returns JSON with project info
     - GET /tasks returns task list
     - POST /tasks creates new task
     - GET /sessions returns session history

7. **Commit**: Pushed as `feat: Add REST API service with FastAPI`

---

## 2026-03-07 - Explore and New Feature Planning (feature-001)

**Task Description**: 完整探索整个仓库的内容，进行头脑风暴想一些能够让项目变的更加完备以及用户友好的各种新功能，进行细致的分析和规划，写入markdown文档，并制定详细的后续计划到feature_list.json中，按优先级排序。

**Lessons Learned:**

1. **Project Analysis Process**:
   - Read CLAUDE.md and README.md for project overview and architecture
   - Read all core modules: main.py, agent_core.py, prompt_manager.py, session_manager.py, state_manager.py, etc.
   - Reviewed analysis_report.md for existing issues and technical debt
   - Examined pyproject.toml for current dependencies

2. **Brainstormed New Features (categorized)**:
   - **Frontend/UI**: Web Dashboard, Task Board, Real-time Log Viewer, Config Editor
   - **API/Services**: REST API, WebSocket, Webhooks, MCP Server, gRPC
   - **Notifications**: Email, Slack/Discord, Telegram, Feishu/DingTalk, Webhook
   - **Observability**: Prometheus metrics, Grafana dashboards, Structured logging, OpenTelemetry
   - **Plugins**: Plugin system, Tool marketplace, Custom validators
   - **UX Improvements**: Rich CLI, Progress bars, Color themes, Command completion
   - **Data/Storage**: SQLite, Redis cache, Cloud backup, Data export
   - **Security**: API key auth, RBAC, Audit logs, Encryption

3. **Priority Analysis**:
   - **P0 (Core)**: REST API → WebSocket → Web Dashboard (foundational infrastructure)
   - **P1 (Important)**: Webhooks, Prometheus, Email/Slack notifications, Rich CLI
   - **P2 (Enhancement)**: Task board, Grafana, Auth, Feishu integration, Plugins, SQLite

4. **Key Design Decisions**:
   - REST API with FastAPI (async-compatible with existing code)
   - Web Dashboard as HTML/JS (simple) or React/Vue (complex)
   - All tasks include `context_files` for agent to gather sufficient info before execution
   - Each task has `verify_command` for testing

5. **Output Created**:
   - `NEW_FEATURES_ANALYSIS.md`: Comprehensive analysis document (251 lines)
   - `feature_list.json`: 16 prioritized tasks with detailed descriptions

6. **Verification**: Feature list created and committed.

7. **Commit**: Pushed as `feat: Add new features analysis and 16 prioritized roadmap tasks`

---

## Previous Lessons

*(Add new lessons at the top)*

