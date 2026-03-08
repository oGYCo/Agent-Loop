"""Exception hierarchy and error code system for Agent-Loop.

This module provides a structured exception hierarchy that replaces scattered
Exception catches throughout the codebase. Each exception type has an associated
error code for easy logging, monitoring, and alerting.

Error Code Ranges:
- E1001-E1099: Configuration errors
- E2001-E2099: Task execution errors
- E3001-E3099: Provider/Model errors
- E4001-E4099: Notification errors
- E5001-E5099: Session errors
- E6001-E6099: State/Storage errors
- E9001-E9099: Other/General errors
"""

from enum import Enum
from typing import Any, Dict, Optional


class ErrorCode(Enum):
    """Error code enumeration for Agent-Loop.

    Each error code has a unique number for easy log analysis and monitoring.
    The prefix indicates the error category:
    - E1xxx: Configuration
    - E2xxx: Task execution
    - E3xxx: Provider/Model
    - E4xxx: Notification
    - E5xxx: Session
    - E6xxx: State/Storage
    - E9xxx: General/Other
    """

    # Configuration errors (E1001-E1099)
    E1001 = "E1001"  # Config file not found
    E1002 = "E1002"  # Config validation failed
    E1003 = "E1003"  # Config reload failed

    # Task execution errors (E2001-E2099)
    E2001 = "E2001"  # Task execution failed
    E2002 = "E2002"  # Task timeout
    E2003 = "E2003"  # Task retry exhausted

    # Provider/Model errors (E3001-E3099)
    E3001 = "E3001"  # Provider error (general)
    E3002 = "E3002"  # Provider authentication failed
    E3003 = "E3003"  # Provider rate limit exceeded
    E3004 = "E3004"  # Provider connection error

    # Notification errors (E4001-E4099)
    E4001 = "E4001"  # Notification error (general)
    E4002 = "E4002"  # Webhook error
    E4003 = "E4003"  # Email error
    E4004 = "E4004"  # Slack error

    # Session errors (E5001-E5099)
    E5001 = "E5001"  # Session error (general)
    E5002 = "E5002"  # Session corrupted
    E5003 = "E5003"  # Session not found

    # State/Storage errors (E6001-E6099)
    E6001 = "E6001"  # State file corrupted
    E6002 = "E6002"  # State file not found
    E6003 = "E6003"  # State write failed
    E6004 = "E6004"  # State read failed

    # Other/General errors (E9001-E9099)
    E9001 = "E9001"  # Unknown error
    E9002 = "E9002"  # Invalid operation
    E9003 = "E9003"  # Resource not found


class AgentLoopError(Exception):
    """Base exception class for all Agent-Loop errors.

    This is the root of the exception hierarchy. All custom exceptions
    should inherit from this class.

    Attributes:
        error_code: The error code enum value
        message: Human-readable error message
        detail: Additional details about the error
        is_retryable: Whether the operation that caused this error can be retried
    """

    def __init__(
        self,
        message: str,
        error_code: ErrorCode = ErrorCode.E9001,
        detail: Optional[str] = None,
        is_retryable: bool = False,
        original_exception: Optional[Exception] = None,
    ):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.detail = detail
        self.is_retryable = is_retryable
        self.original_exception = original_exception

    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for JSON serialization."""
        result: Dict[str, Any] = {
            "error_code": self.error_code.value,
            "message": self.message,
        }
        if self.detail:
            result["detail"] = self.detail
        if self.is_retryable:
            result["retryable"] = self.is_retryable
        return result

    def __str__(self) -> str:
        parts = [f"[{self.error_code.value}] {self.message}"]
        if self.detail:
            parts.append(self.detail)
        if self.is_retryable:
            parts.append("(retryable)")
        return " ".join(parts)


# ========== Configuration Errors ==========

class ConfigError(AgentLoopError):
    """Base class for configuration-related errors.

    Configuration errors are generally not retryable and require
    human intervention to fix.
    """

    def __init__(
        self,
        message: str,
        error_code: ErrorCode = ErrorCode.E1001,
        detail: Optional[str] = None,
        original_exception: Optional[Exception] = None,
    ):
        super().__init__(
            message=message,
            error_code=error_code,
            detail=detail,
            is_retryable=False,
            original_exception=original_exception,
        )


class ConfigValidationError(ConfigError):
    """Raised when configuration validation fails.

    This includes invalid values, missing required fields, or
    schema violations in configuration files.
    """

    def __init__(
        self,
        message: str,
        detail: Optional[str] = None,
        original_exception: Optional[Exception] = None,
    ):
        super().__init__(
            message=message,
            error_code=ErrorCode.E1002,
            detail=detail,
            original_exception=original_exception,
        )


class ConfigReloadError(ConfigError):
    """Raised when configuration hot reload fails.

    This typically occurs when the configuration file is modified
    incorrectly or becomes unreadable.
    """

    def __init__(
        self,
        message: str,
        detail: Optional[str] = None,
        original_exception: Optional[Exception] = None,
    ):
        super().__init__(
            message=message,
            error_code=ErrorCode.E1003,
            detail=detail,
            original_exception=original_exception,
        )


# ========== Task Execution Errors ==========

class TaskExecutionError(AgentLoopError):
    """Base class for task execution errors.

    Task execution errors may be retryable depending on the specific
    failure mode.
    """

    def __init__(
        self,
        message: str,
        error_code: ErrorCode = ErrorCode.E2001,
        detail: Optional[str] = None,
        is_retryable: bool = True,
        original_exception: Optional[Exception] = None,
    ):
        super().__init__(
            message=message,
            error_code=error_code,
            detail=detail,
            is_retryable=is_retryable,
            original_exception=original_exception,
        )


class TaskTimeoutError(TaskExecutionError):
    """Raised when a task execution times out.

    Task timeouts are generally retryable as they may be caused
    by temporary resource constraints.
    """

    def __init__(
        self,
        message: str = "Task execution timed out",
        detail: Optional[str] = None,
        original_exception: Optional[Exception] = None,
    ):
        super().__init__(
            message=message,
            error_code=ErrorCode.E2002,
            detail=detail,
            is_retryable=True,
            original_exception=original_exception,
        )


class TaskRetryExhaustedError(TaskExecutionError):
    """Raised when all retry attempts for a task have been exhausted.

    This is a permanent error that requires human intervention to resolve.
    """

    def __init__(
        self,
        message: str = "Task failed after all retry attempts",
        detail: Optional[str] = None,
        original_exception: Optional[Exception] = None,
    ):
        super().__init__(
            message=message,
            error_code=ErrorCode.E2003,
            detail=detail,
            is_retryable=False,
            original_exception=original_exception,
        )


# ========== Provider/Model Errors ==========

class ProviderError(AgentLoopError):
    """Base class for model provider errors.

    Provider errors may be transient (network issues) or permanent
    (authentication problems).
    """

    def __init__(
        self,
        message: str,
        error_code: ErrorCode = ErrorCode.E3001,
        detail: Optional[str] = None,
        is_retryable: bool = True,
        original_exception: Optional[Exception] = None,
    ):
        super().__init__(
            message=message,
            error_code=error_code,
            detail=detail,
            is_retryable=is_retryable,
            original_exception=original_exception,
        )


class ProviderAuthError(ProviderError):
    """Raised when provider authentication fails.

    Authentication errors are permanent and require human intervention
    to fix (e.g., updating API keys).
    """

    def __init__(
        self,
        message: str = "Provider authentication failed",
        detail: Optional[str] = None,
        original_exception: Optional[Exception] = None,
    ):
        super().__init__(
            message=message,
            error_code=ErrorCode.E3002,
            detail=detail,
            is_retryable=False,
            original_exception=original_exception,
        )


class ProviderRateLimitError(ProviderError):
    """Raised when provider rate limit is exceeded.

    Rate limit errors are transient and will resolve after the
    rate limit window expires.
    """

    def __init__(
        self,
        message: str = "Provider rate limit exceeded",
        detail: Optional[str] = None,
        original_exception: Optional[Exception] = None,
    ):
        super().__init__(
            message=message,
            error_code=ErrorCode.E3003,
            detail=detail,
            is_retryable=True,
            original_exception=original_exception,
        )


class ProviderConnectionError(ProviderError):
    """Raised when connection to provider fails.

    Connection errors are transient and generally retryable.
    """

    def __init__(
        self,
        message: str = "Failed to connect to provider",
        detail: Optional[str] = None,
        original_exception: Optional[Exception] = None,
    ):
        super().__init__(
            message=message,
            error_code=ErrorCode.E3004,
            detail=detail,
            is_retryable=True,
            original_exception=original_exception,
        )


# ========== Notification Errors ==========

class NotificationError(AgentLoopError):
    """Base class for notification-related errors.

    Notification errors are generally not critical and may be retryable.
    """

    def __init__(
        self,
        message: str,
        error_code: ErrorCode = ErrorCode.E4001,
        detail: Optional[str] = None,
        is_retryable: bool = True,
        original_exception: Optional[Exception] = None,
    ):
        super().__init__(
            message=message,
            error_code=error_code,
            detail=detail,
            is_retryable=is_retryable,
            original_exception=original_exception,
        )


class WebhookError(NotificationError):
    """Raised when webhook notification fails.

    Webhook errors may be caused by invalid URLs, network issues,
    or server-side problems.
    """

    def __init__(
        self,
        message: str = "Webhook notification failed",
        detail: Optional[str] = None,
        is_retryable: bool = True,
        original_exception: Optional[Exception] = None,
    ):
        super().__init__(
            message=message,
            error_code=ErrorCode.E4002,
            detail=detail,
            is_retryable=is_retryable,
            original_exception=original_exception,
        )


class EmailError(NotificationError):
    """Raised when email notification fails.

    Email errors may be caused by SMTP configuration issues,
    invalid recipients, or server problems.
    """

    def __init__(
        self,
        message: str = "Email notification failed",
        detail: Optional[str] = None,
        is_retryable: bool = True,
        original_exception: Optional[Exception] = None,
    ):
        super().__init__(
            message=message,
            error_code=ErrorCode.E4003,
            detail=detail,
            is_retryable=is_retryable,
            original_exception=original_exception,
        )


class SlackError(NotificationError):
    """Raised when Slack notification fails.

    Slack errors may be caused by invalid webhook URLs, channel
    permissions, or network issues.
    """

    def __init__(
        self,
        message: str = "Slack notification failed",
        detail: Optional[str] = None,
        is_retryable: bool = True,
        original_exception: Optional[Exception] = None,
    ):
        super().__init__(
            message=message,
            error_code=ErrorCode.E4004,
            detail=detail,
            is_retryable=is_retryable,
            original_exception=original_exception,
        )


# ========== Session Errors ==========

class SessionError(AgentLoopError):
    """Base class for session-related errors.

    Session errors may require human intervention depending on
    the specific failure mode.
    """

    def __init__(
        self,
        message: str,
        error_code: ErrorCode = ErrorCode.E5001,
        detail: Optional[str] = None,
        is_retryable: bool = True,
        original_exception: Optional[Exception] = None,
    ):
        super().__init__(
            message=message,
            error_code=error_code,
            detail=detail,
            is_retryable=is_retryable,
            original_exception=original_exception,
        )


class SessionCorruptError(SessionError):
    """Raised when session data is corrupted.

    Corrupted session data may require creating a new session
    or restoring from a checkpoint.
    """

    def __init__(
        self,
        message: str = "Session data is corrupted",
        detail: Optional[str] = None,
        original_exception: Optional[Exception] = None,
    ):
        super().__init__(
            message=message,
            error_code=ErrorCode.E5002,
            detail=detail,
            is_retryable=False,
            original_exception=original_exception,
        )


class SessionNotFoundError(SessionError):
    """Raised when a session cannot be found.

    This may occur when trying to load a session that doesn't
    exist or has been deleted.
    """

    def __init__(
        self,
        message: str = "Session not found",
        detail: Optional[str] = None,
        original_exception: Optional[Exception] = None,
    ):
        super().__init__(
            message=message,
            error_code=ErrorCode.E5003,
            detail=detail,
            is_retryable=False,
            original_exception=original_exception,
        )


# ========== State/Storage Errors ==========

class StateError(AgentLoopError):
    """Base class for state/storage-related errors.

    State errors may indicate disk problems or file corruption.
    """

    def __init__(
        self,
        message: str,
        error_code: ErrorCode = ErrorCode.E6001,
        detail: Optional[str] = None,
        is_retryable: bool = True,
        original_exception: Optional[Exception] = None,
    ):
        super().__init__(
            message=message,
            error_code=error_code,
            detail=detail,
            is_retryable=is_retryable,
            original_exception=original_exception,
        )


class StateCorruptError(StateError):
    """Raised when state file is corrupted.

    Corrupted state files may require manual intervention
    or restoration from backup.
    """

    def __init__(
        self,
        message: str = "State file is corrupted",
        detail: Optional[str] = None,
        original_exception: Optional[Exception] = None,
    ):
        super().__init__(
            message=message,
            error_code=ErrorCode.E6001,
            detail=detail,
            is_retryable=False,
            original_exception=original_exception,
        )


class StateNotFoundError(StateError):
    """Raised when state file cannot be found.

    This may occur when the state file doesn't exist yet
    (first run) or has been deleted.
    """

    def __init__(
        self,
        message: str = "State file not found",
        detail: Optional[str] = None,
        original_exception: Optional[Exception] = None,
    ):
        super().__init__(
            message=message,
            error_code=ErrorCode.E6002,
            detail=detail,
            is_retryable=False,
            original_exception=original_exception,
        )


class StateReadError(StateError):
    """Raised when state file cannot be read.

    This may occur due to file permissions, disk errors,
    or file locking issues.
    """

    def __init__(
        self,
        message: str = "Failed to read state file",
        detail: Optional[str] = None,
        original_exception: Optional[Exception] = None,
    ):
        super().__init__(
            message=message,
            error_code=ErrorCode.E6004,
            detail=detail,
            is_retryable=True,
            original_exception=original_exception,
        )


class StateWriteError(StateError):
    """Raised when state file cannot be written.

    This may occur due to disk full, permissions, or
    file locking issues.
    """

    def __init__(
        self,
        message: str = "Failed to write state file",
        detail: Optional[str] = None,
        original_exception: Optional[Exception] = None,
    ):
        super().__init__(
            message=message,
            error_code=ErrorCode.E6003,
            detail=detail,
            is_retryable=True,
            original_exception=original_exception,
        )
