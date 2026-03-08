"""Structured Logging Module - Production-grade logging with rotation, correlation tracking, and audit logging

This module provides structured JSON logging for the Agent-Loop system,
making it easier for log analysis tools to process logs.
Features:
- Log rotation with RotatingFileHandler (10MB per file, 5 backups)
- Correlation ID tracking for sessions, tasks, and API requests
- Sensitive data redaction (API keys, passwords, tokens)
- Dynamic log level adjustment via API
- Structured context (module, function, line_number)
- Audit logging for state changes
"""

import logging
import logging.handlers
import os
import re
import sys
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Generator

import structlog
from structlog.types import EventDict, Processor

from . import console as rich_console


# Global log level that can be adjusted at runtime
_current_log_level: str = "INFO"
_log_level_locked = False


# ============== Log Rotation ==============

def _get_rotating_file_handler(
    log_file: str,
    log_level: int,
) -> logging.handlers.RotatingFileHandler:
    """Create a rotating file handler with 10MB per file, 5 backups.

    Args:
        log_file: Path to the log file
        log_level: Logging level number

    Returns:
        Configured RotatingFileHandler
    """
    # Ensure log directory exists
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding="utf-8",
    )
    handler.setLevel(log_level)
    handler.setFormatter(
        logging.Formatter(fmt="%(message)s")
    )
    return handler


# ============== Correlation ID Tracking ==============

class CorrelationIdProcessor(Processor):
    """Structlog processor that adds correlation_id to all log entries.

    Correlation IDs are generated for:
    - Agent sessions (session_id)
    - Task executions (execution_id)
    - API requests (request_id)
    """

    def __init__(self) -> None:
        self._correlation_id: str | None = None
        self._correlation_type: str | None = None

    def __call__(
        self,
        logger: logging.Logger,
        method_name: str,
        event_dict: EventDict,
    ) -> EventDict:
        """Add correlation_id to the event dict.

        Args:
            logger: The logger instance
            method_name: The log method name (info, debug, etc.)
            event_dict: The event dictionary to modify

        Returns:
            Modified event dict with correlation_id
        """
        # Use existing correlation_id from context or use the one set on this processor
        if self._correlation_id:
            event_dict["correlation_id"] = self._correlation_id

        if self._correlation_type:
            event_dict["correlation_type"] = self._correlation_type

        return event_dict

    def set_correlation(
        self,
        correlation_id: str,
        correlation_type: str = "session",
    ) -> None:
        """Set the correlation ID and type for this processor.

        Args:
            correlation_id: The correlation UUID
            correlation_type: Type: 'session', 'execution', 'request'
        """
        self._correlation_id = correlation_id
        self._correlation_type = correlation_type

    def clear_correlation(self) -> None:
        """Clear the correlation ID."""
        self._correlation_id = None
        self._correlation_type = None


# Global correlation processor instance
_correlation_processor = CorrelationIdProcessor()


def generate_correlation_id() -> str:
    """Generate a new UUID for correlation tracking.

    Returns:
        A new UUID string
    """
    return str(uuid.uuid4())


@contextmanager
def correlation_context(
    correlation_id: str | None = None,
    correlation_type: str = "session",
) -> Generator[None, None, None]:
    """Context manager for setting correlation ID in logging context.

    Args:
        correlation_id: Optional correlation ID (generates new one if not provided)
        correlation_type: Type of correlation (session, execution, request)

    Yields:
        None

    Example:
        with correlation_context(task_id, "execution"):
            logger.info("task started", task_id=task_id)
    """
    import structlog.contextvars

    corr_id = correlation_id or generate_correlation_id()
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(
        correlation_id=corr_id,
        correlation_type=correlation_type,
    )
    try:
        yield
    finally:
        structlog.contextvars.clear_contextvars()


# ============== Sensitive Data Redaction ==============

# Patterns for sensitive data
SENSITIVE_PATTERNS = [
    (re.compile(r'sk-[a-zA-Z0-9]{20,}', re.IGNORECASE), '[REDACTED_API_KEY]'),
    (re.compile(r'password["\s:=]+[^\s"]+', re.IGNORECASE), 'password=[REDACTED]'),
    (re.compile(r'token["\s:=]+[^\s"]+', re.IGNORECASE), 'token=[REDACTED]'),
    (re.compile(r'secret["\s:=]+[^\s"]+', re.IGNORECASE), 'secret=[REDACTED]'),
    (re.compile(r'Authorization["\s:=]+[^\s"]+', re.IGNORECASE), 'Authorization=[REDACTED]'),
    (re.compile(r'Bearer\s+[a-zA-Z0-9\-_.~+/]+=*', re.IGNORECASE), 'Bearer [REDACTED]'),
    (re.compile(r'aws_access_key_id[=\s]+[A-Z0-9]{20}', re.IGNORECASE), 'aws_access_key_id=[REDACTED]'),
    (re.compile(r'aws_secret_access_key[=\s]+[A-Za-z0-9/+=]{40}', re.IGNORECASE), 'aws_secret_access_key=[REDACTED]'),
]


class SensitiveDataRedactor(Processor):
    """Structlog processor that redacts sensitive data from log messages.

    Automatically detects and redacts:
    - API keys (sk-*)
    - Passwords
    - Tokens
    - Secrets
    - Authorization headers
    - AWS credentials
    """

    def __init__(self) -> None:
        self._redact_values: bool = True
        self._redact_keys: bool = True

        # Keys that should be redacted
        self._sensitive_keys = {
            'password', 'secret', 'token', 'api_key', 'apikey',
            'authorization', 'auth', 'credential', 'private_key',
            'access_key', 'session_token', 'refresh_token',
        }

    def __call__(
        self,
        logger: logging.Logger,
        method_name: str,
        event_dict: EventDict,
    ) -> EventDict:
        """Redact sensitive data from the event dict.

        Args:
            logger: The logger instance
            method_name: The log method name
            event_dict: The event dictionary to modify

        Returns:
            Modified event dict with redacted sensitive data
        """
        # Redact sensitive keys
        if self._redact_keys:
            keys_to_remove = []
            for key in event_dict:
                key_lower = key.lower()
                if key_lower in self._sensitive_keys or any(
                    sk in key_lower for sk in self._sensitive_keys
                ):
                    keys_to_remove.append(key)
                    event_dict[key] = '[REDACTED]'

        # Redact sensitive patterns in string values
        if self._redact_values:
            for key, value in event_dict.items():
                if isinstance(value, str):
                    redacted = value
                    for pattern, replacement in SENSITIVE_PATTERNS:
                        redacted = pattern.sub(replacement, redacted)
                    event_dict[key] = redacted

        return event_dict


# Global sensitive data redactor
_sensitive_redactor = SensitiveDataRedactor()


# ============== Structured Context ==============

class StructuredContextProcessor(Processor):
    """Structlog processor that adds structured context to all log entries.

    Automatically adds:
    - module: The module name
    - function: The function name
    - line_number: The line number
    """

    def __init__(self) -> None:
        self._add_caller_info = True

    def __call__(
        self,
        logger: logging.Logger,
        method_name: str,
        event_dict: EventDict,
    ) -> EventDict:
        """Add caller information to the event dict.

        Args:
            logger: The logger instance
            method_name: The log method name
            event_dict: The event dictionary to modify

        Returns:
            Modified event dict with caller info
        """
        if self._add_caller_info:
            # Get caller frame info
            frame = sys._getframe(2) if hasattr(sys, '_getframe') else None
            if frame:
                event_dict['module'] = frame.f_globals.get('__name__', 'unknown')
                event_dict['function'] = frame.f_code.co_name
                event_dict['line_number'] = frame.f_lineno

        return event_dict


# Global structured context processor
_structured_context = StructuredContextProcessor()


# ============== Audit Logger ==============

_audit_logger: logging.Logger | None = None


def get_audit_logger(name: str = "agent_audit") -> logging.Logger:
    """Get or create the audit logger.

    The audit logger writes to a separate audit.log file and records
    all state change operations:
    - Task create/update/delete
    - Configuration changes
    - Agent start/stop

    Args:
        name: Logger name

    Returns:
        Configured audit logger
    """
    global _audit_logger

    if _audit_logger is not None:
        return _audit_logger

    # Create audit logger
    _audit_logger = logging.getLogger(name)
    _audit_logger.setLevel(logging.INFO)

    # Avoid duplicate handlers
    if not _audit_logger.handlers:
        # Use rotating handler for audit log
        audit_file = os.environ.get("AUDIT_LOG_FILE", "logs/audit.log")
        audit_handler = _get_rotating_file_handler(audit_file, logging.INFO)
        audit_handler.setFormatter(
            logging.Formatter(
                fmt="%(asctime)s | %(levelname)s | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S"
            )
        )
        _audit_logger.addHandler(audit_handler)

        # Ensure audit logger doesn't propagate to root
        _audit_logger.propagate = False

    return _audit_logger


def log_audit(
    action: str,
    entity_type: str,
    entity_id: str,
    details: Dict[str, Any] | None = None,
    user: str = "system",
    correlation_id: str = "N/A",
) -> None:
    """Log an audit event for state changes.

    Args:
        action: Action performed (create, update, delete, start, stop)
        entity_type: Type of entity (task, config, session, agent)
        entity_id: ID of the entity
        details: Additional details about the action
        user: User who performed the action (default: system)
        correlation_id: Optional correlation ID for tracking
    """
    audit_logger = get_audit_logger()

    details_str = ""
    if details:
        # Redact sensitive data from details
        details_copy = dict(details)
        for key in list(details_copy.keys()):
            key_lower = key.lower()
            if any(sk in key_lower for sk in {'password', 'secret', 'token', 'api_key'}):
                details_copy[key] = '[REDACTED]'
        details_str = f" | Details: {details_copy}"

    audit_logger.info(
        f"action={action} | entity={entity_type}:{entity_id} | user={user} | correlation_id={correlation_id}{details_str}"
    )


# ============== Log Level Management ==============

def set_log_level(level: str) -> bool:
    """Set the global log level at runtime.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)

    Returns:
        True if successful, False if invalid level
    """
    global _current_log_level, _log_level_locked

    if _log_level_locked:
        return False

    level_upper = level.upper()
    if not hasattr(logging, level_upper):
        return False

    _current_log_level = level_upper
    log_level_num = getattr(logging, level_upper)

    # Update root logger level
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level_num)

    # Update all handler levels
    for handler in root_logger.handlers:
        handler.setLevel(log_level_num)

    return True


def get_log_level() -> str:
    """Get the current global log level.

    Returns:
        Current log level as string
    """
    return _current_log_level


def lock_log_level(locked: bool = True) -> None:
    """Lock/unlock the log level from being changed at runtime.

    Args:
        locked: Whether to lock the log level
    """
    global _log_level_locked
    _log_level_locked = locked


# ============== Main Configuration ==============


def configure_logging(
    log_level: str = "INFO",
    log_file: str = "",
    json_output: bool = True,
    enable_audit: bool = True,
) -> structlog.BoundLogger:
    """Configure structured logging for the application.

    Features:
    - Log rotation: Uses RotatingFileHandler with 10MB max file size, 5 backups
    - Correlation tracking: Adds correlation_id to all log entries
    - Sensitive data redaction: Redacts API keys, passwords, tokens
    - Structured context: Adds module, function, line_number to logs

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional file path for JSON log output
        json_output: Whether to output JSON format (True for file, False for console)
        enable_audit: Whether to enable audit logging

    Returns:
        Configured structlog logger
    """
    global _current_log_level

    # Get log level from environment variable if not provided
    log_level = os.environ.get("LOG_LEVEL", log_level).upper()
    log_level_num = getattr(logging, log_level, logging.INFO)
    _current_log_level = log_level

    # Get log file path from environment variable
    log_file = log_file or os.environ.get("LOG_FILE", "")

    # Determine if we should use JSON output
    # Default: use JSON if log file is specified, otherwise human-readable console
    # Can be overridden with LOG_JSON environment variable
    if os.environ.get("LOG_JSON", ""):
        use_json = os.environ.get("LOG_JSON", "false").lower() == "true"
    else:
        use_json = bool(log_file)

    # Configure processors in order
    processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        _correlation_processor,  # Add correlation ID
        _sensitive_redactor,    # Redact sensitive data
        _structured_context,    # Add module, function, line_number
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    # Add JSON rendering if enabled
    if use_json:
        processors.append(structlog.processors.JSONRenderer())
    else:
        # Human-readable format for console
        # Don't include correlation_id in console output for readability
        processors.append(
            structlog.dev.ConsoleRenderer(
                colors=True,
            )
        )

    # Configure structlog
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Configure standard library logging
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level_num)

    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Create appropriate handler based on output
    if use_json and log_file:
        # Use rotating file handler for log rotation
        handler = _get_rotating_file_handler(log_file, log_level_num)
    else:
        # Console handler with rich for better readability
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(
            logging.Formatter(
                fmt="%(message)s",
            )
        )

    handler.setLevel(log_level_num)
    root_logger.addHandler(handler)

    # Initialize audit logger if enabled
    if enable_audit:
        get_audit_logger()

    # Set specific loggers to appropriate levels
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("fastapi").setLevel(logging.WARNING)

    # Return a bound logger
    return structlog.get_logger()


def get_logger(name: str = "") -> structlog.BoundLogger:
    """Get a structured logger instance.

    Args:
        name: Logger name (typically __name__)

    Returns:
        A structlog bound logger
    """
    return structlog.get_logger(name)


def log_iteration(
    logger: structlog.BoundLogger,
    iteration: int,
    total: int,
    task_name: str | None = None,
    status: str = "started",
) -> None:
    """Log an agent iteration with structured data.

    Args:
        logger: The logger instance
        iteration: Current iteration number
        total: Total iterations
        task_name: Optional task name
        status: Iteration status (started, completed, failed)
    """
    logger.info(
        "agent_iteration",
        iteration=iteration,
        total_iterations=total,
        task_name=task_name,
        status=status,
    )


def log_task_event(
    logger: structlog.BoundLogger,
    event: str,
    task_id: str,
    details: Dict[str, Any] | None = None,
) -> None:
    """Log a task-related event with structured data.

    Args:
        logger: The logger instance
        event: Event type (started, completed, failed, etc.)
        task_id: Task identifier
        details: Additional event details
    """
    logger.info(
        "task_event",
        event=event,
        task_id=task_id,
        **(details or {}),
    )


def log_error_with_context(
    logger: structlog.BoundLogger,
    error: Exception,
    context: Dict[str, Any] | None = None,
) -> None:
    """Log an error with additional context.

    Args:
        logger: The logger instance
        error: The exception to log
        context: Additional context information
    """
    logger.error(
        "error_occurred",
        error_type=type(error).__name__,
        error_message=str(error),
        **(context or {}),
    )


# Default logger instance - will be configured at module import time
_logger: structlog.BoundLogger | None = None


def init_logger() -> structlog.BoundLogger:
    """Initialize the default logger with configuration from environment.

    Returns:
        Configured structlog logger
    """
    global _logger
    if _logger is None:
        _logger = configure_logging()
    return _logger


# Initialize logger on module import
init_logger()
