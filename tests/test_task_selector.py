"""Tests for TaskSelector module"""

import pytest
from pathlib import Path
import sys
import tempfile
import json

sys.path.insert(0, str(Path(__file__).parent.parent))

from agent.state_manager import StateManager
from agent.task_selector import TaskSelector


class TestTaskSelector:
    """Test cases for TaskSelector"""

    @pytest.fixture
    def temp_agent_dir(self):
        """Create a temporary directory for testing"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.fixture
    def state_manager(self, temp_agent_dir):
        """Create StateManager with temporary directory"""
        return StateManager(agent_dir=temp_agent_dir)

    @pytest.fixture
    def task_selector(self, state_manager):
        """Create TaskSelector with test state manager"""
        return TaskSelector(state_manager)

    @pytest.fixture
    def sample_features(self, state_manager):
        """Create sample feature list"""
        data = {
            "features": [
                {
                    "id": "feature-001",
                    "name": "High Priority Task",
                    "description": "This is high priority",
                    "status": "pending",
                    "passes": False,
                    "priority": 1
                },
                {
                    "id": "feature-002",
                    "name": "Medium Priority Task",
                    "description": "This is medium priority",
                    "status": "pending",
                    "passes": False,
                    "priority": 2
                },
                {
                    "id": "feature-003",
                    "name": "Low Priority Task",
                    "description": "This is low priority",
                    "status": "pending",
                    "passes": False,
                    "priority": 3
                },
                {
                    "id": "feature-004",
                    "name": "Completed Task",
                    "description": "Already completed",
                    "status": "completed",
                    "passes": True,
                    "priority": 1
                }
            ]
        }
        state_manager.save_feature_list(data)
        return data

    def test_select_next_task(self, task_selector, sample_features):
        """Test selecting next task based on priority"""
        task = task_selector.select_next_task()
        assert task is not None
        assert task["id"] == "feature-001"  # Highest priority (lowest number)

    def test_select_next_task_all_completed(self, task_selector, state_manager):
        """Test when all tasks are completed"""
        data = {
            "features": [
                {
                    "id": "feature-001",
                    "name": "Completed",
                    "status": "completed",
                    "passes": True,
                    "priority": 1
                }
            ]
        }
        state_manager.save_feature_list(data)

        task = task_selector.select_next_task()
        assert task is None

    def test_select_next_task_passes_true(self, task_selector, state_manager):
        """Test when task has passes=True"""
        data = {
            "features": [
                {
                    "id": "feature-001",
                    "name": "Passed Task",
                    "status": "pending",
                    "passes": True,
                    "priority": 1
                },
                {
                    "id": "feature-002",
                    "name": "Not Passed Task",
                    "status": "pending",
                    "passes": False,
                    "priority": 2
                }
            ]
        }
        state_manager.save_feature_list(data)

        task = task_selector.select_next_task()
        assert task is not None
        assert task["id"] == "feature-002"

    def test_get_pending_count(self, task_selector, sample_features):
        """Test getting pending task count"""
        count = task_selector.get_pending_count()
        assert count == 3  # feature-001, 002, 003 are pending

    def test_get_completed_count(self, task_selector, sample_features):
        """Test getting completed task count"""
        count = task_selector.get_completed_count()
        assert count == 1  # Only feature-004 is completed

    def test_get_total_count(self, task_selector, sample_features):
        """Test getting total task count"""
        count = task_selector.get_total_count()
        assert count == 4

    def test_mark_task_completed(self, task_selector, sample_features):
        """Test marking a task as completed"""
        result = task_selector.mark_task_completed("feature-001")
        assert result is True

        # Verify the task was marked
        feature = task_selector.state_manager.get_feature("feature-001")
        assert feature["status"] == "completed"
        assert feature["passes"] is True

    def test_mark_task_failed(self, task_selector, sample_features):
        """Test marking a task as failed"""
        result = task_selector.mark_task_failed("feature-001")
        assert result is True

        # Verify the task was marked
        feature = task_selector.state_manager.get_feature("feature-001")
        assert feature["status"] == "failed"

    def test_mark_task_failed_not_found(self, task_selector, sample_features):
        """Test marking a non-existent task as failed"""
        result = task_selector.mark_task_failed("non-existent")
        assert result is False

    def test_priority_ordering(self, task_selector, state_manager):
        """Test that tasks are selected by priority order"""
        data = {
            "features": [
                {"id": "low", "status": "pending", "passes": False, "priority": 100},
                {"id": "high", "status": "pending", "passes": False, "priority": 1},
                {"id": "medium", "status": "pending", "passes": False, "priority": 50}
            ]
        }
        state_manager.save_feature_list(data)

        task = task_selector.select_next_task()
        assert task["id"] == "high"

    def test_empty_feature_list(self, task_selector, state_manager):
        """Test with empty feature list"""
        data = {"features": []}
        state_manager.save_feature_list(data)

        task = task_selector.select_next_task()
        assert task is None
        assert task_selector.get_pending_count() == 0
        assert task_selector.get_total_count() == 0

    # Additional tests for edge cases

    def test_get_completed_count_with_passes_true(self, task_selector, state_manager):
        """Test getting completed count when passes=True but status is pending"""
        data = {
            "features": [
                {
                    "id": "feature-001",
                    "name": "Status Completed",
                    "status": "completed",
                    "passes": True,
                    "priority": 1
                },
                {
                    "id": "feature-002",
                    "name": "Passes True but Pending",
                    "status": "pending",
                    "passes": True,  # passes=True counts as completed
                    "priority": 2
                },
                {
                    "id": "feature-003",
                    "name": "Still Pending",
                    "status": "pending",
                    "passes": False,
                    "priority": 3
                }
            ]
        }
        state_manager.save_feature_list(data)

        # Both feature-001 (status=completed) and feature-002 (passes=True) count as completed
        count = task_selector.get_completed_count()
        assert count == 2

    def test_missing_priority_field(self, task_selector, state_manager):
        """Test that missing priority defaults to DEFAULT_PRIORITY (1000)"""
        data = {
            "features": [
                {"id": "no-priority", "status": "pending", "passes": False},
                {"id": "has-priority", "status": "pending", "passes": False, "priority": 1}
            ]
        }
        state_manager.save_feature_list(data)

        # Should select the one with explicit priority=1
        task = task_selector.select_next_task()
        assert task["id"] == "has-priority"

    def test_in_progress_status_skipped(self, task_selector, state_manager):
        """Test that in_progress tasks are not selected"""
        data = {
            "features": [
                {"id": "in-progress", "status": "in_progress", "passes": False, "priority": 1},
                {"id": "pending", "status": "pending", "passes": False, "priority": 2}
            ]
        }
        state_manager.save_feature_list(data)

        task = task_selector.select_next_task()
        assert task["id"] == "pending"

    def test_passes_none_vs_false(self, task_selector, state_manager):
        """Test that passes=None is treated as falsy (not completed)"""
        data = {
            "features": [
                {"id": "passes-null", "status": "pending", "passes": None, "priority": 1},
                {"id": "passes-false", "status": "pending", "passes": False, "priority": 2}
            ]
        }
        state_manager.save_feature_list(data)

        # Both should be selected as pending (passes=None is falsy)
        # Lower priority selected first
        task = task_selector.select_next_task()
        assert task["id"] == "passes-null"

    def test_same_priority_selection(self, task_selector, state_manager):
        """Test selection when multiple tasks have same priority"""
        data = {
            "features": [
                {"id": "first", "status": "pending", "passes": False, "priority": 1},
                {"id": "second", "status": "pending", "passes": False, "priority": 1},
                {"id": "third", "status": "pending", "passes": False, "priority": 1}
            ]
        }
        state_manager.save_feature_list(data)

        task = task_selector.select_next_task()
        # Should return one of them (any is valid since same priority)
        assert task["id"] in ["first", "second", "third"]
        assert task["priority"] == 1

    def test_get_pending_count_with_passes_true(self, task_selector, state_manager):
        """Test pending count excludes passes=True tasks"""
        data = {
            "features": [
                {"id": "pending-false", "status": "pending", "passes": False, "priority": 1},
                {"id": "pending-true", "status": "pending", "passes": True, "priority": 2},
                {"id": "completed", "status": "completed", "passes": True, "priority": 3}
            ]
        }
        state_manager.save_feature_list(data)

        count = task_selector.get_pending_count()
        # Only pending-false should count as pending
        assert count == 1

    def test_failed_status_not_selected(self, task_selector, state_manager):
        """Test that failed tasks are not selected"""
        data = {
            "features": [
                {"id": "failed", "status": "failed", "passes": False, "priority": 1},
                {"id": "pending", "status": "pending", "passes": False, "priority": 2}
            ]
        }
        state_manager.save_feature_list(data)

        task = task_selector.select_next_task()
        assert task["id"] == "pending"

    def test_all_tasks_failed(self, task_selector, state_manager):
        """Test when all tasks are failed"""
        data = {
            "features": [
                {"id": "failed-1", "status": "failed", "passes": False, "priority": 1},
                {"id": "failed-2", "status": "failed", "passes": False, "priority": 2}
            ]
        }
        state_manager.save_feature_list(data)

        task = task_selector.select_next_task()
        assert task is None
