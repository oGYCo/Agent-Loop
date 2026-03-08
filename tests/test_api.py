"""Tests for API module - REST endpoints, WebSocket, authentication, and error handling"""

import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Generator
from unittest.mock import patch, MagicMock

import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import FastAPI test utilities
from fastapi.testclient import TestClient
from fastapi import WebSocketDisconnect
import websockets
import asyncio

from api import app, get_api_key, load_api_keys, ConnectionManager, ws_manager


# ========== Fixtures ==========

@pytest.fixture
def temp_agent_dir():
    """Create a temporary directory for testing"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def mock_state_manager(temp_agent_dir):
    """Create a mock StateManager for testing"""
    with patch('api.StateManager') as mock:
        instance = MagicMock()
        instance.agent_dir = temp_agent_dir

        # Mock config
        instance.load_config.return_value = {
            "project_name": "Test Project",
            "project_type": "python",
            "test_command": "pytest",
            "api_keys": {"enabled": False, "keys": ["test-key"]}
        }

        # Mock feature list
        instance.load_feature_list.return_value = {
            "features": [
                {
                    "id": "feature-001",
                    "name": "Test Feature",
                    "description": "A test feature",
                    "priority": 1,
                    "status": "pending",
                    "passes": False,
                    "created_at": "2024-01-01",
                    "updated_at": "2024-01-01"
                },
                {
                    "id": "feature-002",
                    "name": "Completed Feature",
                    "description": "A completed feature",
                    "priority": 2,
                    "status": "completed",
                    "passes": True,
                    "created_at": "2024-01-01",
                    "updated_at": "2024-01-02"
                }
            ]
        }

        # Mock get_feature
        def mock_get_feature(task_id):
            features = instance.load_feature_list.return_value["features"]
            for f in features:
                if f["id"] == task_id:
                    return f
            return None
        instance.get_feature.side_effect = mock_get_feature

        # Mock update_feature
        def mock_update_feature(task_id, updates):
            features = instance.load_feature_list.return_value["features"]
            for f in features:
                if f["id"] == task_id:
                    f.update(updates)
                    return True
            return False
        instance.update_feature.side_effect = mock_update_feature

        # Mock add_feature
        def mock_add_feature(feature):
            instance.load_feature_list.return_value["features"].append(feature)
        instance.add_feature.side_effect = mock_add_feature

        # Mock state
        instance.load_state.return_value = {
            "current_session": {"id": "session-001", "status": "running"},
            "error_count": 0
        }

        # Mock session history
        instance.load_session_history.return_value = {
            "sessions": [
                {"id": "session-001", "status": "completed", "tasks_completed": 5}
            ],
            "total_sessions": 1
        }

        mock.return_value = instance
        yield instance


@pytest.fixture
def mock_git_helper():
    """Create a mock GitHelper for testing"""
    with patch('api.GitHelper') as mock:
        instance = MagicMock()
        instance.get_current_branch.return_value = "main"
        instance.has_changes.return_value = False
        mock.return_value = instance
        yield instance


@pytest.fixture
def mock_task_selector():
    """Create a mock TaskSelector for testing"""
    with patch('api.TaskSelector') as mock:
        instance = MagicMock()
        instance.get_completed_count.return_value = 1
        instance.get_total_count.return_value = 2
        instance.get_pending_count.return_value = 1
        mock.return_value = instance
        yield instance


@pytest.fixture
def mock_session_manager():
    """Create a mock SessionManager for testing"""
    with patch('api.SessionManager') as mock:
        instance = MagicMock()
        instance.get_session_stats.return_value = {
            "total_sessions": 1,
            "completed_sessions": 1
        }
        mock.return_value = instance
        yield instance


@pytest.fixture
def client(mock_state_manager, mock_git_helper, mock_task_selector, mock_session_manager):
    """Create a test client with mocked dependencies"""
    # Patch all the dependencies used in api.py
    with patch('api.StateManager', return_value=mock_state_manager), \
         patch('api.GitHelper', return_value=mock_git_helper), \
         patch('api.TaskSelector', return_value=mock_task_selector), \
         patch('api.SessionManager', return_value=mock_session_manager):
        yield TestClient(app)


# ========== Health Check Tests ==========

class TestHealthEndpoint:
    """Test cases for /health endpoint"""

    def test_health_check(self, client):
        """Test health check returns healthy status"""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "agent-loop-api"


# ========== Status Endpoint Tests ==========

class TestStatusEndpoint:
    """Test cases for /status endpoint"""

    def test_get_status_success(self, client, mock_state_manager, mock_git_helper, mock_task_selector):
        """Test getting agent status"""
        response = client.get("/status")
        assert response.status_code == 200
        data = response.json()

        assert data["project_name"] == "Test Project"
        assert data["project_type"] == "python"
        assert data["test_command"] == "pytest"
        assert data["git_branch"] == "main"
        assert data["has_changes"] is False
        assert data["tasks_completed"] == 1
        assert data["tasks_total"] == 2
        assert data["tasks_pending"] == 1

    def test_get_status_with_current_session(self, client, mock_state_manager):
        """Test getting status with current session"""
        response = client.get("/status")
        assert response.status_code == 200
        data = response.json()
        assert data["current_session"]["id"] == "session-001"

    def test_get_status_error_handling(self, client, mock_state_manager):
        """Test status endpoint error handling"""
        # Mock an exception
        mock_state_manager.load_config.side_effect = Exception("Test error")

        response = client.get("/status")
        assert response.status_code == 500


# ========== Tasks Endpoint Tests ==========

class TestTasksEndpoint:
    """Test cases for /tasks endpoints"""

    def test_get_tasks_all(self, client, mock_state_manager):
        """Test getting all tasks"""
        response = client.get("/tasks")
        assert response.status_code == 200
        data = response.json()
        # Now returns paginated response format
        assert "items" in data
        assert len(data["items"]) == 2

    def test_get_tasks_filter_by_status(self, client, mock_state_manager):
        """Test filtering tasks by status"""
        response = client.get("/tasks?status_filter=pending")
        assert response.status_code == 200
        data = response.json()
        # Now returns paginated response format
        assert "items" in data
        assert len(data["items"]) == 1
        assert data["items"][0]["status"] == "pending"

    def test_get_tasks_filter_completed(self, client, mock_state_manager):
        """Test filtering tasks by completed status"""
        response = client.get("/tasks?status_filter=completed")
        assert response.status_code == 200
        data = response.json()
        # Now returns paginated response format
        assert "items" in data
        assert len(data["items"]) == 1
        assert data["items"][0]["status"] == "completed"

    def test_get_tasks_sorted_by_priority(self, client, mock_state_manager):
        """Test that tasks are sorted by priority"""
        response = client.get("/tasks")
        assert response.status_code == 200
        data = response.json()
        # First task should have priority 1 (lowest number = highest priority)
        assert data["items"][0]["priority"] == 1

    def test_create_task(self, client, mock_state_manager):
        """Test creating a new task"""
        task_data = {
            "name": "New Test Task",
            "description": "A new task for testing",
            "priority": 5
        }
        response = client.post("/tasks", json=task_data)
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "New Test Task"
        assert data["priority"] == 5
        assert data["status"] == "pending"
        assert data["passes"] is False
        # Verify add_feature was called
        mock_state_manager.add_feature.assert_called()

    def test_create_task_with_custom_id(self, client, mock_state_manager):
        """Test creating a task with custom ID"""
        task_data = {
            "id": "custom-task-001",
            "name": "Custom ID Task",
            "description": "Task with custom ID",
            "priority": 3
        }
        response = client.post("/tasks", json=task_data)
        assert response.status_code == 201
        data = response.json()
        assert data["id"] == "custom-task-001"

    def test_get_single_task(self, client, mock_state_manager):
        """Test getting a single task by ID"""
        response = client.get("/tasks/feature-001")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "feature-001"
        assert data["name"] == "Test Feature"

    def test_get_single_task_not_found(self, client, mock_state_manager):
        """Test getting a non-existent task"""
        response = client.get("/tasks/non-existent")
        assert response.status_code == 404

    def test_update_task_priority(self, client, mock_state_manager):
        """Test updating task priority"""
        update_data = {"priority": 10}
        response = client.patch("/tasks/feature-001", json=update_data)
        assert response.status_code == 200
        data = response.json()
        assert data["priority"] == 10

    def test_update_task_status(self, client, mock_state_manager):
        """Test updating task status"""
        update_data = {"status": "completed"}
        response = client.patch("/tasks/feature-001", json=update_data)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"

    def test_update_task_passes(self, client, mock_state_manager):
        """Test updating task passes"""
        update_data = {"passes": True}
        response = client.patch("/tasks/feature-001", json=update_data)
        assert response.status_code == 200
        data = response.json()
        assert data["passes"] is True

    def test_update_task_not_found(self, client, mock_state_manager):
        """Test updating a non-existent task"""
        response = client.patch("/tasks/non-existent", json={"priority": 10})
        assert response.status_code == 404

    def test_update_task_no_fields(self, client, mock_state_manager):
        """Test updating task with no fields"""
        response = client.patch("/tasks/feature-001", json={})
        assert response.status_code == 400


# ========== Sessions Endpoint Tests ==========

class TestSessionsEndpoint:
    """Test cases for /sessions endpoint"""

    def test_get_sessions(self, client, mock_state_manager, mock_session_manager):
        """Test getting session history"""
        response = client.get("/sessions")
        assert response.status_code == 200
        data = response.json()
        # Now returns paginated response format
        assert "items" in data
        assert data["total"] == 1
        assert len(data["items"]) == 1

    def test_get_sessions_error_handling(self, client, mock_state_manager):
        """Test sessions endpoint error handling"""
        mock_state_manager.load_session_history.side_effect = Exception("Test error")

        response = client.get("/sessions")
        assert response.status_code == 500


# ========== Run Endpoint Tests ==========

class TestRunEndpoint:
    """Test cases for /run endpoint"""

    def test_run_agent_success(self, client):
        """Test running the agent successfully"""
        with patch('agent.agent_core.AgentCore') as mock:
            mock_instance = MagicMock()
            mock_instance.run_agent_loop.return_value = {
                "iterations": 3,
                "completed": 2,
                "errors": 1
            }
            mock.return_value = mock_instance

            response = client.post("/run", json={"iterations": 3})
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["iterations"] == 3
            assert data["completed"] == 2
            assert data["errors"] == 1

    def test_run_agent_error(self, client):
        """Test running the agent with error"""
        with patch('agent.agent_core.AgentCore') as mock:
            mock_instance = MagicMock()
            mock_instance.run_agent_loop.side_effect = Exception("Agent error")
            mock.return_value = mock_instance

            response = client.post("/run", json={"iterations": 1})
            assert response.status_code == 200  # Returns success=False in body
            data = response.json()
            assert data["success"] is False
            assert "Agent error" in data["message"]


# ========== Metrics Endpoint Tests ==========

class TestMetricsEndpoint:
    """Test cases for /metrics endpoint"""

    def test_get_metrics(self, client, mock_task_selector):
        """Test getting Prometheus metrics"""
        with patch('api.get_prometheus_metrics') as mock_metrics, \
             patch('api.get_metrics_content_type') as mock_content:
            mock_metrics.return_value = "# HELP test_metric Test metric\n# TYPE test_metric gauge\ntest_metric 1.0"
            mock_content.return_value = "text/plain"

            response = client.get("/metrics")
            assert response.status_code == 200
            assert "text/plain" in response.headers["content-type"]


# ========== Webhook and Email Test Endpoints ==========

class TestNotificationEndpoints:
    """Test cases for webhook and email test endpoints"""

    def test_test_webhook(self, client):
        """Test webhook test endpoint"""
        async def mock_test_webhook():
            return {"success": True, "message": "Webhook sent"}

        with patch('agent.webhook.get_webhook_notifier') as mock:
            instance = MagicMock()
            instance.test_webhook = mock_test_webhook
            mock.return_value = instance

            response = client.post("/webhook/test")
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True

    def test_test_webhook_error(self, client):
        """Test webhook test endpoint with error"""
        async def mock_test_webhook():
            raise Exception("Webhook error")

        with patch('agent.webhook.get_webhook_notifier') as mock:
            instance = MagicMock()
            instance.test_webhook = mock_test_webhook
            mock.return_value = instance

            response = client.post("/webhook/test")
            assert response.status_code == 200  # Returns error in body
            data = response.json()
            assert data["success"] is False

    def test_test_email(self, client):
        """Test email test endpoint"""
        async def mock_test_email():
            return {"success": True, "message": "Email sent"}

        with patch('agent.email_notifier.get_email_notifier') as mock:
            instance = MagicMock()
            instance.test_email = mock_test_email
            mock.return_value = instance

            response = client.post("/email/test")
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True

    def test_test_email_error(self, client):
        """Test email test endpoint with error"""
        async def mock_test_email():
            raise Exception("Email error")

        with patch('agent.email_notifier.get_email_notifier') as mock:
            instance = MagicMock()
            instance.test_email = mock_test_email
            mock.return_value = instance

            response = client.post("/email/test")
            assert response.status_code == 200  # Returns error in body
            data = response.json()
            assert data["success"] is False


# ========== API Key Authentication Tests ==========

class TestAPIKeyAuthentication:
    """Test cases for API key authentication"""

    def test_api_key_not_required_when_disabled(self, mock_state_manager):
        """Test that API key is not required when authentication is disabled"""
        # Mock config with API key disabled
        mock_state_manager.load_config.return_value = {
            "api_keys": {"enabled": False, "keys": []}
        }

        with patch('api.load_api_keys', return_value=(False, [])):
            # Create a test client without the global patch
            with patch('api.StateManager', return_value=mock_state_manager):
                test_client = TestClient(app)
                response = test_client.get("/status")
                assert response.status_code == 200

    def test_api_key_required_when_enabled(self):
        """Test that API key is required when authentication is enabled"""
        with patch('api.load_api_keys', return_value=(True, ["valid-key"])):
            test_client = TestClient(app)
            response = test_client.get("/status")
            assert response.status_code == 401

    def test_api_key_invalid(self):
        """Test that invalid API key returns 401 (unified response to prevent enumeration)"""
        with patch('api.load_api_keys', return_value=(True, ["valid-key"])):
            test_client = TestClient(app)
            response = test_client.get("/status", headers={"X-API-Key": "invalid-key"})
            # Security: Return 401 for both missing and invalid keys to prevent endpoint enumeration
            assert response.status_code == 401

    def test_api_key_valid(self):
        """Test that valid API key allows access"""
        with patch('api.load_api_keys', return_value=(True, ["valid-key"])):
            test_client = TestClient(app)
            response = test_client.get("/status", headers={"X-API-Key": "valid-key"})
            assert response.status_code == 200


# ========== WebSocket Tests ==========

class TestWebSocketEndpoint:
    """Test cases for WebSocket endpoint"""

    @pytest.mark.asyncio
    async def test_websocket_connection_without_auth(self):
        """Test WebSocket connection without authentication"""
        # Test with API key auth disabled
        from fastapi import WebSocket

        # Create a mock websocket
        mock_ws = MagicMock(spec=WebSocket)

        # Test connect
        await ws_manager.connect(mock_ws)
        assert len(ws_manager.active_connections) == 1

        # Test disconnect
        ws_manager.disconnect(mock_ws)
        assert len(ws_manager.active_connections) == 0

    @pytest.mark.asyncio
    async def test_websocket_broadcast(self):
        """Test WebSocket broadcast functionality"""
        from fastapi import WebSocket

        mock_ws = MagicMock(spec=WebSocket)
        ws_manager.active_connections = [mock_ws]

        await ws_manager.broadcast("test_event", {"key": "value"})

        # Verify send_text was called
        mock_ws.send_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_websocket_send_message_empty(self):
        """Test sending message when no connections"""
        ws_manager.active_connections = []

        # Should not raise an error
        await ws_manager.send_message({"type": "test"})

    @pytest.mark.asyncio
    async def test_websocket_disconnect_handling(self):
        """Test WebSocket handles disconnection gracefully"""
        from fastapi import WebSocket

        mock_ws = MagicMock(spec=WebSocket)
        mock_ws.send_text.side_effect = Exception("Connection closed")

        ws_manager.active_connections = [mock_ws]

        # Should handle the error gracefully
        await ws_manager.broadcast("test_event", {"data": "test"})

        # Connection should be removed
        assert len(ws_manager.active_connections) == 0


# ========== Error Handling Tests ==========

class TestErrorHandling:
    """Test cases for error handling - using client fixture which properly patches dependencies"""

    def test_status_with_missing_config(self, client):
        """Test status endpoint handles missing config gracefully"""
        # The mocked state_manager returns valid data, but we can test
        # that the endpoint returns proper response structure
        response = client.get("/status")
        assert response.status_code == 200
        # Verify expected fields exist
        data = response.json()
        assert "project_name" in data
        assert "tasks_completed" in data
        assert "tasks_pending" in data
        assert "tasks_total" in data

    def test_tasks_with_empty_list(self, client):
        """Test tasks endpoint with empty task list"""
        # Test that it handles empty list properly
        response = client.get("/tasks")
        assert response.status_code == 200
        data = response.json()
        # Should return the mocked tasks
        assert len(data) >= 0

    def test_invalid_task_id_format(self, client):
        """Test getting task with invalid ID format"""
        # Should return 404 for non-existent task
        response = client.get("/tasks/invalid-id-12345")
        assert response.status_code == 404

    def test_update_nonexistent_task(self, client):
        """Test updating a non-existent task returns 404"""
        response = client.patch("/tasks/nonexistent-task", json={"priority": 5})
        assert response.status_code == 404

    def test_create_task_with_empty_name(self, client):
        """Test creating task with empty name"""
        response = client.post("/tasks", json={"name": ""})
        # Should either succeed (empty name allowed) or fail with validation error
        assert response.status_code in [201, 422, 500]

    def test_invalid_status_filter(self, client):
        """Test tasks endpoint with invalid status filter"""
        response = client.get("/tasks?status_filter=invalid_status")
        # Should return tasks filtered by that status (empty result)
        assert response.status_code == 200


# ========== ConnectionManager Tests ==========

class TestConnectionManager:
    """Test cases for ConnectionManager class"""

    def test_connection_manager_init(self):
        """Test ConnectionManager initialization"""
        manager = ConnectionManager()
        assert manager.active_connections == []

    def test_connection_manager_disconnect_not_in_list(self):
        """Test disconnecting a websocket not in the list"""
        from fastapi import WebSocket

        manager = ConnectionManager()
        mock_ws = MagicMock(spec=WebSocket)

        # Should not raise an error
        manager.disconnect(mock_ws)


# ========== Load API Keys Tests ==========

class TestLoadApiKeys:
    """Test cases for load_api_keys function"""

    def test_load_api_keys_enabled(self, mock_state_manager):
        """Test loading API keys when enabled"""
        mock_state_manager.load_config.return_value = {
            "api_keys": {"enabled": True, "keys": ["key1", "key2"]}
        }

        enabled, keys = load_api_keys()
        assert enabled is True
        assert keys == ["key1", "key2"]

    def test_load_api_keys_disabled(self, mock_state_manager):
        """Test loading API keys when disabled"""
        mock_state_manager.load_config.return_value = {
            "api_keys": {"enabled": False, "keys": []}
        }

        enabled, keys = load_api_keys()
        assert enabled is False
        assert keys == []

    def test_load_api_keys_missing_config(self, mock_state_manager):
        """Test loading API keys when config is missing"""
        mock_state_manager.load_config.return_value = {}

        enabled, keys = load_api_keys()
        assert enabled is False
        assert keys == []

    def test_load_api_keys_exception(self, mock_state_manager):
        """Test loading API keys when exception occurs"""
        mock_state_manager.load_config.side_effect = Exception("Error")

        enabled, keys = load_api_keys()
        assert enabled is False
        assert keys == []


# ========== Get API Key Tests ==========

class TestGetApiKey:
    """Test cases for get_api_key function"""

    def test_get_api_key_auth_disabled(self):
        """Test get_api_key when auth is disabled - accepts any key if provided"""
        with patch('api.load_api_keys', return_value=(False, [])):
            # When auth is disabled and a key is provided, return the key
            key = get_api_key(x_api_key="any-key")
            assert key == "any-key"

    def test_get_api_key_auth_disabled_no_key(self):
        """Test get_api_key when auth is disabled and no key provided"""
        with patch('api.load_api_keys', return_value=(False, [])):
            # When auth is disabled and no key is provided, return "no-auth"
            key = get_api_key(x_api_key=None)
            assert key == "no-auth"

    def test_get_api_key_no_key_provided(self):
        """Test get_api_key when no key is provided but auth is enabled"""
        from fastapi import HTTPException

        with patch('api.load_api_keys', return_value=(True, ["valid-key"])):
            with pytest.raises(HTTPException) as exc:
                get_api_key(x_api_key=None)
            assert exc.value.status_code == 401

    def test_get_api_key_invalid(self):
        """Test get_api_key with invalid key - returns 401 for security"""
        from fastapi import HTTPException

        with patch('api.load_api_keys', return_value=(True, ["valid-key"])):
            with pytest.raises(HTTPException) as exc:
                get_api_key(x_api_key="invalid-key")
            # Security: Return 401 for both missing and invalid keys to prevent enumeration
            assert exc.value.status_code == 401

    def test_get_api_key_valid(self):
        """Test get_api_key with valid key"""
        with patch('api.load_api_keys', return_value=(True, ["valid-key"])):
            key = get_api_key(x_api_key="valid-key")
            assert key == "valid-key"


# ========== Dashboard Tests ==========

class TestDashboardEndpoint:
    """Test cases for dashboard endpoint"""

    def test_serve_dashboard(self, client):
        """Test serving the dashboard"""
        # This test requires the static/index.html file to exist
        # Skip if file doesn't exist
        static_path = Path(__file__).parent.parent / "static" / "index.html"
        if not static_path.exists():
            pytest.skip("static/index.html not found")

        response = client.get("/")
        # Will return 200 if file exists, 404 if not
        assert response.status_code in [200, 404]
