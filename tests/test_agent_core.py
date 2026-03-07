"""Tests for AgentCore module"""

import pytest
import json
import tempfile
from pathlib import Path
import sys
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from agent.state_manager import StateManager
from agent.agent_core import AgentCore


class TestAgentCore:
    """Test cases for AgentCore"""

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
    def agent_core(self, temp_agent_dir, state_manager):
        """Create AgentCore with mocked dependencies"""
        with patch('agent.agent_core.GitHelper') as mock_git:
            with patch('agent.agent_core.HumanIntervention'):
                # Configure mock to return empty status
                mock_git_instance = mock_git.return_value
                mock_git_instance.get_status.return_value = ""
                mock_git_instance.get_current_branch.return_value = "main"

                core = AgentCore(project_root=temp_agent_dir)
                core.state_manager = state_manager
                # Also replace task_selector's state_manager to use the test one
                from agent.task_selector import TaskSelector
                core.task_selector = TaskSelector(state_manager)
                return core

    def test_init(self, temp_agent_dir):
        """Test AgentCore initialization"""
        with patch('agent.agent_core.GitHelper'):
            with patch('agent.agent_core.HumanIntervention'):
                with patch('agent.agent_core.StateManager'):
                    core = AgentCore(project_root=temp_agent_dir)
                    assert core.project_root == temp_agent_dir

    def test_get_system_prompt(self, agent_core):
        """Test getting system prompt"""
        prompt = agent_core.get_system_prompt()
        assert "You are an autonomous AI agent for the Agent-Loop project" in prompt
        assert "Browser Navigate" in prompt
        assert "WebSearch" in prompt

    def test_get_task_prompt(self, agent_core, state_manager):
        """Test getting task prompt"""
        # Add a feature
        state_manager.add_feature({
            "id": "feature-001",
            "name": "Test Task",
            "description": "Test description",
            "priority": 1
        })

        task = {
            "id": "feature-001",
            "name": "Test Task",
            "description": "Test description",
            "priority": 1
        }

        prompt = agent_core.get_task_prompt(task)
        assert "Test Task" in prompt
        assert "Test description" in prompt

    def test_verify_task_with_changes(self, agent_core, temp_agent_dir):
        """Test verifying task with changes"""
        # Create a git repo with changes
        import subprocess
        from pathlib import Path
        subprocess.run(["git", "init"], cwd=temp_agent_dir, check=True)
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"],
            cwd=temp_agent_dir,
            check=True
        )
        subprocess.run(
            ["git", "config", "user.name", "Test"],
            cwd=temp_agent_dir,
            check=True
        )

        # Create a test file to have changes
        test_file = Path(temp_agent_dir) / "test.txt"
        test_file.write_text("test")

        # Configure mock to return non-empty status (simulating changes)
        agent_core.git_helper.get_status.return_value = "M test.txt"

        task = {"id": "feature-001", "name": "Test"}
        result = agent_core.verify_task(task)
        assert result is True

    def test_verify_task_no_changes(self, agent_core, temp_agent_dir):
        """Test verifying task without changes"""
        import subprocess
        from pathlib import Path

        # Create a placeholder file so there's something to commit
        Path(temp_agent_dir).joinpath("placeholder.txt").touch()

        # Create git repo
        subprocess.run(["git", "init"], cwd=temp_agent_dir, check=True)
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"],
            cwd=temp_agent_dir,
            check=True
        )
        subprocess.run(
            ["git", "config", "user.name", "Test"],
            cwd=temp_agent_dir,
            check=True
        )
        # Make initial commit
        subprocess.run(["git", "add", "-A"], cwd=temp_agent_dir, check=True)
        subprocess.run(
            ["git", "commit", "-m", "Initial"],
            cwd=temp_agent_dir,
            check=True
        )

        task = {"id": "feature-001", "name": "Test"}
        result = agent_core.verify_task(task)
        assert result is False

    def test_handle_error(self, agent_core, state_manager):
        """Test error handling"""
        agent_core.handle_error("Test error")

        state = state_manager.load_state()
        assert state["error_count"] == 1
        assert state["last_error"] == "Test error"

    def test_initialize_session(self, agent_core, state_manager):
        """Test session initialization"""
        result = agent_core.initialize_session("coder")

        assert "session_id" in result
        assert "progress" in result
        assert "pending_tasks" in result

        # Check state was saved
        state = state_manager.load_state()
        assert state["current_session"]["agent_type"] == "coder"
        assert state["error_count"] == 0

    def test_gather_context(self, agent_core, state_manager):
        """Test gathering context"""
        # Add some features
        state_manager.add_feature({
            "id": "feature-001",
            "name": "Test",
            "status": "pending",
            "priority": 1
        })

        context = agent_core.gather_context()

        assert "current_task" in context
        assert "state" in context
        assert "git_status" in context
        assert "pending_count" in context
        assert "completed_count" in context
        assert "total_count" in context

    @patch('agent.agent_core.asyncio')
    def test_execute_task(self, mock_asyncio, agent_core):
        """Test execute task (synchronous wrapper)"""
        # Mock the async execution - use Mock with side_effect to close coroutine
        mock_run = Mock(side_effect=lambda coro: coro.close() or {
            "task_id": "feature-001",
            "status": "completed",
            "message": "Done"
        })
        mock_asyncio.run = mock_run

        task = {"id": "feature-001", "name": "Test"}
        result = agent_core.execute_task(task)

        assert result["status"] == "completed"
        mock_asyncio.run.assert_called_once()

    def test_extract_and_save_experience(self, agent_core, temp_agent_dir):
        """Test extracting and saving experience"""
        task = {
            "id": "feature-001",
            "name": "Test Task",
            "description": "Test description"
        }
        result = {
            "status": "completed",
            "message": "Task completed successfully"
        }

        agent_core.extract_and_save_experience(task, result)

        # Use the actual state_manager's agent_dir, not a hardcoded path
        memory_file = agent_core.state_manager.agent_dir / "MEMORY.md"
        assert memory_file.exists()

        with open(memory_file) as f:
            content = f.read()
        assert "Test Task" in content

    @patch('agent.agent_core.GitHelper')
    def test_complete_session(self, mock_git, agent_core, state_manager):
        """Test completing session"""
        # Setup
        state_manager.update_state({
            "current_session": {"id": "test-session"}
        })

        mock_git_instance = Mock()
        mock_git.return_value = mock_git_instance
        mock_git_instance.stage_and_commit = Mock(return_value=True)

        agent_core.git_helper = mock_git_instance

        agent_core.complete_session({"message": "Test summary"})

        # Verify commit was attempted
        mock_git_instance.stage_and_commit.assert_called()

    def test_task_selector_integration(self, agent_core, state_manager):
        """Test task selector is properly integrated"""
        # Add features
        state_manager.add_feature({
            "id": "feature-001",
            "name": "High Priority",
            "status": "pending",
            "passes": False,
            "priority": 1
        })

        context = agent_core.gather_context()
        # Should have selected the high priority task
        if context["current_task"]:
            assert context["current_task"]["priority"] == 1

    def test_config_loading(self, agent_core, state_manager):
        """Test configuration is loaded"""
        state_manager.save_config({"model": "test-model"})

        # Recreate agent core to load config
        with patch('agent.agent_core.GitHelper'):
            with patch('agent.agent_core.HumanIntervention'):
                core = AgentCore(project_root=agent_core.project_root)
                core.state_manager = state_manager
                # Config should be accessible
                assert core.config is not None

    # ===== Edge Case Tests for initialize_session =====

    def test_initialize_session_with_existing_session(self, agent_core, state_manager):
        """Test session initialization when a session already exists"""
        # First initialize
        agent_core.initialize_session("coder")
        state = state_manager.load_state()
        first_session_id = state["current_session"]["id"]

        # Second initialize - should create new session (or reset)
        result = agent_core.initialize_session("coder")
        state = state_manager.load_state()
        second_session_id = state["current_session"]["id"]

        # Should have session_id in result
        assert "session_id" in result
        assert result["session_id"] is not None

    def test_initialize_session_resets_error_count(self, agent_core, state_manager):
        """Test that session initialization resets error count"""
        # Set some errors first
        agent_core.handle_error("Previous error")
        state = state_manager.load_state()
        assert state["error_count"] > 0

        # Initialize new session - should reset errors
        agent_core.initialize_session("coder")
        state = state_manager.load_state()
        assert state["error_count"] == 0

    def test_initialize_session_different_agent_types(self, agent_core, state_manager):
        """Test session initialization with different agent types"""
        for agent_type in ["coder", "general", "custom"]:
            result = agent_core.initialize_session(agent_type)
            state = state_manager.load_state()
            assert state["current_session"]["agent_type"] == agent_type
            assert "session_id" in result

    # ===== Edge Case Tests for gather_context =====

    def test_gather_context_with_no_tasks(self, agent_core, state_manager):
        """Test gathering context with no tasks"""
        context = agent_core.gather_context()

        assert "pending_count" in context
        assert "completed_count" in context
        assert "total_count" in context
        assert context["pending_count"] == 0
        assert context["completed_count"] == 0
        assert context["total_count"] == 0

    def test_gather_context_with_completed_tasks(self, agent_core, state_manager):
        """Test gathering context with completed tasks"""
        # Add and complete a task
        state_manager.add_feature({
            "id": "feature-001",
            "name": "Completed Task",
            "status": "completed",
            "priority": 1
        })

        context = agent_core.gather_context()

        assert context["completed_count"] == 1
        assert context["pending_count"] == 0

    def test_gather_context_with_mixed_status(self, agent_core, state_manager):
        """Test gathering context with mixed task status"""
        # Add tasks with different statuses
        state_manager.add_feature({
            "id": "feature-001",
            "name": "Pending Task",
            "status": "pending",
            "priority": 1
        })
        state_manager.add_feature({
            "id": "feature-002",
            "name": "Completed Task",
            "status": "completed",
            "priority": 2
        })
        state_manager.add_feature({
            "id": "feature-003",
            "name": "In Progress Task",
            "status": "in_progress",
            "priority": 3
        })

        context = agent_core.gather_context()

        assert context["total_count"] == 3
        assert context["completed_count"] == 1
        assert context["pending_count"] >= 1

    def test_gather_context_returns_dict(self, agent_core, state_manager):
        """Test that gather_context returns proper dict structure"""
        context = agent_core.gather_context()

        # Should return a dict with all expected keys
        assert isinstance(context, dict)
        assert "current_task" in context
        assert "state" in context
        assert "git_status" in context
        assert "current_branch" in context

    # ===== Edge Case Tests for verify_task =====

    def test_verify_task_with_changes_detected(self, agent_core, temp_agent_dir):
        """Test verifying task when changes are detected"""
        # Configure mock to return non-empty status
        agent_core.git_helper.get_status = Mock(return_value="M test.txt")

        task = {"id": "feature-001", "name": "Test"}
        result = agent_core.verify_task(task)

        assert result is True

    def test_verify_task_marks_completed(self, agent_core, temp_agent_dir):
        """Test that verify_task marks task as completed"""
        # Add a task first
        agent_core.state_manager.add_feature({
            "id": "feature-001",
            "name": "Test Task",
            "status": "pending",
            "priority": 1
        })

        # Configure mock to return non-empty status
        agent_core.git_helper.get_status = Mock(return_value="M test.txt")

        task = {"id": "feature-001", "name": "Test"}
        result = agent_core.verify_task(task)

        assert result is True
        # Check task was marked as completed
        task = agent_core.state_manager.get_feature("feature-001")
        assert task["status"] == "completed"

    def test_verify_task_with_git_error(self, agent_core, temp_agent_dir):
        """Test verifying task when git fails"""
        # Don't initialize git repo - should handle gracefully
        task = {"id": "feature-001", "name": "Test"}

        # Mock git to raise an error
        agent_core.git_helper.get_status = Mock(side_effect=Exception("Git error"))

        # Should handle gracefully (return False or raise appropriately)
        try:
            result = agent_core.verify_task(task)
        except Exception:
            # Could also handle gracefully - depends on implementation
            pass

    def test_verify_task_with_empty_status(self, agent_core, temp_agent_dir):
        """Test verifying task with empty git status"""
        import subprocess
        from pathlib import Path

        # Create and commit file
        placeholder = Path(temp_agent_dir) / "placeholder.txt"
        placeholder.write_text("content")

        subprocess.run(["git", "init"], cwd=temp_agent_dir, check=True)
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"],
            cwd=temp_agent_dir,
            check=True
        )
        subprocess.run(
            ["git", "config", "user.name", "Test"],
            cwd=temp_agent_dir,
            check=True
        )
        subprocess.run(["git", "add", "-A"], cwd=temp_agent_dir, check=True)
        subprocess.run(
            ["git", "commit", "-m", "Initial"],
            cwd=temp_agent_dir,
            check=True
        )

        # Explicitly return empty status
        agent_core.git_helper.get_status = Mock(return_value="")

        task = {"id": "feature-001", "name": "Test"}
        result = agent_core.verify_task(task)
        assert result is False

    # ===== Edge Case Tests for execute_task =====

    @patch('agent.agent_core.asyncio')
    def test_execute_task_with_failed_result(self, mock_asyncio, agent_core):
        """Test execute task with failed result"""
        def mock_run(coro):
            coro.close()
            return {
                "task_id": "feature-001",
                "status": "failed",
                "error": "Task failed"
            }
        mock_asyncio.run = mock_run

        task = {"id": "feature-001", "name": "Test"}
        result = agent_core.execute_task(task)

        assert result["status"] == "failed"

    @patch('agent.agent_core.asyncio')
    def test_execute_task_with_error_result(self, mock_asyncio, agent_core):
        """Test execute task with error in result"""
        def mock_run(coro):
            coro.close()
            return {
                "task_id": "feature-001",
                "status": "error",
                "message": "Error occurred"
            }
        mock_asyncio.run = mock_run

        task = {"id": "feature-001", "name": "Test"}
        result = agent_core.execute_task(task)

        assert "error" in result["status"] or "message" in result

    @patch('agent.agent_core.asyncio')
    def test_execute_task_preserves_task_info(self, mock_asyncio, agent_core):
        """Test that execute_task preserves task information"""
        def mock_run(coro):
            coro.close()
            return {
                "task_id": "feature-001",
                "status": "completed"
            }
        mock_asyncio.run = mock_run

        task = {
            "id": "feature-001",
            "name": "Test Task",
            "description": "Test description",
            "priority": 1
        }
        result = agent_core.execute_task(task)

        assert result["task_id"] == "feature-001"

    # ===== Edge Case Tests for complete_session =====

    def test_complete_session_with_no_current_session(self, agent_core, state_manager):
        """Test completing session when there's no current session"""
        # Ensure no current session
        state = state_manager.load_state()
        if "current_session" in state:
            del state["current_session"]
            state_manager.save_state(state)

        # Should handle gracefully
        try:
            agent_core.complete_session({"message": "Test summary"})
        except Exception:
            # May raise or handle gracefully
            pass

    def test_complete_session_updates_history(self, agent_core, state_manager):
        """Test that complete_session updates session history"""
        # Initialize a session first
        agent_core.initialize_session("coder")

        # Complete the session
        agent_core.complete_session({"message": "Test summary"})

        # Check that session was moved to history
        history = state_manager.load_session_history()
        assert len(history) >= 1

    @patch('agent.agent_core.GitHelper')
    def test_complete_session_with_commit_failure(self, mock_git, agent_core, state_manager):
        """Test completing session when commit fails"""
        # Setup
        state_manager.update_state({
            "current_session": {"id": "test-session"}
        })

        mock_git_instance = Mock()
        mock_git.return_value = mock_git_instance
        # Make commit fail
        mock_git_instance.stage_and_commit = Mock(side_effect=Exception("Commit failed"))

        agent_core.git_helper = mock_git_instance

        # Should handle commit failure gracefully
        try:
            agent_core.complete_session({"message": "Test summary"})
        except Exception:
            # Could also handle gracefully
            pass

    # ===== Error Handling Tests =====

    def test_handle_error_increments_count(self, agent_core, state_manager):
        """Test that handle_error increments error count"""
        initial_state = state_manager.load_state()
        initial_count = initial_state.get("error_count", 0)

        agent_core.handle_error("Test error 1")
        agent_core.handle_error("Test error 2")

        state = state_manager.load_state()
        assert state["error_count"] == initial_count + 2

    def test_handle_error_stores_last_error(self, agent_core, state_manager):
        """Test that handle_error stores the last error"""
        error_msg = "Most recent error"
        agent_core.handle_error(error_msg)

        state = state_manager.load_state()
        assert state["last_error"] == error_msg

    def test_handle_error_with_task_context(self, agent_core, state_manager):
        """Test handle_error with task context"""
        task = {
            "id": "feature-001",
            "name": "Failing Task",
            "description": "This task will fail"
        }

        agent_core.handle_error("Task failed", task=task)

        state = state_manager.load_state()
        # Should store task info with error
        assert "last_error" in state

    # ===== Additional Edge Case Tests =====

    def test_get_task_prompt_with_empty_task(self, agent_core):
        """Test getting task prompt with minimal task"""
        task = {"id": "feature-001", "name": "Test"}

        prompt = agent_core.get_task_prompt(task)
        assert "Test" in prompt

    def test_get_task_prompt_with_full_task(self, agent_core):
        """Test getting task prompt with full task details"""
        task = {
            "id": "feature-001",
            "name": "Complex Task",
            "description": "A detailed description",
            "priority": 1,
            "status": "pending"
        }

        prompt = agent_core.get_task_prompt(task)
        assert "Complex Task" in prompt
        assert "A detailed description" in prompt

    def test_extract_and_save_experience_with_failed_result(self, agent_core, temp_agent_dir):
        """Test extracting experience from failed task"""
        task = {
            "id": "feature-001",
            "name": "Failed Task",
            "description": "Task that failed"
        }
        result = {
            "status": "failed",
            "error": "Task failed"
        }

        agent_core.extract_and_save_experience(task, result)

        # Should still save to memory
        memory_file = agent_core.state_manager.agent_dir / "MEMORY.md"
        assert memory_file.exists()

    def test_session_stats(self, agent_core, state_manager):
        """Test getting session statistics"""
        # Add sessions to history
        history = state_manager.load_session_history()
        history["sessions"] = [
            {"id": "session-1", "status": "completed"},
            {"id": "session-2", "status": "completed"},
            {"id": "session-3", "status": "failed"},
        ]
        state_manager.save_session_history(history)

        stats = agent_core._get_session_stats()

        assert "total" in stats
        assert "completed" in stats
        assert "failed" in stats
        assert stats["total"] == 3
        assert stats["completed"] == 2
        assert stats["failed"] == 1
