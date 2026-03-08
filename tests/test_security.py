"""Security tests for API module - testing security features

These tests verify:
- Rate limiting
- Input validation
- XSS sanitization
- CSP headers
- File permissions
- Authentication security
"""

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi.testclient import TestClient
from fastapi import HTTPException

from api import (
    app,
    get_api_key,
    load_api_keys,
    load_cors_config,
    load_rate_limit_config,
    sanitize_for_html,
    sanitize_task_response,
    MAX_TASK_NAME_LENGTH,
    MAX_DESCRIPTION_LENGTH,
)
from agent.state_manager import StateManager


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
        instance.load_config.return_value = {
            "project_name": "Test Project",
            "project_type": "python",
            "test_command": "pytest",
            "api_keys": {"enabled": False, "keys": ["test-key"]},
            "rate_limit": {
                "enabled": True,
                "default_limit": "100/minute"
            },
            "cors": {
                "enabled": True,
                "allow_origins": []
            }
        }
        instance.load_feature_list.return_value = {"features": []}
        instance.load_state.return_value = {"current_session": None, "error_count": 0}
        mock.return_value = instance
        yield instance


@pytest.fixture
def client(mock_state_manager):
    """Create a test client with mocked dependencies"""
    with patch('api.StateManager', return_value=mock_state_manager), \
         patch('api.GitHelper') as mock_git, \
         patch('api.TaskSelector') as mock_task, \
         patch('api.SessionManager') as mock_session:
        mock_git.return_value.get_current_branch.return_value = "main"
        mock_git.return_value.has_changes.return_value = False
        mock_task.return_value.get_completed_count.return_value = 0
        mock_task.return_value.get_total_count.return_value = 0
        mock_task.return_value.get_pending_count.return_value = 0
        mock_session.return_value.get_session_stats.return_value = {
            "total_sessions": 0,
            "completed_sessions": 0
        }
        yield TestClient(app)


# ========== Rate Limiting Tests ==========

class TestRateLimiting:
    """Test cases for rate limiting"""

    def test_rate_limit_config_loading(self, mock_state_manager):
        """Test loading rate limit configuration"""
        mock_state_manager.load_config.return_value = {
            "rate_limit": {
                "enabled": True,
                "default_limit": "50/minute",
                "endpoints": {"/run": "5/minute"}
            }
        }

        config = load_rate_limit_config()
        assert config["enabled"] is True
        assert config["default_limit"] == "50/minute"

    def test_rate_limit_config_defaults(self, mock_state_manager):
        """Test rate limit config defaults when not provided"""
        mock_state_manager.load_config.return_value = {}

        config = load_rate_limit_config()
        assert config["enabled"] is True
        assert config["default_limit"] == "100/minute"


# ========== CORS Tests ==========

class TestCORS:
    """Test cases for CORS configuration"""

    def test_cors_config_strict_mode(self, mock_state_manager):
        """Test CORS in strict mode (same-origin only)"""
        mock_state_manager.load_config.return_value = {
            "cors": {
                "enabled": True,
                "allow_origins": [],  # Empty = same-origin only
                "allow_credentials": False
            }
        }

        config = load_cors_config()
        assert config["enabled"] is True
        assert config["allow_origins"] == []

    def test_cors_config_custom_origins(self, mock_state_manager):
        """Test CORS with custom allowed origins"""
        mock_state_manager.load_config.return_value = {
            "cors": {
                "enabled": True,
                "allow_origins": ["https://example.com"],
                "allow_credentials": True
            }
        }

        config = load_cors_config()
        assert config["enabled"] is True
        assert "https://example.com" in config["allow_origins"]
        assert config["allow_credentials"] is True

    def test_cors_disabled(self, mock_state_manager):
        """Test CORS when disabled"""
        mock_state_manager.load_config.return_value = {
            "cors": {
                "enabled": False
            }
        }

        config = load_cors_config()
        assert config["enabled"] is False


# ========== Input Validation Tests ==========

class TestInputValidation:
    """Test cases for input validation"""

    def test_task_name_max_length(self):
        """Test that task name length is validated"""
        from api import TaskCreate
        from pydantic import ValidationError

        # Create a name that's too long
        long_name = "a" * (MAX_TASK_NAME_LENGTH + 1)

        with pytest.raises(ValidationError) as exc:
            TaskCreate(name=long_name)

        assert "cannot exceed" in str(exc.value)

    def test_task_description_max_length(self):
        """Test that description length is validated"""
        from api import TaskCreate
        from pydantic import ValidationError

        # Create a description that's too long
        long_desc = "a" * (MAX_DESCRIPTION_LENGTH + 1)

        with pytest.raises(ValidationError) as exc:
            TaskCreate(name="Valid Name", description=long_desc)

        assert "cannot exceed" in str(exc.value)

    def test_task_name_valid_characters(self):
        """Test that task name accepts valid characters"""
        from api import TaskCreate

        # Valid names
        task = TaskCreate(name="Task 123")
        assert task.name == "Task 123"

        task = TaskCreate(name="Task-Name_Valid")
        assert task.name == "Task-Name_Valid"

    def test_task_name_invalid_characters(self):
        """Test that task name rejects invalid characters"""
        from api import TaskCreate
        from pydantic import ValidationError

        # Invalid name with special characters
        with pytest.raises(ValidationError):
            TaskCreate(name="Task<script>alert(1)</script>")

    def test_task_priority_bounds(self):
        """Test priority validation bounds"""
        from api import TaskCreate
        from pydantic import ValidationError

        # Priority too low
        with pytest.raises(ValidationError):
            TaskCreate(name="Test", priority=0)

        # Priority too high
        with pytest.raises(ValidationError):
            TaskCreate(name="Test", priority=100)

    def test_task_id_format(self):
        """Test task ID format validation"""
        from api import TaskCreate
        from pydantic import ValidationError

        # Valid ID
        task = TaskCreate(id="task-001", name="Test")
        assert task.id == "task-001"

        # Invalid ID with spaces
        with pytest.raises(ValidationError):
            TaskCreate(id="task 001", name="Test")

    def test_status_validation(self):
        """Test status field validation in TaskUpdate"""
        from api import TaskUpdate
        from pydantic import ValidationError

        # Valid status
        update = TaskUpdate(status="completed")
        assert update.status == "completed"

        # Invalid status
        with pytest.raises(ValidationError):
            TaskUpdate(status="invalid_status")


# ========== XSS Sanitization Tests ==========

class TestXSSSanitization:
    """Test cases for XSS sanitization"""

    def test_sanitize_html_basic(self):
        """Test basic HTML sanitization"""
        # Should strip HTML tags using bleach
        result = sanitize_for_html("<script>alert('xss')</script>Test")
        # Bleach strips tags but may keep text content
        assert "<script>" not in result
        assert "</script>" not in result

    def test_sanitize_html_none(self):
        """Test sanitizing None input"""
        result = sanitize_for_html(None)
        assert result == ""

    def test_sanitize_task_response(self):
        """Test task response sanitization"""
        task = {
            "id": "test-001",
            "name": "<script>alert(1)</script>Test",
            "description": "<img src=x onerror=alert(1)>",
            "status": "pending"
        }

        sanitized = sanitize_task_response(task)

        # HTML should be stripped
        assert "<script>" not in sanitized["name"]
        assert "<img" not in sanitized["description"]
        # Original fields should be preserved
        assert sanitized["id"] == "test-001"
        assert sanitized["status"] == "pending"


# ========== CSP Headers Tests ==========

class TestCSPHeaders:
    """Test cases for CSP and security headers"""

    def test_dashboard_csp_headers(self, client):
        """Test that dashboard includes CSP headers"""
        response = client.get("/")

        # Check for security headers
        assert "Content-Security-Policy" in response.headers
        csp = response.headers["Content-Security-Policy"]
        assert "default-src 'self'" in csp
        assert "script-src 'self'" in csp

    def test_dashboard_x_frame_options(self, client):
        """Test X-Frame-Options header"""
        response = client.get("/")

        assert "X-Frame-Options" in response.headers
        assert response.headers["X-Frame-Options"] == "DENY"

    def test_dashboard_x_content_type_options(self, client):
        """Test X-Content-Type-Options header"""
        response = client.get("/")

        assert "X-Content-Type-Options" in response.headers
        assert response.headers["X-Content-Type-Options"] == "nosniff"


# ========== File Permission Tests ==========

class TestFilePermissions:
    """Test cases for secure file permissions"""

    def test_state_manager_sets_permissions(self, temp_agent_dir):
        """Test that StateManager sets secure file permissions"""
        # Patch StateManager to use temp directory
        with patch('agent.state_manager.StateManager.__init__', return_value=None):
            from agent.state_manager import StateManager
            sm = StateManager.__new__(StateManager)
            sm.agent_dir = Path(temp_agent_dir)
            sm.feature_list_path = Path(temp_agent_dir) / "feature_list.json"
            sm.state_path = Path(temp_agent_dir) / "state.json"
            sm.session_history_path = Path(temp_agent_dir) / "session_history.json"
            sm.config_path = Path(temp_agent_dir) / "config.json"
            sm.progress_path = Path(temp_agent_dir) / "progress.txt"

            # Save a feature list
            sm.save_feature_list({"features": []})

            # Check file permissions
            if os.name != 'nt':  # Skip on Windows
                stat_info = os.stat(sm.feature_list_path)
                mode = stat_info.st_mode & 0o777
                # Should be 0o600 (owner read/write only)
                assert mode == 0o600, f"Expected 0o600, got {oct(mode)}"


# ========== Authentication Security Tests ==========

class TestAuthenticationSecurity:
    """Test cases for authentication security"""

    def test_unified_error_response(self):
        """Test that both missing and invalid keys return 401"""
        with patch('api.load_api_keys', return_value=(True, ["valid-key"])):
            # Missing key
            with pytest.raises(HTTPException) as exc:
                get_api_key(x_api_key=None)
            assert exc.value.status_code == 401

            # Invalid key
            with pytest.raises(HTTPException) as exc:
                get_api_key(x_api_key="invalid-key")
            assert exc.value.status_code == 401

            # Both should have same error message
            assert exc.value.detail == "Authentication required"

    def test_valid_key_allows_access(self):
        """Test that valid key allows access"""
        with patch('api.load_api_keys', return_value=(True, ["valid-key"])):
            key = get_api_key(x_api_key="valid-key")
            assert key == "valid-key"

    def test_auth_disabled_allows_access(self):
        """Test that disabled auth allows access"""
        with patch('api.load_api_keys', return_value=(False, [])):
            # With key provided
            key = get_api_key(x_api_key="any-key")
            assert key == "any-key"

            # Without key
            key = get_api_key(x_api_key=None)
            assert key == "no-auth"


# ========== Integration Tests ==========

class TestSecurityIntegration:
    """Integration tests for security features"""

    def test_health_endpoint_no_auth_required(self, client):
        """Test that health endpoint is accessible without auth"""
        response = client.get("/health")
        assert response.status_code == 200

    def test_protected_endpoint_requires_auth(self, client):
        """Test that protected endpoints require auth when enabled"""
        with patch('api.load_api_keys', return_value=(True, ["valid-key"])):
            response = client.get("/status")
            assert response.status_code == 401

    def test_invalid_task_creation_rejected(self, client):
        """Test that invalid task creation is rejected"""
        # Try to create task with invalid name
        response = client.post("/tasks", json={
            "name": "<script>alert(1)</script>"
        })
        # Should be rejected with validation error
        assert response.status_code == 422
