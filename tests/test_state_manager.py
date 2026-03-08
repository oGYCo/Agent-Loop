"""Tests for StateManager module"""

import json
import os
import tempfile
import pytest
from pathlib import Path

# Add parent directory to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from agent.state_manager import StateManager


class TestStateManager:
    """Test cases for StateManager"""

    @pytest.fixture
    def temp_agent_dir(self):
        """Create a temporary directory for testing"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.fixture
    def state_manager(self, temp_agent_dir):
        """Create StateManager with temporary directory"""
        return StateManager(agent_dir=temp_agent_dir)

    # ========== Feature List Tests ==========

    def test_load_feature_list_empty(self, state_manager):
        """Test loading feature list when file doesn't exist"""
        result = state_manager.load_feature_list()
        assert result == {"features": []}

    def test_save_and_load_feature_list(self, state_manager):
        """Test saving and loading feature list"""
        data = {
            "features": [
                {"id": "feature-001", "name": "Test Feature", "status": "pending"}
            ]
        }
        state_manager.save_feature_list(data)
        result = state_manager.load_feature_list()
        assert result == data

    def test_get_feature(self, state_manager):
        """Test getting a specific feature"""
        data = {
            "features": [
                {"id": "feature-001", "name": "Test Feature", "status": "pending"},
                {"id": "feature-002", "name": "Another Feature", "status": "completed"}
            ]
        }
        state_manager.save_feature_list(data)

        feature = state_manager.get_feature("feature-001")
        assert feature is not None
        assert feature["name"] == "Test Feature"

    def test_get_feature_not_found(self, state_manager):
        """Test getting a non-existent feature"""
        data = {"features": [{"id": "feature-001", "name": "Test"}]}
        state_manager.save_feature_list(data)

        feature = state_manager.get_feature("non-existent")
        assert feature is None

    def test_update_feature(self, state_manager):
        """Test updating a feature"""
        data = {
            "features": [
                {"id": "feature-001", "name": "Test", "status": "pending", "passes": False}
            ]
        }
        state_manager.save_feature_list(data)

        result = state_manager.update_feature("feature-001", {"passes": True, "status": "completed"})
        assert result is True

        feature = state_manager.get_feature("feature-001")
        assert feature["passes"] is True
        assert feature["status"] == "completed"

    def test_update_feature_not_found(self, state_manager):
        """Test updating a non-existent feature"""
        result = state_manager.update_feature("non-existent", {"passes": True})
        assert result is False

    def test_add_feature(self, state_manager):
        """Test adding a new feature"""
        data = {"features": [{"id": "feature-001", "name": "Test"}]}
        state_manager.save_feature_list(data)

        new_feature = {"id": "feature-002", "name": "New Test"}
        state_manager.add_feature(new_feature)

        result = state_manager.load_feature_list()
        assert len(result["features"]) == 2

    # ========== Progress Tests ==========

    def test_load_progress_empty(self, state_manager):
        """Test loading progress when file doesn't exist"""
        result = state_manager.load_progress()
        assert result == ""

    def test_save_and_load_progress(self, state_manager):
        """Test saving and loading progress"""
        content = "Test progress content"
        state_manager.save_progress(content)
        result = state_manager.load_progress()
        assert result == content

    def test_append_progress(self, state_manager):
        """Test appending progress"""
        state_manager.save_progress("Initial ")
        state_manager.append_progress("Added")

        result = state_manager.load_progress()
        assert "Initial" in result
        assert "Added" in result

    def test_save_text_file(self, state_manager):
        """Test saving arbitrary text files atomically."""
        memory_path = Path(state_manager.agent_dir) / "MEMORY.md"
        content = "# Memory\n\nTest content"

        state_manager.save_text_file(memory_path, content)

        assert memory_path.read_text(encoding="utf-8") == content

    # ========== State Tests ==========

    def test_load_state_default(self, state_manager):
        """Test loading state with default values"""
        result = state_manager.load_state()
        assert result["error_count"] == 0
        assert result["last_error"] is None
        assert result["current_task"] is None

    def test_save_and_load_state(self, state_manager):
        """Test saving and loading state"""
        state = {
            "current_task": "feature-001",
            "error_count": 2,
            "last_error": "Test error"
        }
        state_manager.save_state(state)
        result = state_manager.load_state()
        assert result["current_task"] == "feature-001"
        assert result["error_count"] == 2

    def test_update_state(self, state_manager):
        """Test updating state"""
        state_manager.update_state({"current_task": "feature-001"})
        result = state_manager.load_state()
        assert result["current_task"] == "feature-001"

    # ========== Session History Tests ==========

    def test_load_session_history_default(self, state_manager):
        """Test loading session history with default values"""
        result = state_manager.load_session_history()
        assert result == {"sessions": [], "total_sessions": 0}

    def test_save_and_load_session_history(self, state_manager):
        """Test saving and loading session history"""
        data = {
            "sessions": [
                {"id": "session-001", "status": "completed"}
            ],
            "total_sessions": 1
        }
        state_manager.save_session_history(data)
        result = state_manager.load_session_history()
        assert len(result["sessions"]) == 1

    def test_add_session(self, state_manager):
        """Test adding a session"""
        session = {"id": "session-001", "status": "started"}
        state_manager.add_session(session)

        result = state_manager.load_session_history()
        assert len(result["sessions"]) == 1
        assert result["total_sessions"] == 1

    # ========== Config Tests ==========

    def test_load_config_empty(self, state_manager):
        """Test loading config when file doesn't exist"""
        result = state_manager.load_config()
        assert result == {}

    def test_save_and_load_config(self, state_manager):
        """Test saving and loading config"""
        config = {"model": "test-model", "max_errors": 5}
        state_manager.save_config(config)
        result = state_manager.load_config()
        assert result["model"] == "test-model"

    def test_get_config(self, state_manager):
        """Test getting a config value"""
        config = {"model": "test-model"}
        state_manager.save_config(config)

        result = state_manager.get_config("model")
        assert result == "test-model"

        # Test default value
        result = state_manager.get_config("non-existent", "default")
        assert result == "default"

    # ========== Validation Tests ==========

    def test_validate_config_success(self, state_manager):
        """Test config validation with valid config"""
        config = {
            "project_name": "Test Project",
            "project_type": "python",
            "model": "claude-3-5-sonnet-20241022",
            "session_type": "auto",
            "test_command": "pytest",
            "test_pattern": "test_*.py",
            "max_errors_before_intervention": 5,
            "context_window_limit": 100000,
            "documentation_urls": {"main": "https://example.com"}
        }
        result = state_manager.validate_config(config)
        assert result["project_name"] == "Test Project"

    def test_validate_config_missing_field(self, state_manager):
        """Test config validation with missing required field"""
        config = {
            "project_name": "Test Project",
            "project_type": "python"
            # Missing other required fields
        }
        with pytest.raises(Exception) as exc_info:
            state_manager.validate_config(config)
        assert "Missing required field" in str(exc_info.value)

    def test_validate_config_invalid_type(self, state_manager):
        """Test config validation with wrong type"""
        config = {
            "project_name": "Test Project",
            "project_type": "python",
            "model": "claude-3-5-sonnet-20241022",
            "session_type": "auto",
            "test_command": "pytest",
            "test_pattern": "test_*.py",
            "max_errors_before_intervention": "not_an_int",  # Invalid type
            "context_window_limit": 100000,
            "documentation_urls": {"main": "https://example.com"}
        }
        with pytest.raises(Exception) as exc_info:
            state_manager.validate_config(config)
        assert "Invalid type" in str(exc_info.value)

    def test_validate_config_invalid_value(self, state_manager):
        """Test config validation with invalid value"""
        config = {
            "project_name": "Test Project",
            "project_type": "python",
            "model": "claude-3-5-sonnet-20241022",
            "session_type": "auto",
            "test_command": "pytest",
            "test_pattern": "test_*.py",
            "max_errors_before_intervention": 0,  # Must be > 0
            "context_window_limit": 100000,
            "documentation_urls": {"main": "https://example.com"}
        }
        with pytest.raises(Exception) as exc_info:
            state_manager.validate_config(config)
        assert "must be greater than 0" in str(exc_info.value)

    def test_validate_config_empty_documentation_urls(self, state_manager):
        """Test config validation with empty documentation_urls (now allowed)"""
        config = {
            "project_name": "Test Project",
            "project_type": "python",
            "model": "claude-3-5-sonnet-20241022",
            "session_type": "auto",
            "test_command": "pytest",
            "test_pattern": "test_*.py",
            "max_errors_before_intervention": 5,
            "context_window_limit": 100000,
            "documentation_urls": {}  # Empty - now allowed
        }
        # Empty dictionary should now be accepted
        result = state_manager.validate_config(config)
        assert result["documentation_urls"] == {}

    def test_validate_feature_list_success(self, state_manager):
        """Test feature list validation with valid data"""
        data = {
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
                }
            ]
        }
        result = state_manager.validate_feature_list(data)
        assert len(result["features"]) == 1

    def test_validate_feature_list_missing_features_key(self, state_manager):
        """Test feature list validation with missing features key"""
        data = {"other_key": []}
        with pytest.raises(Exception) as exc_info:
            state_manager.validate_feature_list(data)
        assert "Missing required key" in str(exc_info.value)

    def test_validate_feature_list_invalid_features_type(self, state_manager):
        """Test feature list validation with invalid features type"""
        data = {"features": "not_a_list"}
        with pytest.raises(Exception) as exc_info:
            state_manager.validate_feature_list(data)
        assert "must be a list" in str(exc_info.value)

    def test_validate_feature_list_empty_list(self, state_manager):
        """Test feature list validation with empty features list"""
        data = {"features": []}
        with pytest.raises(Exception) as exc_info:
            state_manager.validate_feature_list(data)
        assert "cannot be empty" in str(exc_info.value)

    def test_validate_feature_list_missing_field(self, state_manager):
        """Test feature list validation with missing required field"""
        data = {
            "features": [
                {
                    "id": "feature-001",
                    "name": "Test Feature"
                    # Missing other required fields
                }
            ]
        }
        with pytest.raises(Exception) as exc_info:
            state_manager.validate_feature_list(data)
        assert "Missing required field" in str(exc_info.value)

    def test_validate_feature_list_invalid_priority(self, state_manager):
        """Test feature list validation with invalid priority"""
        data = {
            "features": [
                {
                    "id": "feature-001",
                    "name": "Test Feature",
                    "description": "A test feature",
                    "priority": 0,  # Must be positive
                    "status": "pending",
                    "passes": False,
                    "created_at": "2024-01-01",
                    "updated_at": "2024-01-01"
                }
            ]
        }
        with pytest.raises(Exception) as exc_info:
            state_manager.validate_feature_list(data)
        assert "priority must be a positive integer" in str(exc_info.value)

    def test_validate_feature_list_invalid_status(self, state_manager):
        """Test feature list validation with invalid status"""
        data = {
            "features": [
                {
                    "id": "feature-001",
                    "name": "Test Feature",
                    "description": "A test feature",
                    "priority": 1,
                    "status": "invalid_status",
                    "passes": False,
                    "created_at": "2024-01-01",
                    "updated_at": "2024-01-01"
                }
            ]
        }
        with pytest.raises(Exception) as exc_info:
            state_manager.validate_feature_list(data)
        assert "status must be one of" in str(exc_info.value)

    def test_validate_feature_list_duplicate_id(self, state_manager):
        """Test feature list validation with duplicate IDs"""
        data = {
            "features": [
                {
                    "id": "feature-001",
                    "name": "Test Feature 1",
                    "description": "A test feature",
                    "priority": 1,
                    "status": "pending",
                    "passes": False,
                    "created_at": "2024-01-01",
                    "updated_at": "2024-01-01"
                },
                {
                    "id": "feature-001",
                    "name": "Test Feature 2",
                    "description": "Another test feature",
                    "priority": 2,
                    "status": "pending",
                    "passes": False,
                    "created_at": "2024-01-01",
                    "updated_at": "2024-01-01"
                }
            ]
        }
        with pytest.raises(Exception) as exc_info:
            state_manager.validate_feature_list(data)
        assert "Duplicate feature ID" in str(exc_info.value)

    # ========== Error Handling Tests ==========

    def test_load_feature_list_corrupted_json(self, state_manager):
        """Test loading corrupted JSON file for feature list raises error"""
        # Write corrupted JSON
        with open(state_manager.feature_list_path, "w") as f:
            f.write("{ invalid json }")

        # Should raise JSONDecodeError for corrupted file
        with pytest.raises(Exception):  # json.JSONDecodeError
            state_manager.load_feature_list()

    def test_load_state_corrupted_json(self, state_manager):
        """Test loading corrupted JSON file for state raises error"""
        # Write corrupted JSON
        with open(state_manager.state_path, "w") as f:
            f.write("{ invalid json }")

        # Should raise JSONDecodeError for corrupted file
        with pytest.raises(Exception):  # json.JSONDecodeError
            state_manager.load_state()

    def test_load_config_corrupted_json(self, state_manager):
        """Test loading corrupted JSON file for config raises error"""
        # Write corrupted JSON
        with open(state_manager.config_path, "w") as f:
            f.write("{ invalid json }")

        # Should raise JSONDecodeError for corrupted file
        with pytest.raises(Exception):  # json.JSONDecodeError
            state_manager.load_config()

    def test_load_session_history_corrupted_json(self, state_manager):
        """Test loading corrupted JSON file for session history raises error"""
        # Write corrupted JSON
        with open(state_manager.session_history_path, "w") as f:
            f.write("{ invalid json }")

        # Should raise JSONDecodeError for corrupted file
        with pytest.raises(Exception):  # json.JSONDecodeError
            state_manager.load_session_history()

    def test_validate_config_with_invalid_type_for_valid_field(self, state_manager):
        """Test config validation with wrong type for a valid field"""
        config = {
            "project_name": "Test Project",
            "project_type": 123,  # Should be string
            "model": "claude-3-5-sonnet-20241022",
            "session_type": "auto",
            "test_command": "pytest",
            "test_pattern": "test_*.py",
            "max_errors_before_intervention": 5,
            "context_window_limit": 100000,
            "documentation_urls": {"main": "https://example.com"}
        }
        with pytest.raises(Exception) as exc_info:
            state_manager.validate_config(config)
        assert "Invalid type" in str(exc_info.value)

    def test_validate_feature_list_invalid_context_files_type(self, state_manager):
        """Test feature list validation with invalid context_files type"""
        data = {
            "features": [
                {
                    "id": "feature-001",
                    "name": "Test Feature",
                    "description": "A test feature",
                    "priority": 1,
                    "status": "pending",
                    "passes": False,
                    "created_at": "2024-01-01",
                    "updated_at": "2024-01-01",
                    "context_files": "not_a_list"  # Should be list
                }
            ]
        }
        with pytest.raises(Exception) as exc_info:
            state_manager.validate_feature_list(data)
        assert "context_files must be a list" in str(exc_info.value)

    def test_validate_feature_list_invalid_verify_command_type(self, state_manager):
        """Test feature list validation with invalid verify_command type"""
        data = {
            "features": [
                {
                    "id": "feature-001",
                    "name": "Test Feature",
                    "description": "A test feature",
                    "priority": 1,
                    "status": "pending",
                    "passes": False,
                    "created_at": "2024-01-01",
                    "updated_at": "2024-01-01",
                    "verify_command": 123  # Should be string
                }
            ]
        }
        with pytest.raises(Exception) as exc_info:
            state_manager.validate_feature_list(data)
        assert "verify_command must be a string" in str(exc_info.value)

    # ========== Boundary Condition Tests ==========

    def test_save_and_load_empty_string_progress(self, state_manager):
        """Test saving and loading empty string progress"""
        state_manager.save_progress("")
        result = state_manager.load_progress()
        assert result == ""

    def test_update_progress_summary_new_file(self, state_manager):
        """Test updating progress summary when progress file doesn't exist"""
        # Ensure no progress file exists
        assert not state_manager.progress_path.exists()
        state_manager.update_progress_summary(10, 5)
        # Should create the file
        assert state_manager.progress_path.exists()

    def test_add_multiple_sessions(self, state_manager):
        """Test adding multiple sessions"""
        for i in range(5):
            state_manager.add_session({"id": f"session-{i}", "status": "completed"})

        result = state_manager.load_session_history()
        assert result["total_sessions"] == 5
        assert len(result["sessions"]) == 5

    def test_update_feature_only_passes(self, state_manager):
        """Test updating only passes field"""
        data = {
            "features": [
                {"id": "feature-001", "name": "Test", "status": "pending", "passes": False}
            ]
        }
        state_manager.save_feature_list(data)

        result = state_manager.update_feature("feature-001", {"passes": True})
        assert result is True

        feature = state_manager.get_feature("feature-001")
        assert feature["passes"] is True
        assert feature["status"] == "pending"  # Unchanged

    def test_update_feature_only_status(self, state_manager):
        """Test updating only status field"""
        data = {
            "features": [
                {"id": "feature-001", "name": "Test", "status": "pending", "passes": False}
            ]
        }
        state_manager.save_feature_list(data)

        result = state_manager.update_feature("feature-001", {"status": "in_progress"})
        assert result is True

        feature = state_manager.get_feature("feature-001")
        assert feature["passes"] is False  # Unchanged
        assert feature["status"] == "in_progress"

    def test_validate_config_loads_from_file_when_none(self, state_manager):
        """Test validate_config loads from file when config is None"""
        # Save a valid config
        config = {
            "project_name": "Test Project",
            "project_type": "python",
            "model": "claude-3-5-sonnet-20241022",
            "session_type": "auto",
            "test_command": "pytest",
            "test_pattern": "test_*.py",
            "max_errors_before_intervention": 5,
            "context_window_limit": 100000,
            "documentation_urls": {"main": "https://example.com"}
        }
        state_manager.save_config(config)

        # Validate without passing config - should load from file
        result = state_manager.validate_config()
        assert result["project_name"] == "Test Project"

    def test_validate_feature_list_loads_from_file_when_none(self, state_manager):
        """Test validate_feature_list loads from file when data is None"""
        # Save valid feature list
        data = {
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
                }
            ]
        }
        state_manager.save_feature_list(data)

        # Validate without passing data - should load from file
        result = state_manager.validate_feature_list()
        assert len(result["features"]) == 1
