"""Tests for the exception hierarchy module."""

import pytest
from agent.exceptions import (
    ErrorCode,
    AgentLoopError,
    ConfigError,
    ConfigValidationError,
    ConfigReloadError,
    TaskExecutionError,
    TaskTimeoutError,
    TaskRetryExhaustedError,
    ProviderError,
    ProviderAuthError,
    ProviderRateLimitError,
    ProviderConnectionError,
    NotificationError,
    WebhookError,
    EmailError,
    SlackError,
    SessionError,
    SessionCorruptError,
    SessionNotFoundError,
    StateError,
    StateCorruptError,
    StateNotFoundError,
    StateReadError,
    StateWriteError,
)


class TestErrorCode:
    """Tests for ErrorCode enum."""

    def test_error_code_values(self):
        """Test that error codes have correct values."""
        assert ErrorCode.E1001.value == "E1001"
        assert ErrorCode.E2001.value == "E2001"
        assert ErrorCode.E3001.value == "E3001"
        assert ErrorCode.E4001.value == "E4001"
        assert ErrorCode.E5001.value == "E5001"
        assert ErrorCode.E6001.value == "E6001"
        assert ErrorCode.E9001.value == "E9001"

    def test_error_code_ranges(self):
        """Test that error codes are in expected ranges."""
        # Config errors (E1001-E1099)
        assert ErrorCode.E1001.value.startswith("E1")
        assert ErrorCode.E1002.value.startswith("E1")
        assert ErrorCode.E1003.value.startswith("E1")

        # Task errors (E2001-E2099)
        assert ErrorCode.E2001.value.startswith("E2")
        assert ErrorCode.E2002.value.startswith("E2")
        assert ErrorCode.E2003.value.startswith("E2")

        # Provider errors (E3001-E3099)
        assert ErrorCode.E3001.value.startswith("E3")

        # Notification errors (E4001-E4099)
        assert ErrorCode.E4001.value.startswith("E4")

        # Session errors (E5001-E5099)
        assert ErrorCode.E5001.value.startswith("E5")

        # State errors (E6001-E6099)
        assert ErrorCode.E6001.value.startswith("E6")

        # General errors (E9001-E9099)
        assert ErrorCode.E9001.value.startswith("E9")


class TestAgentLoopError:
    """Tests for the base AgentLoopError class."""

    def test_basic_error(self):
        """Test basic error creation."""
        error = AgentLoopError("Test error")
        assert error.message == "Test error"
        assert error.error_code == ErrorCode.E9001
        assert error.detail is None
        assert error.is_retryable is False

    def test_error_with_detail(self):
        """Test error with detail."""
        error = AgentLoopError("Test error", detail="Extra info")
        assert error.detail == "Extra info"

    def test_error_with_original_exception(self):
        """Test error with original exception."""
        original = ValueError("Original error")
        error = AgentLoopError("Wrapped error", original_exception=original)
        assert error.original_exception is original

    def test_error_is_retryable(self):
        """Test retryable flag."""
        error = AgentLoopError("Test error", is_retryable=True)
        assert error.is_retryable is True

    def test_to_dict(self):
        """Test conversion to dictionary."""
        error = AgentLoopError(
            "Test error",
            error_code=ErrorCode.E1001,
            detail="Extra info",
            is_retryable=True,
        )
        result = error.to_dict()
        assert result["error_code"] == "E1001"
        assert result["message"] == "Test error"
        assert result["detail"] == "Extra info"
        assert result["retryable"] is True

    def test_to_dict_without_optional_fields(self):
        """Test conversion to dict without optional fields."""
        error = AgentLoopError("Test error")
        result = error.to_dict()
        assert "error_code" in result
        assert "message" in result
        assert "detail" not in result
        assert "retryable" not in result

    def test_str_representation(self):
        """Test string representation."""
        error = AgentLoopError("Test error")
        assert "Test error" in str(error)
        assert "E9001" in str(error)

    def test_str_with_retryable(self):
        """Test string representation with retryable flag."""
        error = AgentLoopError("Test error", is_retryable=True)
        assert "retryable" in str(error)


class TestConfigErrors:
    """Tests for configuration-related errors."""

    def test_config_error(self):
        """Test ConfigError."""
        error = ConfigError("Config failed")
        assert error.error_code == ErrorCode.E1001
        assert error.is_retryable is False

    def test_config_validation_error(self):
        """Test ConfigValidationError."""
        error = ConfigValidationError("Invalid config", detail="Missing field")
        assert error.error_code == ErrorCode.E1002
        assert error.detail == "Missing field"
        assert error.is_retryable is False

    def test_config_reload_error(self):
        """Test ConfigReloadError."""
        error = ConfigReloadError("Reload failed")
        assert error.error_code == ErrorCode.E1003
        assert error.is_retryable is False


class TestTaskErrors:
    """Tests for task execution errors."""

    def test_task_execution_error(self):
        """Test TaskExecutionError."""
        error = TaskExecutionError("Task failed")
        assert error.error_code == ErrorCode.E2001
        assert error.is_retryable is True  # Default is retryable

    def test_task_timeout_error(self):
        """Test TaskTimeoutError."""
        error = TaskTimeoutError()
        assert error.message == "Task execution timed out"
        assert error.error_code == ErrorCode.E2002
        assert error.is_retryable is True

    def test_task_retry_exhausted_error(self):
        """Test TaskRetryExhaustedError."""
        error = TaskRetryExhaustedError()
        assert error.error_code == ErrorCode.E2003
        assert error.is_retryable is False


class TestProviderErrors:
    """Tests for provider-related errors."""

    def test_provider_error(self):
        """Test ProviderError."""
        error = ProviderError("Provider failed")
        assert error.error_code == ErrorCode.E3001

    def test_provider_auth_error(self):
        """Test ProviderAuthError."""
        error = ProviderAuthError()
        assert error.message == "Provider authentication failed"
        assert error.error_code == ErrorCode.E3002
        assert error.is_retryable is False

    def test_provider_rate_limit_error(self):
        """Test ProviderRateLimitError."""
        error = ProviderRateLimitError()
        assert error.message == "Provider rate limit exceeded"
        assert error.error_code == ErrorCode.E3003
        assert error.is_retryable is True

    def test_provider_connection_error(self):
        """Test ProviderConnectionError."""
        error = ProviderConnectionError()
        assert error.message == "Failed to connect to provider"
        assert error.error_code == ErrorCode.E3004
        assert error.is_retryable is True


class TestNotificationErrors:
    """Tests for notification-related errors."""

    def test_notification_error(self):
        """Test NotificationError."""
        error = NotificationError("Notification failed")
        assert error.error_code == ErrorCode.E4001

    def test_webhook_error(self):
        """Test WebhookError."""
        error = WebhookError()
        assert error.message == "Webhook notification failed"
        assert error.error_code == ErrorCode.E4002

    def test_email_error(self):
        """Test EmailError."""
        error = EmailError()
        assert error.message == "Email notification failed"
        assert error.error_code == ErrorCode.E4003

    def test_slack_error(self):
        """Test SlackError."""
        error = SlackError()
        assert error.message == "Slack notification failed"
        assert error.error_code == ErrorCode.E4004


class TestSessionErrors:
    """Tests for session-related errors."""

    def test_session_error(self):
        """Test SessionError."""
        error = SessionError("Session failed")
        assert error.error_code == ErrorCode.E5001

    def test_session_corrupt_error(self):
        """Test SessionCorruptError."""
        error = SessionCorruptError()
        assert error.message == "Session data is corrupted"
        assert error.error_code == ErrorCode.E5002
        assert error.is_retryable is False

    def test_session_not_found_error(self):
        """Test SessionNotFoundError."""
        error = SessionNotFoundError()
        assert error.message == "Session not found"
        assert error.error_code == ErrorCode.E5003
        assert error.is_retryable is False


class TestStateErrors:
    """Tests for state-related errors."""

    def test_state_error(self):
        """Test StateError."""
        error = StateError("State failed")
        assert error.error_code == ErrorCode.E6001

    def test_state_corrupt_error(self):
        """Test StateCorruptError."""
        error = StateCorruptError()
        assert error.message == "State file is corrupted"
        assert error.error_code == ErrorCode.E6001
        assert error.is_retryable is False

    def test_state_not_found_error(self):
        """Test StateNotFoundError."""
        error = StateNotFoundError()
        assert error.message == "State file not found"
        assert error.error_code == ErrorCode.E6002
        assert error.is_retryable is False

    def test_state_read_error(self):
        """Test StateReadError."""
        error = StateReadError()
        assert error.message == "Failed to read state file"
        assert error.error_code == ErrorCode.E6004
        assert error.is_retryable is True

    def test_state_write_error(self):
        """Test StateWriteError."""
        error = StateWriteError()
        assert error.message == "Failed to write state file"
        assert error.error_code == ErrorCode.E6003
        assert error.is_retryable is True


class TestExceptionChaining:
    """Tests for exception chaining."""

    def test_exception_chaining_with_from(self):
        """Test exception chaining using 'from' keyword."""
        original = ValueError("Original error")
        try:
            raise AgentLoopError("New error", original_exception=original) from original
        except AgentLoopError as e:
            assert e.original_exception is original
            # The __cause__ should be set by 'from'
            assert e.__cause__ is original

    def test_exception_hierarchy(self):
        """Test that all exceptions inherit from AgentLoopError."""
        errors = [
            ConfigError("test"),
            TaskExecutionError("test"),
            ProviderError("test"),
            NotificationError("test"),
            SessionError("test"),
            StateError("test"),
        ]
        for error in errors:
            assert isinstance(error, AgentLoopError)


class TestExceptionDifferentiation:
    """Tests to verify exception differentiation between transient and permanent errors."""

    def test_config_errors_are_not_retryable(self):
        """Config errors should not be retryable."""
        error = ConfigValidationError("Invalid config")
        assert error.is_retryable is False

    def test_task_errors_default_to_retryable(self):
        """Task errors should be retryable by default."""
        error = TaskExecutionError("Task failed")
        assert error.is_retryable is True

    def test_task_timeout_is_retryable(self):
        """Task timeout should be retryable."""
        error = TaskTimeoutError()
        assert error.is_retryable is True

    def test_task_retry_exhausted_not_retryable(self):
        """Task retry exhausted should not be retryable."""
        error = TaskRetryExhaustedError()
        assert error.is_retryable is False

    def test_provider_auth_not_retryable(self):
        """Provider auth errors should not be retryable."""
        error = ProviderAuthError()
        assert error.is_retryable is False

    def test_provider_rate_limit_retryable(self):
        """Provider rate limit errors should be retryable."""
        error = ProviderRateLimitError()
        assert error.is_retryable is True

    def test_provider_connection_retryable(self):
        """Provider connection errors should be retryable."""
        error = ProviderConnectionError()
        assert error.is_retryable is True
