"""Tests for StateManager module"""

import json
import os
import tempfile
import pytest
from pathlib import Path

# Add parent directory to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from state_manager import StateManager


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
