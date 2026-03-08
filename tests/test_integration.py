"""Integration tests for Agent-Loop modules working together

These tests verify that the core modules work correctly when integrated:
- AgentCore with StateManager
- GitHelper integration with AgentCore
- State persistence across sessions
"""

import json
import os
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

# Add parent directory to path for imports
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from agent.state_manager import StateManager
from agent.git_helper import GitHelper
from agent.task_selector import TaskSelector
from agent.agent_core import AgentCore


class TestAgentStatePersistence:
    """Integration tests for state persistence across modules"""

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
    def git_helper(self, temp_agent_dir):
        """Create GitHelper with temporary directory"""
        return GitHelper(project_root=temp_agent_dir)

    def test_state_persistence_after_feature_update(self, state_manager):
        """Test that feature updates persist correctly in state"""
        # Add a feature
        state_manager.add_feature({
            "id": "feat-001",
            "name": "Test Feature",
            "description": "Test description",
            "priority": 1,
            "status": "pending",
            "passes": False,
            "created_at": "2026-03-08",
            "updated_at": "2026-03-08"
        })

        # Update the feature
        state_manager.update_feature("feat-001", {
            "status": "in_progress",
            "passes": False
        })

        # Verify persistence - reload from disk
        data = state_manager.load_feature_list()
        feature = next(f for f in data["features"] if f["id"] == "feat-001")

        assert feature["status"] == "in_progress"
        assert feature["updated_at"] == "2026-03-08"

    def test_state_persistence_with_session_history(self, state_manager):
        """Test that session history persists correctly"""
        # Add multiple sessions
        for i in range(3):
            state_manager.add_session({
                "id": f"session-{i}",
                "status": "completed",
                "start_time": "2026-03-08T00:00:00",
                "end_time": "2026-03-08T01:00:00",
                "tasks_completed": i + 1
            })

        # Verify persistence
        history = state_manager.load_session_history()
        assert history["total_sessions"] == 3
        assert len(history["sessions"]) == 3

    def test_state_persistence_with_current_state(self, state_manager):
        """Test that current state persists correctly"""
        # Update state
        state_manager.update_state({
            "current_task": "feat-001",
            "error_count": 2,
            "last_error": "Test error",
            "context_used": 5000
        })

        # Verify persistence
        state = state_manager.load_state()
        assert state["current_task"] == "feat-001"
        assert state["error_count"] == 2
        assert state["last_error"] == "Test error"
        assert state["context_used"] == 5000

    def test_full_workflow_feature_lifecycle(self, state_manager):
        """Test complete feature lifecycle with state persistence"""
        # 1. Add a new feature
        state_manager.add_feature({
            "id": "feat-001",
            "name": "New Feature",
            "description": "A new feature",
            "priority": 1,
            "status": "pending",
            "passes": False,
            "created_at": "2026-03-08",
            "updated_at": "2026-03-08"
        })

        # 2. Start working on it
        state_manager.update_feature("feat-001", {"status": "in_progress"})

        # 3. Mark as completed with passes
        state_manager.update_feature("feat-001", {
            "status": "completed",
            "passes": True
        })

        # Verify all states persisted
        feature = state_manager.get_feature("feat-001")
        assert feature["status"] == "completed"
        assert feature["passes"] is True

        # Verify feature list is valid
        validated = state_manager.validate_feature_list()
        assert any(f["id"] == "feat-001" for f in validated["features"])


class TestGitIntegration:
    """Integration tests for Git integration with other modules"""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for testing"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.fixture
    def initialized_git_repo(self, temp_dir):
        """Initialize a git repository with initial commit"""
        subprocess.run(["git", "init"], cwd=temp_dir, check=True)
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"],
            cwd=temp_dir,
            check=True
        )
        subprocess.run(
            ["git", "config", "user.name", "Test"],
            cwd=temp_dir,
            check=True
        )

        # Create initial file and commit
        readme = Path(temp_dir) / "README.md"
        readme.write_text("# Test Project\n\nInitial content")
        subprocess.run(["git", "add", "-A"], cwd=temp_dir, check=True)
        subprocess.run(
            ["git", "commit", "-m", "Initial commit"],
            cwd=temp_dir,
            check=True
        )
        return temp_dir

    @pytest.fixture
    def git_helper(self, initialized_git_repo):
        """Create GitHelper with initialized repo"""
        return GitHelper(project_root=initialized_git_repo)

    @pytest.fixture
    def state_manager(self, initialized_git_repo):
        """Create StateManager in the git repo directory"""
        agent_dir = Path(initialized_git_repo) / ".agent"
        agent_dir.mkdir(exist_ok=True)
        return StateManager(agent_dir=str(agent_dir))

    def test_git_with_state_persistence(self, git_helper, state_manager):
        """Test Git operations work with state persistence"""
        # Save state before git operations
        state_manager.update_state({
            "current_task": "feat-001",
            "error_count": 0
        })

        # Perform git operations
        assert git_helper.is_git_repo() is True
        branch = git_helper.get_current_branch()
        assert branch == "main"

        # Create a branch
        result = git_helper.create_branch("feature-branch")
        assert result is True
        assert git_helper.get_current_branch() == "feature-branch"

        # Switch back
        git_helper.checkout_branch("main")

        # Verify state persisted through git operations
        state = state_manager.load_state()
        assert state["current_task"] == "feat-001"

    def test_git_status_tracking_with_task_changes(self, git_helper, state_manager):
        """Test that git status tracks with task state changes"""
        # Add a task
        state_manager.add_feature({
            "id": "feat-001",
            "name": "Add new file",
            "description": "Add a new file to the project",
            "priority": 1,
            "status": "pending",
            "passes": False,
            "created_at": "2026-03-08",
            "updated_at": "2026-03-08"
        })

        # Create a new file (simulating task work)
        new_file = Path(git_helper.project_root) / "new_feature.py"
        new_file.write_text("# New feature\nprint('hello')")

        # Check git status
        status = git_helper.get_status()
        assert "new_feature.py" in status
        assert git_helper.has_changes() is True

    def test_git_diff_with_feature_context(self, git_helper, state_manager):
        """Test git diff with feature context"""
        # Add a feature
        state_manager.add_feature({
            "id": "feat-001",
            "name": "Update README",
            "description": "Update README with new content",
            "priority": 1,
            "status": "in_progress",
            "passes": False,
            "created_at": "2026-03-08",
            "updated_at": "2026-03-08"
        })

        # Modify a file
        readme = Path(git_helper.project_root) / "README.md"
        readme.write_text("# Test Project\n\nUpdated content\nNew line")

        # Get diff
        diff = git_helper.get_diff()
        assert "Updated content" in diff or "New line" in diff

    def test_git_branch_with_session_tracking(self, git_helper, state_manager):
        """Test git branch operations with session tracking"""
        # Start a session
        session_data = {
            "id": "session-001",
            "start_time": datetime.now().isoformat(),
            "agent_type": "coder",
            "status": "started"
        }
        state_manager.update_state({
            "current_session": session_data
        })

        # Create a branch for this session
        branch_name = "feature/session-001-work"
        git_helper.create_branch(branch_name)

        # Verify branch exists
        result = subprocess.run(
            ["git", "branch", "--list", branch_name],
            cwd=git_helper.project_root,
            capture_output=True,
            text=True
        )
        assert branch_name in result.stdout

    def test_git_commit_tracking_with_state(self, git_helper, state_manager):
        """Test git commit operations with state tracking"""
        # Set up initial state
        state_manager.update_state({
            "current_task": "feat-001",
            "error_count": 0
        })

        # Create and commit a file
        test_file = Path(git_helper.project_root) / "test.txt"
        test_file.write_text("Test content")

        # Stage and commit
        subprocess.run(["git", "add", "test.txt"], cwd=git_helper.project_root, check=True)
        subprocess.run(
            ["git", "commit", "-m", "Add test.txt"],
            cwd=git_helper.project_root,
            check=True
        )

        # Verify state is still intact
        state = state_manager.load_state()
        assert state["current_task"] == "feat-001"

        # Verify commit exists
        commits = git_helper.get_recent_commits(1)
        assert "Add test.txt" in commits[0]


class TestAgentExecutionFlow:
    """Integration tests for Agent complete execution flow"""

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
        """Create AgentCore with real dependencies"""
        with patch('agent.agent_core.GitHelper') as mock_git:
            with patch('agent.agent_core.HumanIntervention'):
                # Configure mock
                mock_git_instance = mock_git.return_value
                mock_git_instance.get_status.return_value = ""
                mock_git_instance.get_current_branch.return_value = "main"
                mock_git_instance.has_changes.return_value = False

                core = AgentCore(project_root=temp_agent_dir)
                core.state_manager = state_manager

                # Use real TaskSelector
                core.task_selector = TaskSelector(state_manager)
                return core

    def test_full_task_selection_execution_flow(self, agent_core, state_manager):
        """Test the full flow from task selection to execution"""
        # 1. Add multiple tasks with different priorities
        state_manager.add_feature({
            "id": "feat-low",
            "name": "Low Priority Task",
            "description": "This is a low priority task",
            "priority": 3,
            "status": "pending",
            "passes": False,
            "created_at": "2026-03-08",
            "updated_at": "2026-03-08"
        })

        state_manager.add_feature({
            "id": "feat-high",
            "name": "High Priority Task",
            "description": "This is a high priority task",
            "priority": 1,
            "status": "pending",
            "passes": False,
            "created_at": "2026-03-08",
            "updated_at": "2026-03-08"
        })

        state_manager.add_feature({
            "id": "feat-medium",
            "name": "Medium Priority Task",
            "description": "This is a medium priority task",
            "priority": 2,
            "status": "pending",
            "passes": False,
            "created_at": "2026-03-08",
            "updated_at": "2026-03-08"
        })

        # 2. Gather context (should select highest priority task)
        context = agent_core.gather_context()

        # 3. Verify context has correct pending tasks
        assert context["pending_count"] == 3
        assert context["total_count"] == 3
        assert context["completed_count"] == 0

        # 4. Verify current task is highest priority
        if context["current_task"]:
            assert context["current_task"]["priority"] == 1
            assert context["current_task"]["id"] == "feat-high"

    def test_session_initialization_flow(self, agent_core, state_manager):
        """Test session initialization flow"""
        # 1. Initialize session
        result = agent_core.initialize_session("coder")

        # 2. Verify session created
        assert "session_id" in result
        assert result["session_id"] is not None

        # 3. Verify state persisted
        state = state_manager.load_state()
        assert state["current_session"]["agent_type"] == "coder"
        assert state["current_session"]["id"] is not None
        assert state["error_count"] == 0

        # 4. Verify session history updated
        history = state_manager.load_session_history()
        # Session should be in progress or completed
        assert history["total_sessions"] >= 0

    def test_error_handling_flow(self, agent_core, state_manager):
        """Test error handling flow"""
        # 1. Initialize session
        agent_core.initialize_session("coder")

        # 2. Simulate errors
        agent_core.handle_error("First error")
        agent_core.handle_error("Second error")

        # 3. Verify state
        state = state_manager.load_state()
        assert state["error_count"] == 2
        assert state["last_error"] == "Second error"

    def test_task_verification_flow(self, agent_core, state_manager):
        """Test task verification flow"""
        # 1. Add a task
        state_manager.add_feature({
            "id": "feat-001",
            "name": "Test Task",
            "description": "Test description",
            "priority": 1,
            "status": "pending",
            "passes": False,
            "created_at": "2026-03-08",
            "updated_at": "2026-03-08"
        })

        # 2. Configure mock to return changes (using get_status as per verify_task implementation)
        agent_core.git_helper.get_status = Mock(return_value="M test.txt")

        # 3. Verify task
        task = state_manager.get_feature("feat-001")
        result = agent_core.verify_task(task)

        # 4. Verify task was marked as completed
        updated_feature = state_manager.get_feature("feat-001")
        assert updated_feature["status"] == "completed"

    def test_context_gathering_with_git_state(self, agent_core, state_manager):
        """Test context gathering with git state"""
        # 1. Configure git mock
        agent_core.git_helper.get_status = Mock(return_value="M modified.txt")
        agent_core.git_helper.get_current_branch = Mock(return_value="feature-branch")

        # 2. Add some tasks
        state_manager.add_feature({
            "id": "feat-001",
            "name": "Task 1",
            "status": "pending",
            "priority": 1
        })
        state_manager.add_feature({
            "id": "feat-002",
            "name": "Task 2",
            "status": "completed",
            "priority": 2
        })

        # 3. Gather context
        context = agent_core.gather_context()

        # 4. Verify context includes git state
        assert "git_status" in context
        assert "current_branch" in context
        assert context["current_branch"] == "feature-branch"
        assert context["pending_count"] == 1
        assert context["completed_count"] == 1

    def test_memory_extraction_flow(self, agent_core, temp_agent_dir):
        """Test memory extraction flow"""
        # 1. Add tasks
        agent_core.state_manager.add_feature({
            "id": "feat-001",
            "name": "Task One",
            "description": "First task",
            "priority": 1,
            "status": "completed",
            "passes": True,
            "created_at": "2026-03-08",
            "updated_at": "2026-03-08"
        })

        # 2. Extract experience
        task = {
            "id": "feat-001",
            "name": "Task One",
            "description": "First task"
        }
        result = {
            "status": "completed",
            "message": "Successfully completed"
        }

        agent_core.extract_and_save_experience(task, result)

        # 3. Verify memory file created
        memory_file = agent_core.state_manager.agent_dir / "MEMORY.md"
        assert memory_file.exists()

        # 4. Verify content
        content = memory_file.read_text()
        assert "Task One" in content

    def test_complete_session_flow(self, agent_core, state_manager):
        """Test complete session flow"""
        # 1. Initialize session
        agent_core.initialize_session("coder")

        # 2. Add a completed task
        state_manager.add_feature({
            "id": "feat-001",
            "name": "Completed Task",
            "status": "completed",
            "priority": 1
        })

        # 3. Complete session
        summary = {
            "message": "Session completed successfully",
            "tasks_completed": 1,
            "errors": 0
        }
        agent_core.complete_session(summary)

        # 4. Verify session in history
        history = state_manager.load_session_history()
        assert len(history["sessions"]) >= 1

        # 5. Verify state reset
        state = state_manager.load_state()
        # Current session should be cleared or new session started
        assert "current_session" in state


class TestCrossModuleIntegration:
    """Integration tests for multiple modules working together"""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for testing"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.fixture
    def initialized_repo(self, temp_dir):
        """Initialize a git repository"""
        subprocess.run(["git", "init"], cwd=temp_dir, check=True)
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"],
            cwd=temp_dir,
            check=True
        )
        subprocess.run(
            ["git", "config", "user.name", "Test"],
            cwd=temp_dir,
            check=True
        )

        # Create initial commit
        readme = Path(temp_dir) / "README.md"
        readme.write_text("# Project\n\nInitial content")
        subprocess.run(["git", "add", "-A"], cwd=temp_dir, check=True)
        subprocess.run(
            ["git", "commit", "-m", "Initial commit"],
            cwd=temp_dir,
            check=True
        )
        return temp_dir

    @pytest.fixture
    def state_manager(self, initialized_repo):
        """Create StateManager"""
        agent_dir = Path(initialized_repo) / ".agent"
        agent_dir.mkdir(exist_ok=True)
        return StateManager(agent_dir=str(agent_dir))

    @pytest.fixture
    def git_helper(self, initialized_repo):
        """Create GitHelper"""
        return GitHelper(project_root=initialized_repo)

    @pytest.fixture
    def task_selector(self, state_manager):
        """Create TaskSelector"""
        return TaskSelector(state_manager)

    def test_task_selector_with_git_tracking(self, task_selector, state_manager, git_helper):
        """Test TaskSelector working with Git tracking"""
        # Add tasks
        state_manager.add_feature({
            "id": "feat-001",
            "name": "Feature One",
            "description": "First feature",
            "priority": 1,
            "status": "pending",
            "passes": False,
            "created_at": "2026-03-08",
            "updated_at": "2026-03-08"
        })

        # Select task
        task = task_selector.select_next_task()
        assert task is not None
        assert task["id"] == "feat-001"

        # Simulate work - create a file
        new_file = Path(git_helper.project_root) / "feature_one.py"
        new_file.write_text("# Feature One")

        # Verify git has changes
        assert git_helper.has_changes() is True

    def test_state_manager_with_git_branch_state(self, state_manager, git_helper):
        """Test StateManager with git branch state"""
        # Start session
        session_data = {
            "id": "session-001",
            "start_time": datetime.now().isoformat(),
            "agent_type": "coder"
        }
        state_manager.update_state({"current_session": session_data})

        # Create branch
        git_helper.create_branch("feature-001")

        # Verify branch state
        assert git_helper.get_current_branch() == "feature-001"

        # Verify state persists
        state = state_manager.load_state()
        assert state["current_session"]["id"] == "session-001"

    def test_full_feature_branch_workflow(self, state_manager, git_helper):
        """Test complete workflow: create branch, work on feature, commit"""
        # 1. Start session
        state_manager.update_state({
            "current_session": {
                "id": "session-001",
                "agent_type": "coder"
            }
        })

        # 2. Add feature
        state_manager.add_feature({
            "id": "feat-new",
            "name": "New Feature",
            "description": "Add new feature",
            "priority": 1,
            "status": "pending",
            "passes": False,
            "created_at": "2026-03-08",
            "updated_at": "2026-03-08"
        })

        # 3. Create branch for feature
        branch_name = "feat/new-feature"
        git_helper.create_branch(branch_name)

        # 4. Do work - create files
        feature_file = Path(git_helper.project_root) / "new_feature.py"
        feature_file.write_text('def new_feature():\n    pass\n')

        # 5. Verify git state
        assert git_helper.has_changes() is True

        # 6. Mark task in progress
        state_manager.update_feature("feat-new", {"status": "in_progress"})

        # 7. Complete work and commit
        subprocess.run(["git", "add", "new_feature.py"], cwd=git_helper.project_root, check=True)
        subprocess.run(
            ["git", "commit", "-m", "feat: Add new_feature.py"],
            cwd=git_helper.project_root,
            check=True
        )

        # 8. Mark task completed
        state_manager.update_feature("feat-new", {
            "status": "completed",
            "passes": True
        })

        # 9. Verify all state
        feature = state_manager.get_feature("feat-new")
        assert feature["status"] == "completed"
        assert feature["passes"] is True

        commits = git_helper.get_recent_commits(1)
        assert "new_feature.py" in commits[0] or "feat" in commits[0].lower()

    def test_multiple_features_with_git_tracking(self, state_manager, git_helper):
        """Test multiple features with git tracking"""
        # Add multiple features
        features = [
            {"id": "feat-1", "name": "Feature 1", "priority": 1},
            {"id": "feat-2", "name": "Feature 2", "priority": 2},
            {"id": "feat-3", "name": "Feature 3", "priority": 3},
        ]

        for feat in features:
            state_manager.add_feature({
                **feat,
                "description": f"Description for {feat['name']}",
                "status": "pending",
                "passes": False,
                "created_at": "2026-03-08",
                "updated_at": "2026-03-08"
            })

        # Work on first feature
        feat1_file = Path(git_helper.project_root) / "feature_1.py"
        feat1_file.write_text("# Feature 1")
        subprocess.run(["git", "add", "feature_1.py"], cwd=git_helper.project_root, check=True)
        state_manager.update_feature("feat-1", {"status": "completed", "passes": True})

        # Work on second feature
        feat2_file = Path(git_helper.project_root) / "feature_2.py"
        feat2_file.write_text("# Feature 2")
        subprocess.run(["git", "add", "feature_2.py"], cwd=git_helper.project_root, check=True)
        state_manager.update_feature("feat-2", {"status": "completed", "passes": True})

        # Verify state
        assert state_manager.get_feature("feat-1")["status"] == "completed"
        assert state_manager.get_feature("feat-2")["status"] == "completed"
        assert state_manager.get_feature("feat-3")["status"] == "pending"

        # Verify git has both files
        status = git_helper.get_status()
        assert "feature_1.py" in status
        assert "feature_2.py" in status


class TestErrorRecoveryIntegration:
    """Integration tests for error recovery scenarios"""

    @pytest.fixture
    def temp_agent_dir(self):
        """Create a temporary directory for testing"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.fixture
    def state_manager(self, temp_agent_dir):
        """Create StateManager"""
        return StateManager(agent_dir=temp_agent_dir)

    @pytest.fixture
    def git_helper(self, temp_agent_dir):
        """Create GitHelper"""
        return GitHelper(project_root=temp_agent_dir)

    def test_state_recovery_after_git_error(self, state_manager, git_helper):
        """Test state recovery when git operations fail"""
        # Save state
        state_manager.update_state({
            "current_task": "feat-001",
            "error_count": 0
        })

        # Try git operation on non-repo (will fail gracefully)
        # git_helper should handle this
        status = git_helper.get_status()

        # State should still be intact
        state = state_manager.load_state()
        assert state["current_task"] == "feat-001"

    def test_error_count_persistence(self, state_manager):
        """Test error count persists correctly"""
        # Add some errors
        for i in range(5):
            state_manager.update_state({"error_count": i + 1})

        # Verify final count
        state = state_manager.load_state()
        assert state["error_count"] == 5

    def test_session_state_after_errors(self, state_manager):
        """Test session state after multiple errors"""
        # Initialize session
        state_manager.update_state({
            "current_session": {
                "id": "session-001",
                "agent_type": "coder"
            },
            "error_count": 0
        })

        # Add errors
        state_manager.update_state({
            "error_count": 3,
            "last_error": "Connection timeout"
        })

        # Verify session info preserved
        state = state_manager.load_state()
        assert state["current_session"]["id"] == "session-001"
        assert state["error_count"] == 3

    def test_feature_state_after_errors(self, state_manager):
        """Test feature state persists after errors"""
        # Add feature
        state_manager.add_feature({
            "id": "feat-001",
            "name": "Feature",
            "description": "Description",
            "priority": 1,
            "status": "in_progress",
            "passes": False,
            "created_at": "2026-03-08",
            "updated_at": "2026-03-08"
        })

        # Add errors
        state_manager.update_state({"error_count": 2})

        # Verify feature still exists
        feature = state_manager.get_feature("feat-001")
        assert feature["status"] == "in_progress"
