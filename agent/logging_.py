"""Structured Logging Module - Using structlog for JSON logging

This module provides structured JSON logging for the Agent-Loop system,
making it easier for log analysis tools to process logs.
"""

import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict

import structlog

from . import console as rich_console


def configure_logging(
    log_level: str = "INFO",
    log_file: str = "",
    json_output: bool = True,
) -> structlog.BoundLogger:
    """Configure structured logging for the application.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional file path for JSON log output
        json_output: Whether to output JSON format (True for file, False for console)

    Returns:
        Configured structlog logger
    """
    # Get log level from environment variable if not provided
    log_level = os.environ.get("LOG_LEVEL", log_level).upper()
    log_level_num = getattr(logging, log_level, logging.INFO)

    # Get log file path from environment variable
    log_file = log_file or os.environ.get("LOG_FILE", "")

    # Determine if we should use JSON output
    # Default: use JSON if log file is specified, otherwise human-readable console
    # Can be overridden with LOG_JSON environment variable
    if os.environ.get("LOG_JSON", ""):
        use_json = os.environ.get("LOG_JSON", "false").lower() == "true"
    else:
        use_json = bool(log_file)

    # Configure processors based on environment
    processors = [
        structlog.contextvars.merge_contextvars,
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
        # Ensure log directory exists
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        # Use JSON formatter for file output
        handler = logging.FileHandler(log_file, encoding="utf-8")
        handler.setFormatter(
            logging.Formatter(
                fmt="%(message)s",  # structlog handles formatting
            )
        )
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
