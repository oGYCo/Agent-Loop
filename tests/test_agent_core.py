"""Tests for AgentCore module"""

import pytest
import json
import tempfile
from pathlib import Path
import sys
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from state_manager import StateManager
from agent_core import AgentCore


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
        with patch('agent_core.GitHelper') as mock_git:
            with patch('agent_core.HumanIntervention'):
                # Configure mock to return empty status
                mock_git_instance = mock_git.return_value
                mock_git_instance.get_status.return_value = ""
                mock_git_instance.get_current_branch.return_value = "main"

                core = AgentCore(project_root=temp_agent_dir)
                core.state_manager = state_manager
                # Also replace task_selector's state_manager to use the test one
                from task_selector import TaskSelector
                core.task_selector = TaskSelector(state_manager)
                return core

    def test_init(self, temp_agent_dir):
        """Test AgentCore initialization"""
        with patch('agent_core.GitHelper'):
            with patch('agent_core.HumanIntervention'):
                with patch('agent_core.StateManager'):
                    core = AgentCore(project_root=temp_agent_dir)
                    assert core.project_root == temp_agent_dir

    def test_get_system_prompt(self, agent_core):
        """Test getting system prompt"""
        prompt = agent_core.get_system_prompt()
        assert "你是一个高效的长程AI编程助手" in prompt
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

    @patch('agent_core.asyncio')
    def test_execute_task(self, mock_asyncio, agent_core):
        """Test execute task (synchronous wrapper)"""
        # Mock the async execution
        mock_asyncio.run = Mock(return_value={
            "task_id": "feature-001",
            "status": "completed",
            "message": "Done"
        })

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

    @patch('agent_core.GitHelper')
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
        with patch('agent_core.GitHelper'):
            with patch('agent_core.HumanIntervention'):
                core = AgentCore(project_root=agent_core.project_root)
                core.state_manager = state_manager
                # Config should be accessible
                assert core.config is not None
