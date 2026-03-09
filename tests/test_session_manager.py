"""Tests for SessionManager module"""

import pytest
import json
import tempfile
from pathlib import Path
from datetime import datetime, timedelta
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from agent.state_manager import StateManager
from agent.session_manager import SessionManager


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


class TestSessionTagging:
    """Test cases for session tagging features"""

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

    def test_add_session_tag(self, session_manager, state_manager):
        """Test adding a tag to a session"""
        state_manager.add_session({"id": "session-001", "status": "completed"})

        success = session_manager.add_session_tag("session-001", "bugfix")
        assert success is True

        # Verify tag was added
        session = session_manager.get_session_summary("session-001")
        assert "bugfix" in session.get("tags", [])

    def test_add_session_tag_not_found(self, session_manager):
        """Test adding a tag to a non-existent session"""
        success = session_manager.add_session_tag("non-existent", "bugfix")
        assert success is False

    def test_remove_session_tag(self, session_manager, state_manager):
        """Test removing a tag from a session"""
        state_manager.add_session({
            "id": "session-001",
            "status": "completed",
            "tags": ["bugfix", "urgent"]
        })

        success = session_manager.remove_session_tag("session-001", "bugfix")
        assert success is True

        # Verify tag was removed
        session = session_manager.get_session_summary("session-001")
        assert "bugfix" not in session.get("tags", [])
        assert "urgent" in session.get("tags", [])

    def test_get_sessions_by_tag(self, session_manager, state_manager):
        """Test getting sessions by tag"""
        state_manager.add_session({
            "id": "session-001",
            "status": "completed",
            "tags": ["bugfix"]
        })
        state_manager.add_session({
            "id": "session-002",
            "status": "completed",
            "tags": ["feature"]
        })
        state_manager.add_session({
            "id": "session-003",
            "status": "completed",
            "tags": ["bugfix", "urgent"]
        })

        sessions = session_manager.get_sessions_by_tag("bugfix")
        assert len(sessions) == 2
        ids = [s["id"] for s in sessions]
        assert "session-001" in ids
        assert "session-003" in ids

    def test_get_all_tags(self, session_manager, state_manager):
        """Test getting all tags with counts"""
        state_manager.add_session({
            "id": "session-001",
            "status": "completed",
            "tags": ["bugfix", "urgent"]
        })
        state_manager.add_session({
            "id": "session-002",
            "status": "completed",
            "tags": ["feature", "bugfix"]
        })
        state_manager.add_session({
            "id": "session-003",
            "status": "completed",
            "tags": []
        })

        tags = session_manager.get_all_tags()
        assert tags.get("bugfix", 0) == 2
        assert tags.get("urgent", 0) == 1
        assert tags.get("feature", 0) == 1


class TestSessionArchiving:
    """Test cases for session archiving features"""

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


class TestSmartCompression:
    """Test cases for smart context compression"""

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

    def test_is_important_message_error(self, session_manager):
        """Test detecting error messages as important"""
        msg = {"role": "assistant", "content": "Error: Something went wrong"}
        assert session_manager._is_important_message(msg) is True

    def test_is_important_message_code(self, session_manager):
        """Test detecting code content as important"""
        msg = {"role": "assistant", "content": "```python\ndef hello():\n    pass\n```"}
        assert session_manager._is_important_message(msg) is True

    def test_is_important_message_decision(self, session_manager):
        """Test detecting decisions as important"""
        msg = {"role": "assistant", "content": "We decided to use the new API"}
        assert session_manager._is_important_message(msg) is True

    def test_is_important_message_routine(self, session_manager):
        """Test routine messages are not marked important"""
        msg = {"role": "user", "content": "Hello, how are you?"}
        assert session_manager._is_important_message(msg) is False

    def test_compress_preserves_important_messages(self, session_manager):
        """Test compression preserves important content"""
        messages = [
            {"role": "user", "content": f"Message {i}"}
            for i in range(15)
        ]
        # Add an important message
        messages[5] = {"role": "assistant", "content": "Error: Failed to process"}

        result = session_manager.summarize_old_messages(messages, keep_recent=5)

        # Should have summary + important + recent
        assert len(result) < len(messages)
        # Check that important message is preserved
        content = " ".join(str(m) for m in result)
        assert "Error" in content


class TestIncrementalTokenCounting:
    """Test cases for incremental token counting"""

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

    def test_incremental_token_counting(self, session_manager):
        """Test incremental token counting"""
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi!"}
        ]

        # First call - full count
        is_over, count1 = session_manager.check_context_usage(messages)
        assert count1 > 0

        # Add a message and call again - should be incremental
        messages.append({"role": "user", "content": "How are you?"})
        is_over, count2 = session_manager.check_context_usage(messages)
        assert count2 > count1

    def test_force_recalculate(self, session_manager):
        """Test force recalculate option"""
        messages = [
            {"role": "user", "content": "Hello"},
        ]

        # First call
        _, count1 = session_manager.check_context_usage(messages)

        # Force recalculate
        _, count2 = session_manager.check_context_usage(messages, force_recalculate=True)
        assert count1 == count2


class TestSessionStats:
    """Test cases for session statistics"""

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

    def test_get_detailed_stats_empty(self, session_manager):
        """Test detailed stats with no sessions"""
        stats = session_manager.get_detailed_stats()
        assert stats["summary"]["total_sessions"] == 0
        assert "duration" in stats
        assert "errors" in stats

    def test_get_detailed_stats_with_sessions(self, session_manager, state_manager):
        """Test detailed stats with sessions"""
        # Add completed sessions with durations
        now = datetime.now()
        state_manager.add_session({
            "id": "session-001",
            "status": "completed",
            "created_at": now.isoformat(),
            "start_time": (now - timedelta(hours=1)).isoformat(),
            "end_time": now.isoformat(),
            "last_error": "timeout error"
        })
        state_manager.add_session({
            "id": "session-002",
            "status": "failed",
            "created_at": now.isoformat(),
            "last_error": "connection failed"
        })
        state_manager.add_session({
            "id": "session-003",
            "status": "in_progress",
            "created_at": now.isoformat()
        })

        stats = session_manager.get_detailed_stats()
        assert stats["summary"]["total_sessions"] == 3
        assert stats["summary"]["completed_sessions"] == 1
        assert stats["summary"]["failed_sessions"] == 1
        assert stats["summary"]["in_progress_sessions"] == 1

        # Check error types
        assert "timeout" in stats["errors"]
        assert "connection" in stats["errors"]


class TestBackwardCompatibility:
    """Test cases for backward compatibility"""

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

    def test_migrate_session_format(self, session_manager):
        """Test migration of old session format"""
        old_session = {
            "id": "old-session",
            "status": "completed",
            # Missing: tags, created_at
        }

        migrated = session_manager.migrate_session_format(old_session)

        assert "tags" in migrated
        assert migrated["tags"] == []
        assert "created_at" in migrated
        assert "status" in migrated

    def test_load_and_migrate_history(self, session_manager, state_manager):
        """Test loading and migrating old history"""
        # Add old format sessions
        state_manager.add_session({
            "id": "session-001",
            "status": "completed"
            # No tags, created_at
        })

        # Load and migrate
        history = session_manager.load_and_migrate_history()

        # Should have migrated data
        assert len(history["sessions"]) == 1
        assert "tags" in history["sessions"][0]


class TestEnhancedSessionResume:
    """Test cases for enhanced session resume"""

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

    def test_get_session_for_resume(self, session_manager, state_manager):
        """Test getting enhanced session data for resume"""
        # Add session
        state_manager.add_session({
            "id": "session-001",
            "status": "in_progress",
            "created_at": datetime.now().isoformat()
        })

        # Update state with additional info
        state_manager.update_state({
            "error_count": 3,
            "current_task": {"id": "task-001", "name": "Test task"},
            "last_error": "timeout"
        })

        # Create checkpoint
        session_manager.create_checkpoint("session-001", {"progress": 50})

        # Get session for resume
        resume_data = session_manager.get_session_for_resume("session-001")

        assert resume_data is not None
        assert resume_data.get("error_count") == 3
        assert resume_data.get("current_task") == {"id": "task-001", "name": "Test task"}
        assert resume_data.get("checkpoint_data", {}).get("progress") == 50

    def test_get_session_for_resume_not_found(self, session_manager):
        """Test getting resume data for non-existent session"""
        result = session_manager.get_session_for_resume("non-existent")
        assert result is None
