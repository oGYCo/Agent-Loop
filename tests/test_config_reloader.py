"""Tests for ConfigReloader module"""

import json
import tempfile
import time
import pytest
from pathlib import Path

# Add parent directory to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from agent.config_reloader import ConfigReloader, reload_config


class TestConfigReloader:
    """Test cases for ConfigReloader"""

    @pytest.fixture
    def temp_agent_dir(self):
        """Create a temporary directory for testing"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.fixture
    def config_reloader(self, temp_agent_dir):
        """Create ConfigReloader with temporary directory"""
        return ConfigReloader(agent_dir=temp_agent_dir)

    @pytest.fixture
    def valid_config(self):
        """Valid config data for testing"""
        return {
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

    @pytest.fixture
    def valid_feature_list(self):
        """Valid feature list data for testing"""
        return {
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

    # ========== Initialization Tests ==========

    def test_init_with_empty_dir(self, temp_agent_dir):
        """Test initialization with empty directory"""
        reloader = ConfigReloader(agent_dir=temp_agent_dir)
        assert reloader.agent_dir == Path(temp_agent_dir)
        # Should have empty caches when files don't exist
        assert reloader._config_cache is None
        assert reloader._feature_list_cache is None

    def test_init_with_config_file(self, temp_agent_dir, valid_config):
        """Test initialization with config.json file"""
        # Write config file
        config_path = Path(temp_agent_dir) / "config.json"
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(valid_config, f)

        reloader = ConfigReloader(agent_dir=temp_agent_dir)
        assert reloader._config_cache is not None
        assert reloader._config_cache["project_name"] == "Test Project"

    def test_init_with_feature_list_file(self, temp_agent_dir, valid_feature_list):
        """Test initialization with feature_list.json file"""
        # Write feature list file
        feature_list_path = Path(temp_agent_dir) / "feature_list.json"
        with open(feature_list_path, "w", encoding="utf-8") as f:
            json.dump(valid_feature_list, f)

        reloader = ConfigReloader(agent_dir=temp_agent_dir)
        assert reloader._feature_list_cache is not None
        assert len(reloader._feature_list_cache["features"]) == 1

    # ========== File Modification Detection Tests ==========

    def test_check_for_changes_no_files(self, config_reloader):
        """Test change detection when no files exist"""
        changes = config_reloader.check_for_changes()
        assert changes["config"] is False
        assert changes["feature_list"] is False

    def test_check_for_changes_config_modified(self, temp_agent_dir, valid_config):
        """Test config.json modification detection"""
        # Create initial config
        config_path = Path(temp_agent_dir) / "config.json"
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(valid_config, f)

        reloader = ConfigReloader(agent_dir=temp_agent_dir)

        # No changes initially
        changes = reloader.check_for_changes()
        assert changes["config"] is False

        # Wait a bit and modify the file
        time.sleep(0.1)
        valid_config["project_name"] = "Updated Project"
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(valid_config, f)

        # Should detect changes
        changes = reloader.check_for_changes()
        assert changes["config"] is True
        assert changes["feature_list"] is False

    def test_check_for_changes_feature_list_modified(self, temp_agent_dir, valid_feature_list):
        """Test feature_list.json modification detection"""
        # Create initial feature list
        feature_list_path = Path(temp_agent_dir) / "feature_list.json"
        with open(feature_list_path, "w", encoding="utf-8") as f:
            json.dump(valid_feature_list, f)

        reloader = ConfigReloader(agent_dir=temp_agent_dir)

        # No changes initially
        changes = reloader.check_for_changes()
        assert changes["feature_list"] is False

        # Wait a bit and modify the file
        time.sleep(0.1)
        valid_feature_list["features"].append({
            "id": "feature-002",
            "name": "New Feature",
            "description": "Another test",
            "priority": 2,
            "status": "pending",
            "passes": False,
            "created_at": "2024-01-01",
            "updated_at": "2024-01-01"
        })
        with open(feature_list_path, "w", encoding="utf-8") as f:
            json.dump(valid_feature_list, f)

        # Should detect changes
        changes = reloader.check_for_changes()
        assert changes["config"] is False
        assert changes["feature_list"] is True

    def test_check_for_changes_both_modified(self, temp_agent_dir, valid_config, valid_feature_list):
        """Test detection when both files are modified"""
        # Create both files
        config_path = Path(temp_agent_dir) / "config.json"
        feature_list_path = Path(temp_agent_dir) / "feature_list.json"
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(valid_config, f)
        with open(feature_list_path, "w", encoding="utf-8") as f:
            json.dump(valid_feature_list, f)

        reloader = ConfigReloader(agent_dir=temp_agent_dir)

        # No changes initially
        changes = reloader.check_for_changes()
        assert changes["config"] is False
        assert changes["feature_list"] is False

        # Modify both files
        time.sleep(0.1)
        valid_config["project_name"] = "Updated Project"
        valid_feature_list["features"].append({
            "id": "feature-002",
            "name": "New Feature",
            "description": "Another test",
            "priority": 2,
            "status": "pending",
            "passes": False,
            "created_at": "2024-01-01",
            "updated_at": "2024-01-01"
        })
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(valid_config, f)
        with open(feature_list_path, "w", encoding="utf-8") as f:
            json.dump(valid_feature_list, f)

        # Should detect changes in both
        changes = reloader.check_for_changes()
        assert changes["config"] is True
        assert changes["feature_list"] is True

    # ========== Reload Tests ==========

    def test_reload_no_changes(self, config_reloader):
        """Test reload when no files have changed"""
        result = config_reloader.reload()

        assert result["success"] is True
        assert result["message"] == "No changes detected"
        assert len(result["reloaded"]) == 0

    def test_reload_config_file(self, temp_agent_dir, valid_config):
        """Test reloading config.json"""
        # Create initial config
        config_path = Path(temp_agent_dir) / "config.json"
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(valid_config, f)

        reloader = ConfigReloader(agent_dir=temp_agent_dir)

        # Modify the file
        time.sleep(0.1)
        valid_config["project_name"] = "Updated Project"
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(valid_config, f)

        # Reload
        result = reloader.reload()

        assert result["success"] is True
        assert "config.json" in result["reloaded"]
        assert reloader._config_cache["project_name"] == "Updated Project"

    def test_reload_feature_list_file(self, temp_agent_dir, valid_feature_list):
        """Test reloading feature_list.json"""
        # Create initial feature list
        feature_list_path = Path(temp_agent_dir) / "feature_list.json"
        with open(feature_list_path, "w", encoding="utf-8") as f:
            json.dump(valid_feature_list, f)

        reloader = ConfigReloader(agent_dir=temp_agent_dir)

        # Modify the file
        time.sleep(0.1)
        valid_feature_list["features"].append({
            "id": "feature-002",
            "name": "New Feature",
            "description": "Another test",
            "priority": 2,
            "status": "pending",
            "passes": False,
            "created_at": "2024-01-01",
            "updated_at": "2024-01-01"
        })
        with open(feature_list_path, "w", encoding="utf-8") as f:
            json.dump(valid_feature_list, f)

        # Reload
        result = reloader.reload()

        assert result["success"] is True
        assert "feature_list.json" in result["reloaded"]
        assert len(reloader._feature_list_cache["features"]) == 2

    def test_reload_force(self, temp_agent_dir, valid_config):
        """Test force reload without checking for changes"""
        # Create config
        config_path = Path(temp_agent_dir) / "config.json"
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(valid_config, f)

        reloader = ConfigReloader(agent_dir=temp_agent_dir)

        # Force reload without any file changes
        result = reloader.reload(force=True)

        assert result["success"] is True
        assert "config.json" in result["reloaded"]

    def test_reload_multiple_files(self, temp_agent_dir, valid_config, valid_feature_list):
        """Test reloading both files at once"""
        # Create both files
        config_path = Path(temp_agent_dir) / "config.json"
        feature_list_path = Path(temp_agent_dir) / "feature_list.json"
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(valid_config, f)
        with open(feature_list_path, "w", encoding="utf-8") as f:
            json.dump(valid_feature_list, f)

        reloader = ConfigReloader(agent_dir=temp_agent_dir)

        # Modify both files
        time.sleep(0.1)
        valid_config["project_name"] = "Updated Project"
        valid_feature_list["features"].append({
            "id": "feature-002",
            "name": "New Feature",
            "description": "Another test",
            "priority": 2,
            "status": "pending",
            "passes": False,
            "created_at": "2024-01-01",
            "updated_at": "2024-01-01"
        })
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(valid_config, f)
        with open(feature_list_path, "w", encoding="utf-8") as f:
            json.dump(valid_feature_list, f)

        # Reload
        result = reloader.reload()

        assert result["success"] is True
        assert "config.json" in result["reloaded"]
        assert "feature_list.json" in result["reloaded"]

    def test_reload_missing_file(self, temp_agent_dir):
        """Test reload when config file is missing"""
        reloader = ConfigReloader(agent_dir=temp_agent_dir)

        # Create only config.json (not feature_list.json)
        config_path = Path(temp_agent_dir) / "config.json"
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump({"test": "value"}, f)

        # Modify and reload
        time.sleep(0.1)
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump({"test": "updated"}, f)

        result = reloader.reload()

        assert result["success"] is True
        assert "config.json" in result["reloaded"]
        # feature_list.json should not be in errors as it's optional

    def test_reload_corrupted_json(self, temp_agent_dir, valid_config):
        """Test reload with corrupted JSON file"""
        # Create valid config first
        config_path = Path(temp_agent_dir) / "config.json"
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(valid_config, f)

        # Initialize reloader with valid config
        reloader = ConfigReloader(agent_dir=temp_agent_dir)

        # Now corrupt the file after initialization
        with open(config_path, "w", encoding="utf-8") as f:
            f.write("{ invalid json }")

        # Force reload - should handle error gracefully
        result = reloader.reload(force=True)

        assert result["success"] is False
        assert len(result["errors"]) > 0
        assert any("config.json" in err for err in result["errors"])

    # ========== Cache Tests ==========

    def test_get_cached_config(self, temp_agent_dir, valid_config):
        """Test getting cached config"""
        # Create config
        config_path = Path(temp_agent_dir) / "config.json"
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(valid_config, f)

        reloader = ConfigReloader(agent_dir=temp_agent_dir)

        # Get cached config
        cached = reloader.get_cached_config()
        assert cached["project_name"] == "Test Project"

    def test_get_cached_config_no_file(self, config_reloader):
        """Test getting cached config when no file exists"""
        cached = config_reloader.get_cached_config()
        assert cached == {}

    def test_get_cached_feature_list(self, temp_agent_dir, valid_feature_list):
        """Test getting cached feature list"""
        # Create feature list
        feature_list_path = Path(temp_agent_dir) / "feature_list.json"
        with open(feature_list_path, "w", encoding="utf-8") as f:
            json.dump(valid_feature_list, f)

        reloader = ConfigReloader(agent_dir=temp_agent_dir)

        # Get cached feature list
        cached = reloader.get_cached_feature_list()
        assert len(cached["features"]) == 1

    def test_get_cached_feature_list_no_file(self, config_reloader):
        """Test getting cached feature list when no file exists"""
        cached = config_reloader.get_cached_feature_list()
        assert cached == {"features": []}

    # ========== Callback Tests ==========

    def test_add_reload_callback(self, config_reloader):
        """Test adding reload callback"""
        callback_called = {"value": False}

        def callback():
            callback_called["value"] = True

        config_reloader.add_reload_callback(callback)
        assert callback in config_reloader._on_reload_callbacks

    def test_remove_reload_callback(self, config_reloader):
        """Test removing reload callback"""
        def callback():
            pass

        config_reloader.add_reload_callback(callback)
        config_reloader.remove_reload_callback(callback)
        assert callback not in config_reloader._on_reload_callbacks

    def test_callback_triggered_on_reload(self, temp_agent_dir, valid_config):
        """Test that callbacks are triggered on reload"""
        callback_called = {"count": 0}

        def callback():
            callback_called["count"] += 1

        # Create config
        config_path = Path(temp_agent_dir) / "config.json"
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(valid_config, f)

        reloader = ConfigReloader(agent_dir=temp_agent_dir)
        reloader.add_reload_callback(callback)

        # Modify and reload
        time.sleep(0.1)
        valid_config["project_name"] = "Updated Project"
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(valid_config, f)

        reloader.reload()

        assert callback_called["count"] == 1

    def test_callback_error_handling(self, temp_agent_dir, valid_config):
        """Test that callback errors are handled gracefully"""
        def bad_callback():
            raise ValueError("Callback error")

        # Create config
        config_path = Path(temp_agent_dir) / "config.json"
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(valid_config, f)

        reloader = ConfigReloader(agent_dir=temp_agent_dir)
        reloader.add_reload_callback(bad_callback)

        # Modify and reload
        time.sleep(0.1)
        valid_config["project_name"] = "Updated Project"
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(valid_config, f)

        result = reloader.reload()

        # Should still succeed despite callback error
        assert result["success"] is False
        assert any("callback" in err for err in result["errors"])

    # ========== Convenience Function Tests ==========

    def test_reload_config_function(self, temp_agent_dir, valid_config):
        """Test the reload_config convenience function with force=True"""
        # Create config
        config_path = Path(temp_agent_dir) / "config.json"
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(valid_config, f)

        # Use convenience function with force to reload
        result = reload_config(agent_dir=temp_agent_dir, force=True)

        assert result["success"] is True
        assert "config.json" in result["reloaded"]

    def test_reload_config_function_force(self, temp_agent_dir, valid_config):
        """Test the reload_config convenience function with force=True"""
        # Create config
        config_path = Path(temp_agent_dir) / "config.json"
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(valid_config, f)

        # Use convenience function with force
        result = reload_config(agent_dir=temp_agent_dir, force=True)

        assert result["success"] is True

    # ========== File Watcher Tests ==========

    def test_config_watcher_init(self, config_reloader):
        """Test ConfigWatcher initialization"""
        watcher = config_reloader.start_watching(interval=0.5)
        assert watcher.interval == 0.5
        assert watcher.reloader is config_reloader

    # ========== Edge Cases ==========

    def test_reload_timestamp_updated(self, temp_agent_dir, valid_config):
        """Test that reload timestamp is updated after reload"""
        # Create config
        config_path = Path(temp_agent_dir) / "config.json"
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(valid_config, f)

        reloader = ConfigReloader(agent_dir=temp_agent_dir)

        initial_time = reloader._last_reload_time

        # Modify and reload
        time.sleep(0.1)
        valid_config["project_name"] = "Updated Project"
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(valid_config, f)

        reloader.reload()

        assert reloader._last_reload_time > initial_time

    def test_get_file_mtime_nonexistent(self, config_reloader):
        """Test getting mtime for non-existent file"""
        mtime = config_reloader._get_file_mtime("nonexistent.json")
        assert mtime == 0.0

    def test_cache_update_after_reload(self, temp_agent_dir, valid_config):
        """Test that cache is properly updated after reload"""
        # Create config
        config_path = Path(temp_agent_dir) / "config.json"
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(valid_config, f)

        reloader = ConfigReloader(agent_dir=temp_agent_dir)

        # Get cached config - should have original value
        cached_before = reloader.get_cached_config()
        assert cached_before["project_name"] == "Test Project"

        # Modify and reload
        time.sleep(0.1)
        valid_config["project_name"] = "Updated Project"
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(valid_config, f)

        reloader.reload()

        # Cache should be updated
        cached_after = reloader.get_cached_config()
        assert cached_after["project_name"] == "Updated Project"

    def test_reload_result_contains_timestamp(self, config_reloader):
        """Test that reload result contains timestamp"""
        result = config_reloader.reload()
        assert "timestamp" in result
        assert result["timestamp"] is not None
