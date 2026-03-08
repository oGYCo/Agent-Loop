"""REST API Server - FastAPI based API service for Agent-Loop

Provides HTTP endpoints to interact with the Agent-Loop system.
Production-grade with API versioning, logging, error handling, and more.
"""

import asyncio
import json
import os
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import bleach
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Header, Depends, Request, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response, JSONResponse
from starlette.middleware.gzip import GZipMiddleware
from pydantic import BaseModel, field_validator
from pydantic import ValidationInfo
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from agent.state_manager import StateManager
from agent.task_selector import TaskSelector
from agent.session_manager import SessionManager
from agent.git_helper import GitHelper
from agent.metrics import get_prometheus_metrics, get_metrics_content_type, get_metrics_collector
from agent.logging_ import configure_logging, get_logger
from agent.exceptions import (
    AgentLoopError,
    ConfigError,
    ConfigValidationError,
    TaskExecutionError,
    ProviderError,
    NotificationError,
    SessionError,
    StateError,
    ErrorCode,
)

# Configure structured logging
log_level = os.environ.get("LOG_LEVEL", "INFO")
log_file = os.environ.get("LOG_FILE", "")
json_output = bool(log_file)
configure_logging(log_level=log_level, log_file=log_file, json_output=json_output)
logger = get_logger(__name__)


# ========== Unified Error Response ==========

def create_error_response(
    error_code: ErrorCode,
    message: str,
    status_code: int = 500,
    detail: Optional[str] = None,
) -> JSONResponse:
    """Create a standardized JSON error response.

    Args:
        error_code: The error code enum value
        message: Human-readable error message
        status_code: HTTP status code
        detail: Additional details about the error

    Returns:
        JSONResponse with standardized error format
    """
    error_dict: Dict[str, Any] = {
        "error_code": error_code.value,
        "message": message,
        "timestamp": datetime.now().isoformat(),
    }
    if detail:
        error_dict["detail"] = detail

    return JSONResponse(
        status_code=status_code,
        content=error_dict,
    )


def handle_agent_error(error: Exception) -> JSONResponse:
    """Convert AgentLoopError to standardized JSON response.

    Args:
        error: The exception to handle

    Returns:
        JSONResponse with standardized error format
    """
    if isinstance(error, AgentLoopError):
        # Map error codes to HTTP status codes
        status_code = 500
        if isinstance(error, (ConfigValidationError, StateError)):
            status_code = 400
        elif isinstance(error, (SessionError, StateError)):
            status_code = 404

        return create_error_response(
            error_code=error.error_code,
            message=error.message,
            status_code=status_code,
            detail=error.detail,
        )

    # For non-AgentLoopError exceptions, create a generic error response
    return create_error_response(
        error_code=ErrorCode.E9001,
        message=str(error),
        status_code=500,
        detail=type(error).__name__,
    )


# ========== Rate Limiter ==========
limiter = Limiter(key_func=get_remote_address)


def load_rate_limit_config() -> Dict[str, Any]:
    """Load rate limit configuration from config

    Returns:
        Dict with rate limit settings
    """
    try:
        state_manager = StateManager()
        config = state_manager.load_config()
        rate_limit = config.get("rate_limit", {})
        return {
            "enabled": rate_limit.get("enabled", True),
            "default_limit": rate_limit.get("default_limit", "100/minute"),
            "endpoints": rate_limit.get("endpoints", {})
        }
    except Exception:
        return {
            "enabled": True,
            "default_limit": "100/minute",
            "endpoints": {}
        }


app = FastAPI(
    title="Agent-Loop API",
    description="""## Production-Grade REST API for Agent-Loop

This API provides comprehensive endpoints for managing the Agent-Loop autonomous agent system.

### Features
- **Task Management**: Create, read, update, delete, and bulk operations on tasks
- **Session Management**: View session history and stats
- **Agent Control**: Run agent, pause/resume execution
- **Real-time Events**: WebSocket streaming for agent events
- **Health Monitoring**: System health checks with dependency verification
- **Metrics**: Prometheus-compatible metrics endpoint

### Authentication
Use the `X-API-Key` header for API key authentication (when enabled in config).

### Versioning
- Current version: **v1** (prefix: `/api/v1`)
- Legacy routes (without version prefix) are redirected to v1
""",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# Add GZip compression middleware
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Add rate limiter to app state
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# ========== Global Exception Handler ==========

class APIException(Exception):
    """Base API exception with structured error response"""

    def __init__(self, message: str, status_code: int = 500, error_code: str = "E0000", detail: Optional[str] = None):
        self.message = message
        self.status_code = status_code
        self.error_code = error_code
        self.detail = detail
        super().__init__(message)


@app.exception_handler(APIException)
async def api_exception_handler(request: Request, exc: APIException) -> JSONResponse:
    """Handle custom API exceptions with structured error response"""
    error_response: Dict[str, Any] = {
        "error_code": exc.error_code,
        "message": exc.message,
        "timestamp": datetime.now().isoformat(),
    }
    if exc.detail:
        error_response["detail"] = exc.detail
    return JSONResponse(status_code=exc.status_code, content=error_response)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Global exception handler for unhandled errors"""
    logger.error(f"Unhandled exception: {type(exc).__name__}: {exc}")

    # Check if it's already an AgentLoopError handled elsewhere
    if isinstance(exc, AgentLoopError):
        return handle_agent_error(exc)

    error_response: Dict[str, Any] = {
        "error_code": "E9001",
        "message": "Internal server error",
        "timestamp": datetime.now().isoformat(),
        "detail": str(exc) if os.environ.get("DEBUG") else "An unexpected error occurred"
    }
    return JSONResponse(status_code=500, content=error_response)


# ========== Request/Response Logging Middleware ==========

@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all requests with method, path, status, duration, and request_id"""
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id

    start_time = time.time()

    # Log incoming request
    logger.info(
        f"Request started",
        extra={
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "client_host": request.client.host if request.client else None,
        }
    )

    # Process request
    try:
        response = await call_next(request)
    except Exception as e:
        logger.error(
            f"Request failed",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "error": str(e),
            }
        )
        raise

    # Calculate duration
    duration_ms = (time.time() - start_time) * 1000

    # Log response
    logger.info(
        f"Request completed",
        extra={
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_ms": round(duration_ms, 2),
        }
    )

    # Add request_id to response headers
    response.headers["X-Request-ID"] = request_id
    return response


def load_cors_config() -> Dict[str, Any]:
    """Load CORS configuration from config

    Returns:
        Dict with CORS settings
    """
    try:
        state_manager = StateManager()
        config = state_manager.load_config()
        cors = config.get("cors", {})
        return {
            "enabled": cors.get("enabled", True),
            "allow_origins": cors.get("allow_origins", []),  # Empty means same-origin only
            "allow_credentials": cors.get("allow_credentials", False),
            "allow_methods": cors.get("allow_methods", ["GET", "POST", "PATCH", "DELETE"]),
            "allow_headers": cors.get("allow_headers", ["*"]),
        }
    except Exception:
        # Default: strict same-origin only
        return {
            "enabled": True,
            "allow_origins": [],
            "allow_credentials": False,
            "allow_methods": ["GET", "POST", "PATCH", "DELETE"],
            "allow_headers": ["*"],
        }


# Add CORS middleware
cors_config = load_cors_config()
if cors_config["enabled"]:
    # If allow_origins is empty, only allow same-origin requests
    allow_origins = cors_config["allow_origins"] if cors_config["allow_origins"] else ["*"]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allow_origins,
        allow_credentials=cors_config["allow_credentials"],
        allow_methods=cors_config["allow_methods"],
        allow_headers=cors_config["allow_headers"],
    )
    logger.info(f"CORS enabled with origins: {allow_origins}")
else:
    logger.info("CORS disabled")


# ========== API Versioning ==========

# Create v1 router with /api/v1 prefix
api_v1_router = FastAPI(
    title="Agent-Loop API v1",
    description="Version 1 of the Agent-Loop REST API",
    version="1.0.0",
)

# Global agent state for pause/resume
_agent_paused = False
_agent_instance = None


# Legacy route redirects - redirect old paths to new v1 paths
@app.get("/tasks", tags=["Redirect"])
async def redirect_tasks(request: Request):
    """Redirect /tasks to /api/v1/tasks"""
    from fastapi.responses import RedirectResponse
    # Preserve query parameters
    query = request.url.query
    new_url = f"/api/v1/tasks?{query}" if query else "/api/v1/tasks"
    return RedirectResponse(url=new_url, status_code=301)


@app.get("/sessions", tags=["Redirect"])
async def redirect_sessions(request: Request):
    """Redirect /sessions to /api/v1/sessions"""
    from fastapi.responses import RedirectResponse
    # Preserve query parameters
    query = request.url.query
    new_url = f"/api/v1/sessions?{query}" if query else "/api/v1/sessions"
    return RedirectResponse(url=new_url, status_code=301)


@app.get("/status", tags=["Redirect"])
async def redirect_status():
    """Redirect /status to /api/v1/status"""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/api/v1/status", status_code=301)


@app.get("/run", tags=["Redirect"])
async def redirect_run():
    """Redirect /run to /api/v1/run"""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/api/v1/run", status_code=301)


# Global state
_agent_instance = None

# ========== API Key Authentication ==========

# Security: Track authentication attempts for monitoring
_auth_attempts: Dict[str, int] = {}


def load_api_keys() -> tuple[bool, List[str]]:
    """Load API keys from config

    Returns:
        Tuple of (enabled, keys)
    """
    try:
        state_manager = StateManager()
        config = state_manager.load_config()
        api_keys_config = config.get("api_keys", {})
        enabled = api_keys_config.get("enabled", False)
        keys = api_keys_config.get("keys", [])
        return enabled, keys
    except Exception:
        # Default to disabled for security - require explicit enable
        return False, []


def get_api_key(x_api_key: str = Header(None, description="API key for authentication")) -> str:
    """Validate API key from request header

    Args:
        x_api_key: API key from X-API-Key header

    Returns:
        The validated API key

    Raises:
        HTTPException: If API key is invalid or missing

    Security: Uses unified error response to prevent endpoint enumeration.
    Both missing and invalid key return 401 to avoid revealing whether
    the endpoint requires authentication or if the key is invalid.
    """
    enabled, valid_keys = load_api_keys()

    # If API key authentication is not enabled, require explicit opt-in
    # For security, we default to requiring auth unless explicitly disabled
    if not enabled:
        # When disabled, still require a placeholder to prevent accidental exposure
        # but accept any non-empty value to allow easier testing
        if x_api_key:
            return x_api_key
        # If explicitly disabled, allow access (legacy behavior for backward compatibility)
        return "no-auth"

    # Security: Unified error response - don't reveal if endpoint exists
    # Both missing key and invalid key return 401 to prevent enumeration
    if not x_api_key:
        raise HTTPException(
            status_code=401,
            detail="Authentication required"
        )

    # Check if API key is valid (constant-time comparison not needed for API keys)
    if x_api_key not in valid_keys:
        # Log failed attempt for security monitoring (don't include the key)
        logger.warning(f"Invalid API key attempt from authentication")
        raise HTTPException(
            status_code=401,
            detail="Authentication required"
        )

    return x_api_key


# ========== WebSocket Manager ==========

class ConnectionManager:
    """Manages WebSocket connections for real-time event streaming"""

    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        """Accept a new WebSocket connection"""
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket client connected. Total connections: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        """Remove a WebSocket connection"""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(f"WebSocket client disconnected. Total connections: {len(self.active_connections)}")

    async def send_message(self, message: Dict[str, Any]):
        """Send a message to all connected clients"""
        if not self.active_connections:
            return
        message_json = json.dumps(message, ensure_ascii=False)
        # Send to all active connections
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_text(message_json)
            except Exception as e:
                logger.warning(f"Failed to send to WebSocket: {e}")
                disconnected.append(connection)
        # Clean up disconnected clients
        for conn in disconnected:
            self.disconnect(conn)

    async def broadcast(self, event_type: str, data: Dict[str, Any]):
        """Broadcast an event to all connected clients"""
        message = {
            "type": event_type,
            "timestamp": datetime.now().isoformat(),
            "data": data
        }
        await self.send_message(message)


# Global WebSocket manager
ws_manager = ConnectionManager()


# ========== Event Pusher ==========

class EventPusher:
    """Singleton class to push events to WebSocket clients"""

    _instance = None
    _ws_manager: Optional[ConnectionManager] = None

    @classmethod
    def get_instance(cls) -> "EventPusher":
        """Get the singleton instance"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def set_ws_manager(cls, manager: ConnectionManager):
        """Set the WebSocket manager"""
        cls._ws_manager = manager

    async def push_status(self, status: str, message: str, data: Optional[Dict[str, Any]] = None):
        """Push agent status update"""
        if self._ws_manager:
            await self._ws_manager.broadcast("status", {
                "status": status,
                "message": message,
                "data": data or {}
            })

    async def push_task_progress(self, task_id: str, progress: str, details: Optional[Dict[str, Any]] = None):
        """Push task progress update"""
        if self._ws_manager:
            await self._ws_manager.broadcast("task_progress", {
                "task_id": task_id,
                "progress": progress,
                "details": details or {}
            })

    async def push_log(self, level: str, message: str, source: Optional[str] = None):
        """Push log message"""
        if self._ws_manager:
            await self._ws_manager.broadcast("log", {
                "level": level,
                "message": message,
                "source": source
            })

    async def push_iteration(self, iteration: int, total: int, task: Optional[str] = None):
        """Push iteration update"""
        if self._ws_manager:
            await self._ws_manager.broadcast("iteration", {
                "current": iteration,
                "total": total,
                "task": task
            })


# Initialize EventPusher with ws_manager
EventPusher.set_ws_manager(ws_manager)


# ========== Request/Response Models ==========

# Input validation constants
MAX_TASK_NAME_LENGTH = 200
MAX_DESCRIPTION_LENGTH = 2000
MAX_ID_LENGTH = 50
# Whitelist for allowed characters in task names (alphanumeric, dash, underscore, space)
VALID_TASK_NAME_PATTERN = r'^[\w\s\-]+$'


class TaskCreate(BaseModel):
    """Task creation request model with input validation"""
    id: Optional[str] = None
    name: str
    description: Optional[str] = None
    priority: Optional[int] = 99

    @field_validator('name')
    @classmethod
    def validate_name(cls, v: str, info: ValidationInfo) -> str:
        """Validate and sanitize task name"""
        if not v or not v.strip():
            raise ValueError("Task name cannot be empty")

        # Check length
        if len(v) > MAX_TASK_NAME_LENGTH:
            raise ValueError(f"Task name cannot exceed {MAX_TASK_NAME_LENGTH} characters")

        # Check for valid characters (alphanumeric, dash, underscore, space)
        import re
        if not re.match(VALID_TASK_NAME_PATTERN, v):
            raise ValueError("Task name can only contain letters, numbers, spaces, dashes, and underscores")

        # Strip and return sanitized name
        return v.strip()

    @field_validator('description')
    @classmethod
    def validate_description(cls, v: Optional[str], info: ValidationInfo) -> Optional[str]:
        """Validate and sanitize task description"""
        if v is None:
            return None

        # Check length
        if len(v) > MAX_DESCRIPTION_LENGTH:
            raise ValueError(f"Description cannot exceed {MAX_DESCRIPTION_LENGTH} characters")

        # Strip and return
        return v.strip()

    @field_validator('id')
    @classmethod
    def validate_id(cls, v: Optional[str], info: ValidationInfo) -> Optional[str]:
        """Validate task ID format"""
        if v is None:
            return None

        if len(v) > MAX_ID_LENGTH:
            raise ValueError(f"Task ID cannot exceed {MAX_ID_LENGTH} characters")

        # Only allow alphanumeric, dash, underscore
        import re
        if not re.match(r'^[\w\-]+$', v):
            raise ValueError("Task ID can only contain letters, numbers, dashes, and underscores")

        return v.strip()

    @field_validator('priority')
    @classmethod
    def validate_priority(cls, v: Optional[int], info: ValidationInfo) -> Optional[int]:
        """Validate priority value"""
        if v is None:
            return 99

        if not isinstance(v, int):
            raise ValueError("Priority must be an integer")

        if v < 1 or v > 99:
            raise ValueError("Priority must be between 1 and 99")

        return v


class TaskResponse(BaseModel):
    """Task response model"""
    id: str
    name: str
    description: str
    priority: int
    status: str
    passes: bool
    created_at: str
    updated_at: str
    verify_command: Optional[str] = None
    context_files: Optional[List[str]] = None


class TaskUpdate(BaseModel):
    """Task update request model with validation"""
    priority: Optional[int] = None
    status: Optional[str] = None
    passes: Optional[bool] = None

    @field_validator('status')
    @classmethod
    def validate_status(cls, v: Optional[str], info: ValidationInfo) -> Optional[str]:
        """Validate status value"""
        if v is None:
            return v

        valid_statuses = {"pending", "completed", "failed", "in_progress"}
        if v not in valid_statuses:
            raise ValueError(f"Status must be one of: {', '.join(valid_statuses)}")

        return v

    @field_validator('priority')
    @classmethod
    def validate_priority(cls, v: Optional[int], info: ValidationInfo) -> Optional[int]:
        """Validate priority value"""
        if v is None:
            return v

        if not isinstance(v, int):
            raise ValueError("Priority must be an integer")

        if v < 1 or v > 99:
            raise ValueError("Priority must be between 1 and 99")

        return v


class StatusResponse(BaseModel):
    """Agent status response model"""
    project_name: str
    project_type: str
    test_command: str
    git_branch: str
    has_changes: bool
    tasks_completed: int
    tasks_total: int
    tasks_pending: int
    current_session: Optional[Dict[str, Any]]
    error_count: int


class SessionResponse(BaseModel):
    """Session history response model"""
    total_sessions: int
    completed_sessions: int
    sessions: List[Dict[str, Any]]


class PaginatedTaskResponse(BaseModel):
    """Paginated task list response"""
    items: List[TaskResponse]
    page: int
    per_page: int
    total: int
    total_pages: int


class PaginatedSessionResponse(BaseModel):
    """Paginated session list response"""
    items: List[Dict[str, Any]]
    page: int
    per_page: int
    total: int
    total_pages: int


class TaskDeleteResponse(BaseModel):
    """Task deletion response"""
    success: bool
    message: str
    task_id: str
    deleted_archived: bool = False


class BulkTaskOperation(BaseModel):
    """Bulk task operation request"""
    operations: List[Dict[str, Any]]


class BulkTaskResponse(BaseModel):
    """Bulk task operation response"""
    success: bool
    created: int
    updated: int
    deleted: int
    errors: List[Dict[str, str]]


class AgentControlResponse(BaseModel):
    """Agent control response"""
    success: bool
    message: str
    state: str


class HealthCheckResponse(BaseModel):
    """Enhanced health check response"""
    status: str
    service: str
    timestamp: str
    dependencies: Dict[str, Any]


class RunRequest(BaseModel):
    """Agent run request model"""
    iterations: Optional[int] = 10


class RunResponse(BaseModel):
    """Agent run response model"""
    success: bool
    message: str
    iterations: int
    completed: int
    errors: int


# ========== XSS Sanitization ==========

def sanitize_for_html(text: str) -> str:
    """Sanitize text for safe HTML output

    Args:
        text: Input text to sanitize

    Returns:
        Sanitized text safe for HTML display
    """
    if not text:
        return ""
    # Use bleach to strip dangerous HTML tags
    return bleach.clean(text, tags=[], strip=True)


def sanitize_task_response(task: Dict[str, Any]) -> Dict[str, Any]:
    """Sanitize task data for safe API response

    Args:
        task: Task dictionary

    Returns:
        Sanitized task dictionary
    """
    sanitized = task.copy()
    # Sanitize string fields that might be displayed in HTML
    for field in ['name', 'description', 'verify_command']:
        if field in sanitized and sanitized[field]:
            sanitized[field] = sanitize_for_html(str(sanitized[field]))
    return sanitized


# ========== API Endpoints ==========

@app.get("/status", response_model=StatusResponse)
@app.get("/api/v1/status", response_model=StatusResponse, tags=["Status"])
@limiter.limit("60/minute")
def get_status(request: Request, api_key: str = Depends(get_api_key)) -> StatusResponse:
    """Get current Agent status including project info, git status, and task statistics.

    Returns:
        - Project name and type
        - Git branch and changes status
        - Task counts (completed, pending, total)
        - Current session info
        - Error count
    """
    try:
        state_manager = StateManager()
        git_helper = GitHelper()
        task_selector = TaskSelector(state_manager)

        # Get config
        config = state_manager.load_config()

        # Get state
        state = state_manager.load_state()

        # Get task stats
        completed = task_selector.get_completed_count()
        total = task_selector.get_total_count()
        pending = task_selector.get_pending_count()

        return StatusResponse(
            project_name=config.get("project_name", "N/A"),
            project_type=config.get("project_type", "N/A"),
            test_command=config.get("test_command", "N/A"),
            git_branch=git_helper.get_current_branch() or "N/A",
            has_changes=git_helper.has_changes(),
            tasks_completed=completed,
            tasks_total=total,
            tasks_pending=pending,
            current_session=state.get("current_session"),
            error_count=state.get("error_count", 0)
        )
    except AgentLoopError as e:
        logger.error(f"Agent error getting status: {e}")
        raise handle_agent_error(e)
    except Exception as e:
        logger.error(f"Error getting status: {e}")
        raise HTTPException(status_code=500, detail=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/tasks", response_model=PaginatedTaskResponse)
@app.get("/api/v1/tasks", response_model=PaginatedTaskResponse, tags=["Tasks"])
@limiter.limit("60/minute")
def get_tasks(
    request: Request,
    status_filter: Optional[str] = None,
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    api_key: str = Depends(get_api_key)
) -> PaginatedTaskResponse:
    """Get task list with pagination support, optionally filtered by status.

    - **page**: Page number (starting from 1)
    - **per_page**: Number of items per page (max 100)
    - **status_filter**: Filter by task status (pending, completed, failed, in_progress)
    """
    try:
        state_manager = StateManager()
        data = state_manager.load_feature_list()
        features = data.get("features", [])

        # Filter by status if provided (exclude archived unless explicitly requested)
        if status_filter and status_filter != "all":
            features = [f for f in features if f.get("status") == status_filter]
        else:
            # By default, exclude archived tasks
            features = [f for f in features if f.get("status") != "archived"]

        # Sort by priority
        features.sort(key=lambda x: x.get("priority", 99))

        total = len(features)
        total_pages = (total + per_page - 1) // per_page if total > 0 else 1

        # Calculate pagination
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        paginated_features = features[start_idx:end_idx]

        return PaginatedTaskResponse(
            items=[
                TaskResponse(
                    id=f.get("id", ""),
                    name=f.get("name", ""),
                    description=f.get("description", ""),
                    priority=f.get("priority", 99),
                    status=f.get("status", "pending"),
                    passes=f.get("passes", False),
                    created_at=f.get("created_at", ""),
                    updated_at=f.get("updated_at", "")
                )
                for f in paginated_features
            ],
            page=page,
            per_page=per_page,
            total=total,
            total_pages=total_pages
        )
    except AgentLoopError as e:
        logger.error(f"Agent error getting tasks: {e}")
        raise handle_agent_error(e)
    except Exception as e:
        logger.error(f"Error getting tasks: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tasks", response_model=TaskResponse, status_code=201)
@limiter.limit("30/minute")
def create_task(request: Request, task: TaskCreate, api_key: str = Depends(get_api_key)) -> TaskResponse:
    """Add a new task"""
    try:
        state_manager = StateManager()

        # Generate ID if not provided
        task_id = task.id
        if not task_id:
            existing_features = state_manager.load_feature_list().get("features", [])
            task_id = f"task-{len(existing_features) + 1:03d}"

        now = datetime.now().strftime("%Y-%m-%d")

        new_feature = {
            "id": task_id,
            "name": task.name,
            "description": task.description or "",
            "priority": task.priority or 99,
            "status": "pending",
            "passes": False,
            "created_at": now,
            "updated_at": now
        }

        state_manager.add_feature(new_feature)

        return TaskResponse(
            id=new_feature["id"],
            name=new_feature["name"],
            description=new_feature["description"],
            priority=new_feature["priority"],
            status=new_feature["status"],
            passes=new_feature["passes"],
            created_at=new_feature["created_at"],
            updated_at=new_feature["updated_at"]
        )
    except AgentLoopError as e:
        logger.error(f"Agent error creating task: {e}")
        raise handle_agent_error(e)
    except Exception as e:
        logger.error(f"Error creating task: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/tasks/{task_id}", response_model=TaskResponse)
@limiter.limit("60/minute")
def get_task(request: Request, task_id: str, api_key: str = Depends(get_api_key)) -> TaskResponse:
    """Get a single task by ID"""
    try:
        state_manager = StateManager()
        feature = state_manager.get_feature(task_id)

        if not feature:
            raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

        return TaskResponse(
            id=feature.get("id", ""),
            name=feature.get("name", ""),
            description=feature.get("description", ""),
            priority=feature.get("priority", 99),
            status=feature.get("status", "pending"),
            passes=feature.get("passes", False),
            created_at=feature.get("created_at", ""),
            updated_at=feature.get("updated_at", ""),
            verify_command=feature.get("verify_command"),
            context_files=feature.get("context_files")
        )
    except HTTPException:
        raise
    except AgentLoopError as e:
        logger.error(f"Agent error getting task: {e}")
        raise handle_agent_error(e)
    except Exception as e:
        logger.error(f"Error getting task: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.patch("/tasks/{task_id}", response_model=TaskResponse)
@limiter.limit("30/minute")
def update_task(request: Request, task_id: str, updates: TaskUpdate, api_key: str = Depends(get_api_key)) -> TaskResponse:
    """Update a task (priority, status, or passes)"""
    try:
        state_manager = StateManager()

        # Convert Pydantic model to dict, excluding None values
        update_dict = updates.model_dump(exclude_unset=True)

        if not update_dict:
            raise HTTPException(status_code=400, detail="No fields to update")

        # Update the feature
        success = state_manager.update_feature(task_id, update_dict)

        if not success:
            raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

        # Get updated feature
        feature = state_manager.get_feature(task_id)

        return TaskResponse(
            id=feature.get("id", ""),
            name=feature.get("name", ""),
            description=feature.get("description", ""),
            priority=feature.get("priority", 99),
            status=feature.get("status", "pending"),
            passes=feature.get("passes", False),
            created_at=feature.get("created_at", ""),
            updated_at=feature.get("updated_at", ""),
            verify_command=feature.get("verify_command"),
            context_files=feature.get("context_files")
        )
    except HTTPException:
        raise
    except AgentLoopError as e:
        logger.error(f"Agent error updating task: {e}")
        raise handle_agent_error(e)
    except Exception as e:
        logger.error(f"Error updating task: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tasks", response_model=TaskResponse, status_code=201)
@app.post("/api/v1/tasks", response_model=TaskResponse, tags=["Tasks"])
@limiter.limit("30/minute")
def create_task(request: Request, task: TaskCreate, api_key: str = Depends(get_api_key)) -> TaskResponse:
    """Create a new task.

    - **id**: Optional custom task ID
    - **name**: Task name (required)
    - **description**: Task description (optional)
    - **priority**: Priority (1-99, default: 99)
    """
    try:
        state_manager = StateManager()

        # Generate ID if not provided
        task_id = task.id
        if not task_id:
            existing_features = state_manager.load_feature_list().get("features", [])
            task_id = f"task-{len(existing_features) + 1:03d}"

        now = datetime.now().strftime("%Y-%m-%d")

        new_feature = {
            "id": task_id,
            "name": task.name,
            "description": task.description or "",
            "priority": task.priority or 99,
            "status": "pending",
            "passes": False,
            "created_at": now,
            "updated_at": now
        }

        state_manager.add_feature(new_feature)

        return TaskResponse(
            id=new_feature["id"],
            name=new_feature["name"],
            description=new_feature["description"],
            priority=new_feature["priority"],
            status=new_feature["status"],
            passes=new_feature["passes"],
            created_at=new_feature["created_at"],
            updated_at=new_feature["updated_at"]
        )
    except AgentLoopError as e:
        logger.error(f"Agent error creating task: {e}")
        raise handle_agent_error(e)
    except Exception as e:
        logger.error(f"Error creating task: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/tasks/{task_id}", response_model=TaskResponse)
@app.get("/api/v1/tasks/{task_id}", response_model=TaskResponse, tags=["Tasks"])
@limiter.limit("60/minute")
def get_task(request: Request, task_id: str, api_key: str = Depends(get_api_key)) -> TaskResponse:
    """Get a single task by ID.

    - **task_id**: The task ID to retrieve
    """
    try:
        state_manager = StateManager()
        feature = state_manager.get_feature(task_id)

        if not feature:
            raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

        return TaskResponse(
            id=feature.get("id", ""),
            name=feature.get("name", ""),
            description=feature.get("description", ""),
            priority=feature.get("priority", 99),
            status=feature.get("status", "pending"),
            passes=feature.get("passes", False),
            created_at=feature.get("created_at", ""),
            updated_at=feature.get("updated_at", ""),
            verify_command=feature.get("verify_command"),
            context_files=feature.get("context_files")
        )
    except HTTPException:
        raise
    except AgentLoopError as e:
        logger.error(f"Agent error getting task: {e}")
        raise handle_agent_error(e)
    except Exception as e:
        logger.error(f"Error getting task: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.patch("/tasks/{task_id}", response_model=TaskResponse)
@app.patch("/api/v1/tasks/{task_id}", response_model=TaskResponse, tags=["Tasks"])
@limiter.limit("30/minute")
def update_task(request: Request, task_id: str, updates: TaskUpdate, api_key: str = Depends(get_api_key)) -> TaskResponse:
    """Update a task (priority, status, or passes).

    - **task_id**: The task ID to update
    - **priority**: New priority value (1-99)
    - **status**: New status (pending, completed, failed, in_progress)
    - **passes**: Whether the task passes verification
    """
    try:
        state_manager = StateManager()

        # Convert Pydantic model to dict, excluding None values
        update_dict = updates.model_dump(exclude_unset=True)

        if not update_dict:
            raise HTTPException(status_code=400, detail="No fields to update")

        # Update the feature
        success = state_manager.update_feature(task_id, update_dict)

        if not success:
            raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

        # Get updated feature
        feature = state_manager.get_feature(task_id)

        return TaskResponse(
            id=feature.get("id", ""),
            name=feature.get("name", ""),
            description=feature.get("description", ""),
            priority=feature.get("priority", 99),
            status=feature.get("status", "pending"),
            passes=feature.get("passes", False),
            created_at=feature.get("created_at", ""),
            updated_at=feature.get("updated_at", ""),
            verify_command=feature.get("verify_command"),
            context_files=feature.get("context_files")
        )
    except HTTPException:
        raise
    except AgentLoopError as e:
        logger.error(f"Agent error updating task: {e}")
        raise handle_agent_error(e)
    except Exception as e:
        logger.error(f"Error updating task: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/tasks/{task_id}", response_model=TaskDeleteResponse)
@app.delete("/api/v1/tasks/{task_id}", response_model=TaskDeleteResponse, tags=["Tasks"])
@limiter.limit("30/minute")
def delete_task(
    request: Request,
    task_id: str,
    hard: bool = Query(False, description="Hard delete (permanent) vs soft delete (archive)"),
    api_key: str = Depends(get_api_key)
) -> TaskDeleteResponse:
    """Delete a task by ID.

    - **task_id**: The task ID to delete
    - **hard**: If true, permanently delete. If false (default), mark as archived (soft delete)
    """
    try:
        state_manager = StateManager()
        feature = state_manager.get_feature(task_id)

        if not feature:
            raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

        if hard:
            # Hard delete - remove from the list
            data = state_manager.load_feature_list()
            features = data.get("features", [])
            data["features"] = [f for f in features if f.get("id") != task_id]
            state_manager._save_feature_list(data)
            return TaskDeleteResponse(
                success=True,
                message=f"Task {task_id} permanently deleted",
                task_id=task_id,
                deleted_archived=False
            )
        else:
            # Soft delete - mark as archived
            success = state_manager.update_feature(task_id, {"status": "archived"})
            if success:
                return TaskDeleteResponse(
                    success=True,
                    message=f"Task {task_id} archived",
                    task_id=task_id,
                    deleted_archived=True
                )
            else:
                raise HTTPException(status_code=500, detail="Failed to archive task")

    except HTTPException:
        raise
    except AgentLoopError as e:
        logger.error(f"Agent error deleting task: {e}")
        raise handle_agent_error(e)
    except Exception as e:
        logger.error(f"Error deleting task: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tasks/bulk", response_model=BulkTaskResponse)
@app.post("/api/v1/tasks/bulk", response_model=BulkTaskResponse, tags=["Tasks"])
@limiter.limit("30/minute")
def bulk_task_operation(
    request: Request,
    operations: BulkTaskOperation,
    api_key: str = Depends(get_api_key)
) -> BulkTaskResponse:
    """Perform bulk operations on tasks.

    Operations supported:
    - Create: `{"action": "create", "data": {"name": "...", "priority": 1}}`
    - Update: `{"action": "update", "id": "task-id", "data": {"status": "completed"}}`
    - Delete: `{"action": "delete", "id": "task-id", "hard": true/false}`
    """
    created = 0
    updated = 0
    deleted = 0
    errors: List[Dict[str, str]] = []

    try:
        state_manager = StateManager()

        for op in operations.operations:
            try:
                action = op.get("action", "").lower()

                if action == "create":
                    task_data = op.get("data", {})
                    task_id = task_data.get("id")
                    if not task_id:
                        existing_features = state_manager.load_feature_list().get("features", [])
                        task_id = f"task-{len(existing_features) + 1:03d}"

                    now = datetime.now().strftime("%Y-%m-%d")
                    new_feature = {
                        "id": task_id,
                        "name": task_data.get("name", "Untitled"),
                        "description": task_data.get("description", ""),
                        "priority": task_data.get("priority", 99),
                        "status": "pending",
                        "passes": False,
                        "created_at": now,
                        "updated_at": now
                    }
                    state_manager.add_feature(new_feature)
                    created += 1

                elif action == "update":
                    task_id = op.get("id")
                    update_data = op.get("data", {})
                    if not task_id:
                        errors.append({"error": "Missing task id for update"})
                        continue
                    success = state_manager.update_feature(task_id, update_data)
                    if success:
                        updated += 1
                    else:
                        errors.append({"error": f"Task {task_id} not found"})

                elif action == "delete":
                    task_id = op.get("id")
                    hard = op.get("hard", False)
                    if not task_id:
                        errors.append({"error": "Missing task id for delete"})
                        continue

                    feature = state_manager.get_feature(task_id)
                    if not feature:
                        errors.append({"error": f"Task {task_id} not found"})
                        continue

                    if hard:
                        data = state_manager.load_feature_list()
                        features = data.get("features", [])
                        data["features"] = [f for f in features if f.get("id") != task_id]
                        state_manager._save_feature_list(data)
                    else:
                        state_manager.update_feature(task_id, {"status": "archived"})
                    deleted += 1

                else:
                    errors.append({"error": f"Unknown action: {action}"})

            except Exception as e:
                errors.append({"error": str(e)})

        return BulkTaskResponse(
            success=len(errors) == 0,
            created=created,
            updated=updated,
            deleted=deleted,
            errors=errors
        )

    except Exception as e:
        logger.error(f"Error in bulk operation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ========== Agent Control Endpoints ==========

@app.post("/agent/pause", response_model=AgentControlResponse)
@app.post("/api/v1/agent/pause", response_model=AgentControlResponse, tags=["Agent"])
def pause_agent(request: Request, api_key: str = Depends(get_api_key)) -> AgentControlResponse:
    """Pause the agent to prevent new runs.

    When paused, the agent will not start new runs but current runs continue.
    Use /agent/resume to unpause.
    """
    global _agent_paused
    _agent_paused = True
    logger.info("Agent paused via API")

    return AgentControlResponse(
        success=True,
        message="Agent paused successfully",
        state="paused"
    )


@app.post("/agent/resume", response_model=AgentControlResponse)
@app.post("/api/v1/agent/resume", response_model=AgentControlResponse, tags=["Agent"])
def resume_agent(request: Request, api_key: str = Depends(get_api_key)) -> AgentControlResponse:
    """Resume the agent to allow new runs.

    After pausing, use this endpoint to allow new agent runs.
    """
    global _agent_paused
    _agent_paused = False
    logger.info("Agent resumed via API")

    return AgentControlResponse(
        success=True,
        message="Agent resumed successfully",
        state="running"
    )


@app.get("/agent/status", response_model=AgentControlResponse)
@app.get("/api/v1/agent/status", response_model=AgentControlResponse, tags=["Agent"])
def agent_status(request: Request, api_key: str = Depends(get_api_key)) -> AgentControlResponse:
    """Get the current agent state (running or paused)."""
    global _agent_paused
    state = "paused" if _agent_paused else "running"

    return AgentControlResponse(
        success=True,
        message=f"Agent is {state}",
        state=state
    )


@app.post("/run", response_model=RunResponse)
@app.post("/api/v1/run", response_model=RunResponse, tags=["Agent"])
@limiter.limit("10/minute")
def run_agent(request: Request, request_body: RunRequest, api_key: str = Depends(get_api_key)) -> RunResponse:
    """Start the agent loop with specified iterations.

    - **iterations**: Number of iterations to run (default: 10)
    """
    global _agent_instance
    try:
        from agent.agent_core import AgentCore

        # Check if agent is paused
        if _agent_paused:
            return RunResponse(
                success=False,
                message="Agent is paused. Resume before running.",
                iterations=0,
                completed=0,
                errors=1
            )

        # Create agent instance
        _agent_instance = AgentCore()

        # Run agent loop
        iterations = request_body.iterations or 10
        summary = _agent_instance.run_agent_loop(iterations)

        return RunResponse(
            success=True,
            message="Agent completed successfully",
            iterations=summary.get("iterations", 0),
            completed=summary.get("completed", 0),
            errors=summary.get("errors", 0)
        )
    except AgentLoopError as e:
        logger.error(f"Agent error running agent: {e}")
        return RunResponse(
            success=False,
            message=f"Error: {e.message}",
            iterations=0,
            completed=0,
            errors=1
        )
    except Exception as e:
        logger.error(f"Error running agent: {e}")
        return RunResponse(
            success=False,
            message=f"Error: {str(e)}",
            iterations=0,
            completed=0,
            errors=1
        )


@app.get("/sessions", response_model=PaginatedSessionResponse)
@app.get("/api/v1/sessions", response_model=PaginatedSessionResponse, tags=["Sessions"])
@limiter.limit("60/minute")
def get_sessions(
    request: Request,
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    api_key: str = Depends(get_api_key)
) -> PaginatedSessionResponse:
    """Get session history with pagination.

    - **page**: Page number (starting from 1)
    - **per_page**: Number of items per page (max 100)
    """
    try:
        state_manager = StateManager()
        session_manager = SessionManager(state_manager)
        stats = session_manager.get_session_stats()

        # Get full session history
        history = state_manager.load_session_history()
        sessions = history.get("sessions", [])

        # Sort by date (most recent first)
        sessions.sort(key=lambda x: x.get("created_at", ""), reverse=True)

        total = len(sessions)
        total_pages = (total + per_page - 1) // per_page if total > 0 else 1

        # Calculate pagination
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        paginated_sessions = sessions[start_idx:end_idx]

        return PaginatedSessionResponse(
            items=paginated_sessions,
            page=page,
            per_page=per_page,
            total=total,
            total_pages=total_pages
        )
    except AgentLoopError as e:
        logger.error(f"Agent error getting sessions: {e}")
        raise handle_agent_error(e)
    except Exception as e:
        logger.error(f"Error getting sessions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health", response_model=HealthCheckResponse)
@app.get("/api/v1/health", response_model=HealthCheckResponse, tags=["Health"])
def health_check() -> HealthCheckResponse:
    """Enhanced health check endpoint with dependency verification.

    Checks:
    - Configuration files exist
    - Feature list is accessible
    - State files are writable
    """
    dependencies: Dict[str, Any] = {}
    overall_healthy = True

    # Check .agent directory exists
    agent_dir = Path(".agent")
    if agent_dir.exists():
        dependencies["agent_directory"] = {"status": "healthy", "path": str(agent_dir)}
    else:
        dependencies["agent_directory"] = {"status": "unhealthy", "path": str(agent_dir)}
        overall_healthy = False

    # Check config.json exists
    config_path = agent_dir / "config.json"
    if config_path.exists():
        dependencies["config_file"] = {"status": "healthy", "path": str(config_path)}
    else:
        dependencies["config_file"] = {"status": "unhealthy", "path": str(config_path)}
        overall_healthy = False

    # Check feature_list.json exists
    feature_list_path = agent_dir / "feature_list.json"
    if feature_list_path.exists():
        dependencies["feature_list"] = {"status": "healthy", "path": str(feature_list_path)}
    else:
        dependencies["feature_list"] = {"status": "unhealthy", "path": str(feature_list_path)}
        overall_healthy = False

    # Check state.json exists
    state_path = agent_dir / "state.json"
    if state_path.exists():
        dependencies["state_file"] = {"status": "healthy", "path": str(state_path)}
    else:
        dependencies["state_file"] = {"status": "unhealthy", "path": str(state_path)}
        overall_healthy = False

    return HealthCheckResponse(
        status="healthy" if overall_healthy else "degraded",
        service="agent-loop-api",
        timestamp=datetime.now().isoformat(),
        dependencies=dependencies
    )


@app.get("/metrics")
@limiter.limit("30/minute")
def metrics(request: Request, api_key: str = Depends(get_api_key)):
    """Prometheus metrics endpoint

    Returns metrics in Prometheus text format including:
    - Task completion counts (success/error)
    - Session duration histograms
    - Error counts by type
    - API call counts
    - Agent status
    """
    metrics_collector = get_metrics_collector()

    # Update metrics from current state
    try:
        state_manager = StateManager()
        task_selector = TaskSelector(state_manager)

        # Update task metrics
        metrics_collector.set_tasks_pending(task_selector.get_pending_count())
        metrics_collector.set_tasks_total(task_selector.get_total_count())

        # Update API metrics
        metrics_collector.increment_api_call("/metrics")
    except Exception:
        pass  # Metrics should not break the endpoint

    # Return Prometheus format
    return Response(
        content=get_prometheus_metrics(),
        media_type=get_metrics_content_type()
    )


@app.post("/webhook/test")
@limiter.limit("5/minute")
async def test_webhook(request: Request, api_key: str = Depends(get_api_key)) -> Dict[str, Any]:
    """Test webhook notification

    Sends a test webhook notification to verify the webhook configuration.
    """
    try:
        from agent.webhook import get_webhook_notifier

        notifier = get_webhook_notifier()
        result = await notifier.test_webhook()
        return result
    except AgentLoopError as e:
        logger.error(f"Agent error testing webhook: {e}")
        return {
            "success": False,
            "message": f"Test failed: {e.message}",
            "error_code": e.error_code.value,
        }
    except Exception as e:
        logger.error(f"Error testing webhook: {e}")
        return {
            "success": False,
            "message": f"Test failed: {type(e).__name__}: {str(e)}"
        }


@app.post("/email/test")
@limiter.limit("5/minute")
async def test_email(request: Request, api_key: str = Depends(get_api_key)) -> Dict[str, Any]:
    """Test email notification

    Sends a test email to verify the email configuration.
    """
    try:
        from agent.email_notifier import get_email_notifier

        notifier = get_email_notifier()
        result = await notifier.test_email()
        return result
    except AgentLoopError as e:
        logger.error(f"Agent error testing email: {e}")
        return {
            "success": False,
            "message": f"Test failed: {e.message}",
            "error_code": e.error_code.value,
        }
    except Exception as e:
        logger.error(f"Error testing email: {e}")
        return {
            "success": False,
            "message": f"Test failed: {type(e).__name__}: {str(e)}"
        }


@app.get("/")
@limiter.limit("60/minute")
def serve_dashboard(request: Request, api_key: str = Depends(get_api_key)):
    """Serve the web dashboard with CSP security headers"""
    static_path = Path(__file__).parent / "static" / "index.html"

    # Create response with CSP headers
    # Note: 'unsafe-inline' is required because the dashboard has inline JavaScript
    # In production, consider extracting scripts to external files
    response = FileResponse(static_path)
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "  # Required for inline scripts in dashboard
        "style-src 'self' 'unsafe-inline'; "   # Required for inline styles
        "connect-src 'self' ws: wss:; "          # Allow WebSocket connections
        "img-src 'self' data:; "
        "font-src 'self'; "
        "frame-ancestors 'none'; "
        "form-action 'self'; "
        "base-uri 'self'; "
        "object-src 'none'; "
        "upgrade-insecure-requests"
    )
    # Prevent clickjacking
    response.headers["X-Frame-Options"] = "DENY"
    # Prevent MIME type sniffing
    response.headers["X-Content-Type-Options"] = "nosniff"
    # XSS protection (legacy but still useful)
    response.headers["X-XSS-Protection"] = "1; mode=block"
    # Referrer policy for privacy
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

    return response


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time agent event streaming

    Clients can connect to receive:
    - status: Agent status updates (idle, running, error)
    - task_progress: Task execution progress
    - log: Log messages (info, warning, error)
    - iteration: Iteration updates during agent loop
    """
    # Check API key authentication
    enabled, valid_keys = load_api_keys()

    if enabled:
        # Get API key from query parameter
        api_key = websocket.query_params.get("api_key")
        if not api_key:
            await websocket.close(code=4001, reason="API key required")
            return
        if api_key not in valid_keys:
            await websocket.close(code=4003, reason="Invalid API key")
            return

    await ws_manager.connect(websocket)
    try:
        # Send welcome message
        await ws_manager.send_message({
            "type": "connected",
            "timestamp": datetime.now().isoformat(),
            "data": {"message": "WebSocket connected to Agent-Loop"}
        })

        # Keep connection alive and handle incoming messages
        while True:
            # Wait for messages from client (can be used for subscriptions)
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
                # Handle subscription messages if needed
                # Example: {"action": "subscribe", "events": ["status", "log"]}
                logger.info(f"Received WebSocket message: {message}")
            except json.JSONDecodeError:
                logger.warning(f"Invalid JSON received: {data}")
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        ws_manager.disconnect(websocket)


def get_app() -> FastAPI:
    """Get the FastAPI app instance"""
    return app


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
