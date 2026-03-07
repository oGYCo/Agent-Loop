"""REST API Server - FastAPI based API service for Agent-Loop

Provides HTTP endpoints to interact with the Agent-Loop system.
"""

import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from agent.state_manager import StateManager
from agent.task_selector import TaskSelector
from agent.session_manager import SessionManager
from agent.git_helper import GitHelper

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
def get_status() -> StatusResponse:
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
def get_tasks(status_filter: Optional[str] = None) -> List[TaskResponse]:
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
def create_task(task: TaskCreate) -> TaskResponse:
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
def run_agent(request: RunRequest) -> RunResponse:
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
def get_sessions() -> SessionResponse:
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


def get_app() -> FastAPI:
    """Get the FastAPI app instance"""
    return app


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
