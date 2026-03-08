"""Session Manager - 会话管理模块

处理上下文窗口，保持会话状态
"""

import json
import logging
import re
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, cast

from .state_manager import StateManager

logger = logging.getLogger(__name__)

# Try to import tiktoken for accurate token counting
try:
    import tiktoken

    _tokenizer = tiktoken.get_encoding("cl100k_base")
except ImportError:
    _tokenizer = None
    logger.warning("tiktoken not available, falling back to character-based estimation")


def count_tokens(text: str) -> int:
    """Count tokens in text using tiktoken (accurate) or fallback estimation.

    Args:
        text: Text to count tokens for

    Returns:
        Estimated token count
    """
    if _tokenizer is not None:
        try:
            return len(_tokenizer.encode(text))
        except Exception as e:
            logger.warning(f"tiktoken encoding failed: {e}, falling back to estimation")
            return len(text) // 4
    else:
        # Fallback: simple character-based estimation
        return len(text) // 4


# Configuration constants (can be overridden via config)
DEFAULT_ARCHIVE_AFTER_DAYS = 30
DEFAULT_MAX_SESSIONS_BEFORE_ARCHIVE = 100
DEFAULT_KEEP_RECENT_MESSAGES = 10
MAX_TOKEN_CACHE_ENTRIES = 500


class SessionManager:
    """会话管理器 - 增强版

    Features:
    - Session archiving: Auto-archive old sessions to .agent/archive/
    - Smart context compression: Preserve important content
    - Incremental token counting: Cache token counts for efficiency
    - Enhanced session resume: Restore task state, git diff, error counts
    - Session tagging: Add tags for categorization
    - Session statistics: Comprehensive analytics
    """

    def __init__(self, state_manager: StateManager | None = None) -> None:
        self.state_manager = state_manager or StateManager()
        self.config = self.state_manager.load_config()
        self.context_limit = self.config.get("context_window_limit", 100000)

        # Archive settings
        self.archive_after_days = self.config.get(
            "session_archive_after_days", DEFAULT_ARCHIVE_AFTER_DAYS
        )
        self.max_sessions_before_archive = self.config.get(
            "session_max_before_archive", DEFAULT_MAX_SESSIONS_BEFORE_ARCHIVE
        )

        # Token count cache for incremental counting
        self._token_cache: dict[str, int] = {}
        self._last_total_tokens = 0

        # Archive directory
        self.archive_dir = self.state_manager.agent_dir / "archive"

    def _ensure_archive_dir(self) -> None:
        """Ensure archive directory exists"""
        self.archive_dir.mkdir(parents=True, exist_ok=True)

    # ========== Token Counting (Incremental) ==========

    def check_context_usage(
        self, messages: list[dict[str, Any]], force_recalculate: bool = False
    ) -> tuple[bool, int]:
        """Check context usage with incremental token counting.

        Args:
            messages: Message list to check
            force_recalculate: If True, recalculate all tokens instead of using cache

        Returns:
            (is_over_limit: bool, token_count: int)
        """
        if force_recalculate or not self._token_cache:
            # Full recalculation
            total_tokens = 0
            for i, m in enumerate(messages):
                msg_text = json.dumps(m)
                token_count = count_tokens(msg_text)
                self._token_cache[str(i)] = token_count
                total_tokens += token_count
            self._last_total_tokens = total_tokens
        else:
            # Incremental: calculate only for new messages
            total_tokens = self._last_total_tokens
            for i in range(len(self._token_cache), len(messages)):
                msg_text = json.dumps(messages[i])
                token_count = count_tokens(msg_text)
                self._token_cache[str(i)] = token_count
                total_tokens += token_count
            self._last_total_tokens = total_tokens

        return total_tokens > self.context_limit, total_tokens

    def update_token_cache(self, messages: list[dict[str, Any]]) -> None:
        """Update token cache when messages are added/removed.

        Args:
            messages: Current message list
        """
        # Clear cache if message count changed significantly or cache is too large
        if (abs(len(messages) - len(self._token_cache)) > 5
                or len(self._token_cache) > MAX_TOKEN_CACHE_ENTRIES):
            self._token_cache.clear()
            self._last_total_tokens = 0

    # ========== Smart Context Compression ==========

    def _is_important_message(self, message: dict[str, Any]) -> bool:
        """Determine if a message contains important content.

        Important content includes:
        - Code modifications
        - Error messages
        - Key decisions
        - File operations

        Args:
            message: Message to check

        Returns:
            True if message is important
        """
        content = message.get("content", "")
        role = message.get("role", "")

        # System messages with summaries are important
        if role == "system" and "summary" in content.lower():
            return True

        # Check for important keywords
        important_patterns = [
            r"\b(error|exception|failed|failure)\b",
            r"\b(fix|bug|issue|problem)\b",
            r"\b(decision|decided|choose|selected)\b",
            r"(```|```python|```javascript|```bash)",
            r"\b(commit|push|merge|branch)\b",
            r"\b(test|assert|verify)\b",
        ]

        for pattern in important_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                return True

        return False

    def _compress_messages_smart(
        self, messages: list[dict[str, Any]], keep_recent: int = 10
    ) -> list[dict[str, Any]]:
        """Compress messages while preserving important content.

        This method keeps:
        - Recent messages (configurable count)
        - Messages containing code changes, errors, or key decisions

        Args:
            messages: Full message list
            keep_recent: Number of recent messages to keep

        Returns:
            Compressed message list
        """
        if len(messages) <= keep_recent:
            return messages

        # Separate recent and old messages
        recent = messages[-keep_recent:]
        old = messages[:-keep_recent]

        # Extract important messages from old
        important: list[dict[str, Any]] = []
        for msg in old:
            if self._is_important_message(msg):
                # Create a condensed version of important messages
                important.append(self._condense_message(msg))

        # Build summary for discarded messages
        discarded_count = len(old) - len(important)
        summary = {
            "role": "system",
            "content": self._generate_compression_summary(
                discarded_count, len(important), len(messages)
            ),
        }

        # Combine: summary + important messages + recent
        result = [summary] + important + recent

        return result

    def _condense_message(self, message: dict[str, Any]) -> dict[str, Any]:
        """Condense a message while preserving key information.

        Args:
            message: Original message

        Returns:
            Condensed message
        """
        content = message.get("content", "")

        # Truncate long content but keep structure
        max_content_length = 2000
        if len(content) > max_content_length:
            content = content[:max_content_length] + "... [truncated]"

        return {
            "role": message.get("role", "assistant"),
            "content": content,
            "important": True,  # Mark as important
        }

    def _generate_compression_summary(
        self, discarded: int, important: int, total: int
    ) -> str:
        """Generate a summary message for compressed content.

        Args:
            discarded: Number of discarded messages
            important: Number of important messages preserved
            total: Total original messages

        Returns:
            Summary string
        """
        return (
            f"Previous session summary: {total} total messages. "
            f"{discarded} routine messages compressed. "
            f"{important} important messages preserved "
            f"(code changes, errors, decisions)."
        )

    def summarize_old_messages(
        self, messages: list[dict[str, Any]], keep_recent: int = 10
    ) -> list[dict[str, Any]]:
        """Summarize old messages to save context (smart compression).

        Args:
            messages: Message list
            keep_recent: Number of recent messages to keep

        Returns:
            Compressed message list
        """
        # Use smart compression instead of simple summary
        return self._compress_messages_smart(messages, keep_recent)

    # ========== Session Archiving ==========

    def _get_archive_filename(self, date: datetime) -> str:
        """Get archive filename for a given date.

        Args:
            date: Date for the archive

        Returns:
            Archive filename (e.g., "archive_2026-03.json")
        """
        return f"archive_{date.strftime('%Y-%m')}.json"

    def _archive_session(self, session: dict[str, Any]) -> None:
        """Archive a single session to the archive directory.

        Args:
            session: Session to archive
        """
        self._ensure_archive_dir()

        # Get session date or use current date
        created_at = session.get("created_at", datetime.now().isoformat())
        try:
            session_date = datetime.fromisoformat(created_at)
        except (ValueError, TypeError):
            session_date = datetime.now()

        archive_file = self.archive_dir / self._get_archive_filename(session_date)

        # Load or create archive file
        archive_data: dict[str, Any]
        if archive_file.exists():
            try:
                with open(archive_file, "r", encoding="utf-8") as f:
                    archive_data = json.load(f)
            except (json.JSONDecodeError, IOError):
                archive_data = {"sessions": []}
        else:
            archive_data = {"sessions": []}

        # Add session to archive
        archive_data["sessions"].append(session)

        # Save archive file
        try:
            with open(archive_file, "w", encoding="utf-8") as f:
                json.dump(archive_data, f, indent=2, ensure_ascii=False)
            logger.info(f"Archived session {session.get('id')} to {archive_file}")
        except IOError as e:
            logger.error(f"Failed to archive session: {e}")

    def _should_archive_session(self, session: dict[str, Any]) -> bool:
        """Check if a session should be archived based on age.

        Args:
            session: Session to check

        Returns:
            True if session should be archived
        """
        created_at = session.get("created_at")
        if not created_at:
            return False

        try:
            session_date = datetime.fromisoformat(created_at)
            age_days = (datetime.now() - session_date).days
            return age_days > self.archive_after_days
        except (ValueError, TypeError):
            return False

    def archive_old_sessions(self) -> int:
        """Archive old sessions based on age and count thresholds.

        This method:
        1. Archives sessions older than archive_after_days
        2. If total sessions exceed max_sessions_before_archive, archives oldest

        Returns:
            Number of sessions archived
        """
        history = self.state_manager.load_session_history()
        sessions = history.get("sessions", [])

        if not sessions:
            return 0

        archived_count = 0

        # Archive by age
        sessions_to_archive: list[dict[str, Any]] = []
        remaining_sessions: list[dict[str, Any]] = []

        for session in sessions:
            if self._should_archive_session(session):
                sessions_to_archive.append(session)
            else:
                remaining_sessions.append(session)

        # Archive by count if still over limit
        if len(remaining_sessions) > self.max_sessions_before_archive:
            # Sort by date and archive oldest
            remaining_sessions.sort(
                key=lambda s: s.get("created_at", ""), reverse=False
            )
            excess = len(remaining_sessions) - self.max_sessions_before_archive
            for session in remaining_sessions[:excess]:
                sessions_to_archive.append(session)
            remaining_sessions = remaining_sessions[excess:]

        # Actually archive sessions
        for session in sessions_to_archive:
            self._archive_session(session)
            archived_count += 1

        # Update history with remaining sessions
        if archived_count > 0:
            history["sessions"] = remaining_sessions
            history["total_sessions"] = len(remaining_sessions)
            self.state_manager.save_session_history(history)
            logger.info(f"Archived {archived_count} sessions, {len(remaining_sessions)} remaining")

        return archived_count

    def get_archived_sessions(
        self, year: int | None = None, month: int | None = None
    ) -> list[dict[str, Any]]:
        """Get archived sessions, optionally filtered by year/month.

        Args:
            year: Optional year filter
            month: Optional month filter

        Returns:
            List of archived sessions
        """
        self._ensure_archive_dir()

        if year and month:
            # Single month file
            archive_file = self.archive_dir / f"archive_{year:04d}-{month:02d}.json"
            if archive_file.exists():
                with open(archive_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return data.get("sessions", [])
            return []

        # All archive files
        all_sessions: list[dict[str, Any]] = []
        for archive_file in sorted(self.archive_dir.glob("archive_*.json")):
            try:
                with open(archive_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    all_sessions.extend(data.get("sessions", []))
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Failed to read archive {archive_file}: {e}")

        return all_sessions

    # ========== Session Resume (Enhanced) ==========

    def should_resume_session(self, session_id: str) -> bool:
        """Check if we should resume a previous session."""
        state = self.state_manager.load_state()
        current_session = state.get("current_session", {})

        if not current_session.get("id"):
            return False

        # Check if previous session didn't end normally
        history = self.state_manager.load_session_history()
        sessions: list[dict[str, Any]] = history.get("sessions", [])
        for session in sessions:
            if session.get("id") == session_id:
                status: str = cast(str, session.get("status"))
                return status != "completed"

        return False

    def get_session_for_resume(self, session_id: str) -> dict[str, Any] | None:
        """Get enhanced session data for resuming.

        Returns session data including:
        - Messages
        - Task state
        - Error count
        - Git diff (if available)
        - Checkpoint data

        Args:
            session_id: Session ID to resume

        Returns:
            Session data dict or None
        """
        # Load session from history
        history = self.state_manager.load_session_history()
        sessions = history.get("sessions", [])

        session = None
        for s in sessions:
            if s.get("id") == session_id:
                session = s
                break

        if not session:
            return None

        # Load checkpoint for additional context
        checkpoint = self.load_checkpoint(session_id)
        if checkpoint:
            session["checkpoint_data"] = checkpoint.get("data", {})

        # Load state for error counts and task info
        state = self.state_manager.load_state()
        session["error_count"] = state.get("error_count", 0)
        session["current_task"] = state.get("current_task")
        session["last_error"] = state.get("last_error")

        return session

    # ========== Session Tagging ==========

    def add_session_tag(self, session_id: str, tag: str) -> bool:
        """Add a tag to a session.

        Args:
            session_id: Session ID
            tag: Tag to add

        Returns:
            True if tag was added successfully
        """
        history = self.state_manager.load_session_history()
        sessions = history.get("sessions", [])

        for session in sessions:
            if session.get("id") == session_id:
                if "tags" not in session:
                    session["tags"] = []
                if tag not in session["tags"]:
                    session["tags"].append(tag)
                history["sessions"] = sessions
                self.state_manager.save_session_history(history)
                return True

        return False

    def remove_session_tag(self, session_id: str, tag: str) -> bool:
        """Remove a tag from a session.

        Args:
            session_id: Session ID
            tag: Tag to remove

        Returns:
            True if tag was removed successfully
        """
        history = self.state_manager.load_session_history()
        sessions = history.get("sessions", [])

        for session in sessions:
            if session.get("id") == session_id:
                if "tags" in session and tag in session["tags"]:
                    session["tags"].remove(tag)
                    history["sessions"] = sessions
                    self.state_manager.save_session_history(history)
                    return True

        return False

    def get_sessions_by_tag(self, tag: str) -> list[dict[str, Any]]:
        """Get all sessions with a specific tag.

        Args:
            tag: Tag to filter by

        Returns:
            List of sessions with the tag
        """
        history = self.state_manager.load_session_history()
        sessions = history.get("sessions", [])

        return [s for s in sessions if tag in s.get("tags", [])]

    def get_all_tags(self) -> dict[str, int]:
        """Get all tags and their usage counts.

        Returns:
            Dict mapping tags to counts
        """
        history = self.state_manager.load_session_history()
        sessions = history.get("sessions", [])

        tags: dict[str, int] = {}
        for session in sessions:
            for tag in session.get("tags", []):
                tags[tag] = tags.get(tag, 0) + 1

        return tags

    # ========== Session Statistics ==========

    def get_session_stats(self) -> dict[str, Any]:
        """Get basic session statistics."""
        history = self.state_manager.load_session_history()
        state = self.state_manager.load_state()

        sessions = history.get("sessions", [])
        completed_sessions = [s for s in sessions if s.get("status") == "completed"]

        return {
            "total_sessions": len(sessions),
            "completed_sessions": len(completed_sessions),
            "current_session": state.get("current_session", {}),
            "context_limit": self.context_limit,
        }

    def get_detailed_stats(self) -> dict[str, Any]:
        """Get detailed session statistics.

        Returns:
            Comprehensive statistics including:
            - Average session duration
            - Task completion rate
            - Most common error types
            - Daily/weekly trends
            - Tag distribution
        """
        history = self.state_manager.load_session_history()
        sessions = history.get("sessions", [])

        if not sessions:
            return self._empty_stats()

        # Basic counts
        total = len(sessions)
        completed = sum(1 for s in sessions if s.get("status") == "completed")
        failed = sum(1 for s in sessions if s.get("status") == "failed")
        in_progress = sum(1 for s in sessions if s.get("status") == "in_progress")

        # Duration stats
        durations = self._calculate_durations(sessions)
        avg_duration = sum(durations) / len(durations) if durations else 0

        # Error analysis
        error_types = self._analyze_errors(sessions)

        # Tag distribution
        tag_counts = self.get_all_tags()

        # Daily/weekly trends
        daily_trend = self._calculate_daily_trend(sessions)
        weekly_trend = self._calculate_weekly_trend(sessions)

        # Task completion rate
        task_completion_rate = (completed / total * 100) if total > 0 else 0

        return {
            "summary": {
                "total_sessions": total,
                "completed_sessions": completed,
                "failed_sessions": failed,
                "in_progress_sessions": in_progress,
                "completion_rate": round(task_completion_rate, 2),
            },
            "duration": {
                "average_seconds": round(avg_duration, 2),
                "min_seconds": round(min(durations), 2) if durations else 0,
                "max_seconds": round(max(durations), 2) if durations else 0,
            },
            "errors": error_types,
            "tags": tag_counts,
            "trends": {
                "daily": daily_trend,
                "weekly": weekly_trend,
            },
            "archive_info": {
                "archived_sessions": len(self.get_archived_sessions()),
                "archive_threshold_days": self.archive_after_days,
                "max_sessions_before_archive": self.max_sessions_before_archive,
            },
        }

    def _empty_stats(self) -> dict[str, Any]:
        """Return empty stats structure."""
        return {
            "summary": {
                "total_sessions": 0,
                "completed_sessions": 0,
                "failed_sessions": 0,
                "in_progress_sessions": 0,
                "completion_rate": 0,
            },
            "duration": {
                "average_seconds": 0,
                "min_seconds": 0,
                "max_seconds": 0,
            },
            "errors": {},
            "tags": {},
            "trends": {"daily": [], "weekly": []},
            "archive_info": {
                "archived_sessions": 0,
                "archive_threshold_days": self.archive_after_days,
                "max_sessions_before_archive": self.max_sessions_before_archive,
            },
        }

    def _calculate_durations(self, sessions: list[dict[str, Any]]) -> list[float]:
        """Calculate durations for sessions with start/end times."""
        durations = []
        for session in sessions:
            start = session.get("start_time")
            end = session.get("end_time") or session.get("completed_at")
            if start and end:
                try:
                    start_dt = datetime.fromisoformat(start)
                    end_dt = datetime.fromisoformat(end)
                    duration = (end_dt - start_dt).total_seconds()
                    if duration > 0:
                        durations.append(duration)
                except (ValueError, TypeError):
                    pass
        return durations

    def _analyze_errors(self, sessions: list[dict[str, Any]]) -> dict[str, int]:
        """Analyze error types across sessions."""
        error_counts: dict[str, int] = {}
        for session in sessions:
            error = session.get("last_error") or session.get("error")
            if error:
                # Categorize errors
                error_str = str(error).lower()
                if "timeout" in error_str:
                    error_counts["timeout"] = error_counts.get("timeout", 0) + 1
                elif "connection" in error_str:
                    error_counts["connection"] = error_counts.get("connection", 0) + 1
                elif "permission" in error_str or "auth" in error_str:
                    error_counts["permission"] = error_counts.get("permission", 0) + 1
                elif "memory" in error_str:
                    error_counts["memory"] = error_counts.get("memory", 0) + 1
                else:
                    error_counts["other"] = error_counts.get("other", 0) + 1
        return error_counts

    def _calculate_daily_trend(
        self, sessions: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Calculate daily session trends."""
        daily: dict[str, dict[str, int]] = {}
        for session in sessions:
            created = session.get("created_at")
            if created:
                try:
                    date = datetime.fromisoformat(created).strftime("%Y-%m-%d")
                    if date not in daily:
                        daily[date] = {"total": 0, "completed": 0}
                    daily[date]["total"] += 1
                    if session.get("status") == "completed":
                        daily[date]["completed"] += 1
                except (ValueError, TypeError):
                    pass

        # Sort by date and return last 30 days
        sorted_dates = sorted(daily.keys(), reverse=True)[:30]
        return [
            {"date": date, **daily[date]}
            for date in reversed(sorted_dates)
        ]

    def _calculate_weekly_trend(
        self, sessions: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Calculate weekly session trends."""
        weekly: dict[str, dict[str, int]] = {}
        for session in sessions:
            created = session.get("created_at")
            if created:
                try:
                    dt = datetime.fromisoformat(created)
                    week = dt.strftime("%Y-W%U")
                    if week not in weekly:
                        weekly[week] = {"total": 0, "completed": 0}
                    weekly[week]["total"] += 1
                    if session.get("status") == "completed":
                        weekly[week]["completed"] += 1
                except (ValueError, TypeError):
                    pass

        # Sort by week and return last 12 weeks
        sorted_weeks = sorted(weekly.keys(), reverse=True)[:12]
        return [
            {"week": week, **weekly[week]}
            for week in reversed(sorted_weeks)
        ]

    # ========== Backward Compatibility ==========

    def migrate_session_format(self, session: dict[str, Any]) -> dict[str, Any]:
        """Migrate old session format to new format.

        Ensures backward compatibility with old session_history.json files.

        Args:
            session: Session data (may be old format)

        Returns:
            Migrated session with new fields
        """
        migrated = session.copy()

        # Add tags field if missing
        if "tags" not in migrated:
            migrated["tags"] = []

        # Add created_at if missing (backward compatibility)
        if "created_at" not in migrated:
            migrated["created_at"] = migrated.get(
                "start_time", datetime.now().isoformat()
            )

        # Add status if missing
        if "status" not in migrated:
            migrated["status"] = "unknown"

        return migrated

    def load_and_migrate_history(self) -> dict[str, Any]:
        """Load session history and migrate old formats.

        Returns:
            Migrated session history
        """
        history = self.state_manager.load_session_history()
        sessions = history.get("sessions", [])

        # Migrate each session
        migrated_sessions = [self.migrate_session_format(s) for s in sessions]
        history["sessions"] = migrated_sessions

        # Save migrated history if changes were made
        if migrated_sessions != sessions:
            self.state_manager.save_session_history(history)

        return history

    # ========== Checkpoint Management ==========

    def get_session_summary(self, session_id: str) -> dict[str, Any] | None:
        """Get session summary."""
        history = self.state_manager.load_session_history()
        sessions: list[dict[str, Any]] = history.get("sessions", [])

        for session in sessions:
            if session.get("id") == session_id:
                return session

        return None

    def create_checkpoint(self, session_id: str, data: dict[str, Any]) -> None:
        """Create session checkpoint."""
        checkpoint_file = self.state_manager.agent_dir / f"checkpoint_{session_id}.json"

        checkpoint = {
            "session_id": session_id,
            "timestamp": datetime.now().isoformat(),
            "data": data,
        }

        try:
            with open(checkpoint_file, "w") as f:
                json.dump(checkpoint, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to create checkpoint for session {session_id}: {e}")

    def load_checkpoint(self, session_id: str) -> dict[str, Any] | None:
        """Load session checkpoint."""
        checkpoint_file = self.state_manager.agent_dir / f"checkpoint_{session_id}.json"

        if not checkpoint_file.exists():
            return None

        try:
            with open(checkpoint_file, "r") as f:
                return cast(dict[str, Any], json.load(f))
        except Exception as e:
            logger.error(f"Failed to load checkpoint for session {session_id}: {e}")
            return None

    def cleanup_checkpoints(self, keep_latest: int = 3) -> None:
        """Clean up old checkpoints."""
        agent_dir = self.state_manager.agent_dir

        checkpoints = sorted(
            agent_dir.glob("checkpoint_*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )

        for checkpoint in checkpoints[keep_latest:]:
            try:
                checkpoint.unlink()
            except Exception as e:
                logger.warning(f"Failed to delete checkpoint {checkpoint}: {e}")

    # ========== Context Management ==========

    def manage_context(
        self, messages: list[dict[str, Any]], force_summarize: bool = False
    ) -> list[dict[str, Any]]:
        """Manage context window.

        Args:
            messages: Current message list
            force_summarize: Force summarization

        Returns:
            Managed message list
        """
        is_over_limit, token_count = self.check_context_usage(messages)

        if is_over_limit or force_summarize:
            return self.summarize_old_messages(messages)

        return messages
