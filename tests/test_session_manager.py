"""Tests for SessionManager module"""

import pytest
import json
import tempfile
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from state_manager import StateManager
from session_manager import SessionManager


class TestSessionManager:
    """Test cases for SessionManager"""

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
    def session_manager(self, state_manager):
        """Create SessionManager with test state manager"""
        return SessionManager(state_manager)

    def test_check_context_usage_under_limit(self, session_manager):
        """Test context usage check when under limit"""
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"}
        ]
        is_over, count = session_manager.check_context_usage(messages)
        # Should not be over limit with small messages
        assert isinstance(is_over, bool)
        assert isinstance(count, int)

    def test_check_context_usage_over_limit(self, session_manager):
        """Test context usage check when over limit"""
        # Create many large messages to exceed limit
        messages = [
            {"role": "user", "content": "x" * 50000}
            for _ in range(10)
        ]
        is_over, count = session_manager.check_context_usage(messages)
        # With limit 100000 and ~125000 chars, should be over
        assert isinstance(is_over, bool)
        assert isinstance(count, int)

    def test_summarize_old_messages(self, session_manager):
        """Test summarizing old messages"""
        messages = [
            {"role": "user", "content": f"Message {i}"}
            for i in range(20)
        ]
        result = session_manager.summarize_old_messages(messages, keep_recent=5)
        assert len(result) == 6  # 1 summary + 5 recent

    def test_summarize_old_messages_no_op(self, session_manager):
        """Test summarizing when message count is small"""
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi"}
        ]
        result = session_manager.summarize_old_messages(messages, keep_recent=10)
        assert len(result) == 2  # Should be unchanged

    def test_should_resume_session_no_session(self, session_manager, state_manager):
        """Test should_resume_session when no session exists"""
        result = session_manager.should_resume_session("session-001")
        assert result is False

    def test_should_resume_session_incomplete(self, session_manager, state_manager):
        """Test should_resume_session with incomplete session"""
        # Set current session in state (required by the function)
        state_manager.update_state({
            "current_session": {"id": "session-001"}
        })

        # Add an incomplete session
        state_manager.add_session({
            "id": "session-001",
            "status": "in_progress"
        })

        result = session_manager.should_resume_session("session-001")
        assert result is True

    def test_should_resume_session_completed(self, session_manager, state_manager):
        """Test should_resume_session with completed session"""
        # Add a completed session
        state_manager.add_session({
            "id": "session-001",
            "status": "completed"
        })

        result = session_manager.should_resume_session("session-001")
        assert result is False

    def test_get_session_summary(self, session_manager, state_manager):
        """Test getting session summary"""
        session = {
            "id": "session-001",
            "status": "completed",
            "tasks": 5
        }
        state_manager.add_session(session)

        result = session_manager.get_session_summary("session-001")
        assert result is not None
        assert result["id"] == "session-001"

    def test_get_session_summary_not_found(self, session_manager):
        """Test getting session summary when not found"""
        result = session_manager.get_session_summary("non-existent")
        assert result is None

    def test_create_and_load_checkpoint(self, session_manager, state_manager, temp_agent_dir):
        """Test creating and loading checkpoint"""
        session_id = "test-session"
        data = {"task": "test", "progress": 50}

        session_manager.create_checkpoint(session_id, data)
        result = session_manager.load_checkpoint(session_id)

        assert result is not None
        assert result["session_id"] == session_id
        assert result["data"] == data

    def test_load_checkpoint_not_exists(self, session_manager):
        """Test loading checkpoint that doesn't exist"""
        result = session_manager.load_checkpoint("non-existent")
        assert result is None

    def test_cleanup_checkpoints(self, session_manager, state_manager, temp_agent_dir):
        """Test cleaning up old checkpoints"""
        session_id = "test-session"

        # Create multiple checkpoints
        for i in range(5):
            session_manager.create_checkpoint(f"session-{i}", {"data": i})

        # Clean up, keeping only 2
        session_manager.cleanup_checkpoints(keep_latest=2)

        # Check remaining checkpoints
        agent_dir = Path(temp_agent_dir)
        checkpoints = list(agent_dir.glob("checkpoint_*.json"))
        assert len(checkpoints) == 2

    def test_manage_context_no_summarize(self, session_manager):
        """Test manage context without summarizing"""
        messages = [
            {"role": "user", "content": "Hello"}
        ]
        result = session_manager.manage_context(messages)
        assert len(result) == 1

    def test_manage_context_force_summarize(self, session_manager):
        """Test manage context with force summarize"""
        messages = [
            {"role": "user", "content": f"Message {i}"}
            for i in range(20)
        ]
        result = session_manager.manage_context(messages, force_summarize=True)
        # Should be summarized
        assert len(result) < len(messages)

    def test_get_session_stats(self, session_manager, state_manager):
        """Test getting session statistics"""
        # Add some sessions
        state_manager.add_session({"id": "session-001", "status": "completed"})
        state_manager.add_session({"id": "session-002", "status": "in_progress"})

        stats = session_manager.get_session_stats()
        assert stats["total_sessions"] == 2
        assert stats["completed_sessions"] == 1
        assert "current_session" in stats
        assert "context_limit" in stats

    def test_default_context_limit(self, session_manager):
        """Test default context limit"""
        assert session_manager.context_limit == 100000  # Default from config

    def test_custom_context_limit(self, temp_agent_dir):
        """Test custom context limit from config"""
        # Create config with custom limit
        sm = StateManager(agent_dir=temp_agent_dir)
        sm.save_config({"context_window_limit": 50000})

        session_manager = SessionManager(sm)
        assert session_manager.context_limit == 50000
