"""REST API Server - FastAPI based API service for Agent-Loop

Provides HTTP endpoints to interact with the Agent-Loop system.
"""

import asyncio
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Header, Depends
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from agent.state_manager import StateManager
from agent.task_selector import TaskSelector
from agent.session_manager import SessionManager
from agent.git_helper import GitHelper
from agent.metrics import get_prometheus_metrics, get_metrics_content_type, get_metrics_collector

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Agent-Loop API",
    description="REST API for Agent-Loop autonomous agent system",
    version="1.0.0"
)

# Global state
_agent_instance = None

# ========== API Key Authentication ==========

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
        return False, []


def get_api_key(x_api_key: str = Header(None, description="API key for authentication")) -> str:
    """Validate API key from request header

    Args:
        x_api_key: API key from X-API-Key header

    Returns:
        The validated API key

    Raises:
        HTTPException: If API key is invalid or missing
    """
    enabled, valid_keys = load_api_keys()

    # If API key authentication is not enabled, allow access
    if not enabled:
        return "no-auth"

    # Check if API key is provided
    if not x_api_key:
        raise HTTPException(
            status_code=401,
            detail="API key is required. Set X-API-Key header."
        )

    # Check if API key is valid
    if x_api_key not in valid_keys:
        raise HTTPException(
            status_code=403,
            detail="Invalid API key"
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

class TaskCreate(BaseModel):
    """Task creation request model"""
    id: Optional[str] = None
    name: str
    description: Optional[str] = None
    priority: Optional[int] = 99


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


# ========== API Endpoints ==========

@app.get("/status", response_model=StatusResponse)
def get_status(api_key: str = Depends(get_api_key)) -> StatusResponse:
    """Get Agent status"""
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
    except Exception as e:
        logger.error(f"Error getting status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/tasks", response_model=List[TaskResponse])
def get_tasks(status_filter: Optional[str] = None, api_key: str = Depends(get_api_key)) -> List[TaskResponse]:
    """Get task list, optionally filtered by status"""
    try:
        state_manager = StateManager()
        data = state_manager.load_feature_list()
        features = data.get("features", [])

        # Filter by status if provided
        if status_filter and status_filter != "all":
            features = [f for f in features if f.get("status") == status_filter]

        # Sort by priority
        features.sort(key=lambda x: x.get("priority", 99))

        return [
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
            for f in features
        ]
    except Exception as e:
        logger.error(f"Error getting tasks: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tasks", response_model=TaskResponse, status_code=201)
def create_task(task: TaskCreate, api_key: str = Depends(get_api_key)) -> TaskResponse:
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
    except Exception as e:
        logger.error(f"Error creating task: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/run", response_model=RunResponse)
def run_agent(request: RunRequest, api_key: str = Depends(get_api_key)) -> RunResponse:
    """Start the agent"""
    global _agent_instance
    try:
        from agent.agent_core import AgentCore

        # Create agent instance
        _agent_instance = AgentCore()

        # Run agent loop
        iterations = request.iterations or 10
        summary = _agent_instance.run_agent_loop(iterations)

        return RunResponse(
            success=True,
            message="Agent completed successfully",
            iterations=summary.get("iterations", 0),
            completed=summary.get("completed", 0),
            errors=summary.get("errors", 0)
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


@app.get("/sessions", response_model=SessionResponse)
def get_sessions(api_key: str = Depends(get_api_key)) -> SessionResponse:
    """Get session history"""
    try:
        state_manager = StateManager()
        session_manager = SessionManager(state_manager)
        stats = session_manager.get_session_stats()

        # Get full session history
        history = state_manager.load_session_history()
        sessions = history.get("sessions", [])

        return SessionResponse(
            total_sessions=stats["total_sessions"],
            completed_sessions=stats["completed_sessions"],
            sessions=sessions
        )
    except Exception as e:
        logger.error(f"Error getting sessions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
def health_check() -> Dict[str, str]:
    """Health check endpoint"""
    return {"status": "healthy", "service": "agent-loop-api"}


@app.get("/metrics")
def metrics(api_key: str = Depends(get_api_key)):
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
async def test_webhook(api_key: str = Depends(get_api_key)) -> Dict[str, Any]:
    """Test webhook notification

    Sends a test webhook notification to verify the webhook configuration.
    """
    try:
        from agent.webhook import get_webhook_notifier

        notifier = get_webhook_notifier()
        result = await notifier.test_webhook()
        return result
    except Exception as e:
        logger.error(f"Error testing webhook: {e}")
        return {
            "success": False,
            "message": f"Test failed: {type(e).__name__}: {str(e)}"
        }


@app.get("/")
def serve_dashboard(api_key: str = Depends(get_api_key)):
    """Serve the web dashboard"""
    static_path = Path(__file__).parent / "static" / "index.html"
    return FileResponse(static_path)


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
