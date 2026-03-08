# API Reference

Complete REST API documentation for Agent-Loop.

## Interactive Documentation

The fastest way to explore the API is to use the interactive Swagger UI:

1. Start the API server: `uv run python api.py`
2. Open http://localhost:8000/docs
3. Try out endpoints directly in your browser

## Base URL

```
http://localhost:8000/api/v1
```

## Authentication

### API Key Authentication

When `api_keys` is enabled in config.json, include your API key in the header:

```bash
curl -H "X-API-Key: your-api-key" http://localhost:8000/api/v1/tasks
```

## Endpoints

### Health Check

**GET** `/health`

Check API server health status.

```bash
curl http://localhost:8000/health
```

Response:
```json
{
  "status": "healthy",
  "version": "0.1.0",
  "timestamp": "2026-03-08T10:00:00Z"
}
```

---

### List Tasks

**GET** `/tasks`

List all tasks with optional filtering.

```bash
curl http://localhost:8000/api/v1/tasks
```

Query Parameters:
| Parameter | Type   | Description                                                |
| --------- | ------ | ---------------------------------------------------------- |
| `status`  | string | Filter by status (pending, in_progress, completed, failed) |
| `limit`   | int    | Maximum number of tasks to return                          |
| `offset`  | int    | Offset for pagination                                      |

Response:
```json
{
  "tasks": [
    {
      "id": "feat-001",
      "name": "Task Name",
      "description": "Task description",
      "priority": 1,
      "status": "pending",
      "passes": false,
      "created_at": "2026-03-08",
      "updated_at": "2026-03-08"
    }
  ],
  "total": 10
}
```

---

### Get Task

**GET** `/tasks/{task_id}`

Get a specific task by ID.

```bash
curl http://localhost:8000/api/v1/tasks/feat-001
```

Response:
```json
{
  "id": "feat-001",
  "name": "Task Name",
  "description": "Task description",
  "priority": 1,
  "status": "pending",
  "passes": false,
  "verify_command": "cat README.md",
  "context_files": ["CLAUDE.md"],
  "created_at": "2026-03-08",
  "updated_at": "2026-03-08"
}
```

---

### Create Task

**POST** `/tasks`

Create a new task.

```bash
curl -X POST http://localhost:8000/api/v1/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "name": "New Task",
    "description": "Task description",
    "priority": 1
  }'
```

Request Body:
| Field            | Type     | Required | Description                        |
| ---------------- | -------- | -------- | ---------------------------------- |
| `name`           | string   | Yes      | Task name                          |
| `description`    | string   | No       | Task description                   |
| `priority`       | int      | No       | Priority (1 = highest, default: 3) |
| `verify_command` | string   | No       | Verification command               |
| `context_files`  | string[] | No       | Files to include in context        |

Response:
```json
{
  "id": "feat-002",
  "name": "New Task",
  "description": "Task description",
  "priority": 1,
  "status": "pending",
  "passes": false,
  "created_at": "2026-03-08",
  "updated_at": "2026-03-08"
}
```

---

### Update Task

**PATCH** `/tasks/{task_id}`

Update an existing task.

```bash
curl -X PATCH http://localhost:8000/api/v1/tasks/feat-001 \
  -H "Content-Type: application/json" \
  -d '{
    "status": "completed",
    "passes": true
  }'
```

Request Body:
| Field         | Type    | Description                                      |
| ------------- | ------- | ------------------------------------------------ |
| `name`        | string  | Task name                                        |
| `description` | string  | Task description                                 |
| `priority`    | int     | Priority (1-5)                                   |
| `status`      | string  | Status (pending, in_progress, completed, failed) |
| `passes`      | boolean | Pass status                                      |

---

### Delete Task

**DELETE** `/tasks/{task_id}`

Delete a task.

```bash
curl -X DELETE http://localhost:8000/api/v1/tasks/feat-001
```

---

### Run Agent

**POST** `/run`

Start agent execution.

```bash
curl -X POST http://localhost:8000/api/v1/run \
  -H "Content-Type: application/json" \
  -d '{
    "iterations": 3
  }'
```

Request Body:
| Field        | Type   | Required | Description                        |
| ------------ | ------ | -------- | ---------------------------------- |
| `iterations` | int    | No       | Number of iterations (default: 10) |
| `task_id`    | string | No       | Specific task ID to run            |

Response:
```json
{
  "session_id": "sess-abc123",
  "status": "started",
  "iterations": 3,
  "message": "Agent execution started"
}
```

---

### Get Status

**GET** `/status`

Get current project status.

```bash
curl http://localhost:8000/api/v1/status
```

Response:
```json
{
  "project_name": "my-project",
  "current_task": "feat-001",
  "total_tasks": 10,
  "pending_tasks": 5,
  "completed_tasks": 3,
  "failed_tasks": 2,
  "last_run": "2026-03-08T10:00:00Z"
}
```

---

### Session History

**GET** `/session/history`

Get session history.

```bash
curl http://localhost:8000/api/v1/session/history
```

Query Parameters:
| Parameter | Type | Description                  |
| --------- | ---- | ---------------------------- |
| `limit`   | int  | Number of sessions to return |
| `offset`  | int  | Offset for pagination        |

Response:
```json
{
  "sessions": [
    {
      "session_id": "sess-abc123",
      "started_at": "2026-03-08T10:00:00Z",
      "ended_at": "2026-03-08T10:30:00Z",
      "iterations": 5,
      "tasks_completed": 3,
      "status": "completed"
    }
  ],
  "total": 10
}
```

---

### Test Webhook

**POST** `/webhook/test`

Test webhook configuration.

```bash
curl -X POST http://localhost:8000/api/v1/webhook/test \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://your-server.com/webhook",
    "secret": "your-secret"
  }'
```

---

### Test Email

**POST** `/email/test`

Test email configuration.

```bash
curl -X POST http://localhost:8000/api/v1/email/test \
  -H "Content-Type: application/json" \
  -d '{
    "smtp_host": "smtp.gmail.com",
    "smtp_port": 587,
    "smtp_user": "your-email@gmail.com",
    "smtp_password": "app-password",
    "to_emails": ["test@example.com"]
  }'
```

---

### Metrics

**GET** `/metrics`

Get Prometheus metrics.

```bash
curl http://localhost:8000/metrics
```

---

### WebSocket Streaming

**WebSocket** `/ws/stream`

Real-time agent output streaming.

```javascript
const ws = new WebSocket('ws://localhost:8000/api/v1/ws/stream');

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log(data.type, data.content);
};
```

## Error Responses

All endpoints return standard HTTP status codes:

| Code | Description           |
| ---- | --------------------- |
| 200  | Success               |
| 201  | Created               |
| 400  | Bad Request           |
| 401  | Unauthorized          |
| 404  | Not Found             |
| 429  | Rate Limited          |
| 500  | Internal Server Error |

Error response format:
```json
{
  "error": "Error message",
  "code": "ERROR_CODE",
  "details": {}
}
```

## Rate Limiting

When rate limiting is enabled, responses include headers:

- `X-RateLimit-Limit`: Maximum requests per window
- `X-RateLimit-Remaining`: Requests remaining in window
- `X-RateLimit-Reset`: Unix timestamp when limit resets
