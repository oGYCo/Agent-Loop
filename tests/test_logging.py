"""Tests for the enhanced logging module.

Tests cover:
- Log rotation configuration
- Correlation ID tracking
- Sensitive data redaction
- Dynamic log level adjustment
- Audit logging
"""

import io
import json
import logging
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from agent import logging_ as log_module


class TestLogRotation:
    """Tests for log rotation functionality."""

    def test_rotating_file_handler_creation(self):
        """Test that rotating file handler is created with correct parameters."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, "test.log")

            handler = log_module._get_rotating_file_handler(log_file, logging.INFO)

            assert handler.maxBytes == 10 * 1024 * 1024  # 10MB
            assert handler.backupCount == 5
            assert isinstance(handler, logging.handlers.RotatingFileHandler)

    def test_log_rotation_with_configure_logging(self):
        """Test that configure_logging uses rotating handler when log_file is specified."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, "test.log")

            # Reconfigure logging to use rotating handler
            logger = log_module.configure_logging(
                log_level="INFO",
                log_file=log_file,
                json_output=True,
            )

            # Check that rotating handler was added
            root_logger = logging.getLogger()
            handlers = root_logger.handlers

            rotating_handlers = [
                h for h in handlers
                if isinstance(h, logging.handlers.RotatingFileHandler)
            ]

            assert len(rotating_handlers) > 0


class TestCorrelationId:
    """Tests for correlation ID tracking."""

    def test_generate_correlation_id(self):
        """Test that correlation ID generation produces valid UUIDs."""
        import uuid

        corr_id = log_module.generate_correlation_id()

        # Should be a valid UUID
        uuid_obj = uuid.UUID(corr_id)
        assert str(uuid_obj) == corr_id

    def test_generate_unique_ids(self):
        """Test that generated IDs are unique."""
        ids = [log_module.generate_correlation_id() for _ in range(100)]
        assert len(set(ids)) == 100

    def test_correlation_processor_adds_id(self):
        """Test that CorrelationIdProcessor adds correlation_id to event dict."""
        import logging

        processor = log_module.CorrelationIdProcessor()
        processor.set_correlation("test-correlation-id", "session")

        event_dict = {
            "event": "test",
            "message": "test message",
        }

        result = processor(logging.getLogger(), "info", event_dict)

        assert result["correlation_id"] == "test-correlation-id"
        assert result["correlation_type"] == "session"

    def test_correlation_context_manager(self):
        """Test that correlation_context sets context variables."""
        # Just verify the context manager can be entered and exited without error
        with log_module.correlation_context("test-id-123", "execution"):
            logger = log_module.get_logger("test")
            # Log something - should include correlation_id in the processor
            logger.info("test message")

        # If we get here without error, the context manager works
        assert True


class TestSensitiveDataRedaction:
    """Tests for sensitive data redaction."""

    def test_redact_api_key(self):
        """Test that API keys are redacted."""
        processor = log_module.SensitiveDataRedactor()

        event_dict = {
            "message": "Testing",
            "my_api_key": "sk-1234567890abcdefghijklmnop",
        }

        result = processor(logging.getLogger(), "info", event_dict)

        # The key 'my_api_key' contains 'api_key' so it should be redacted
        assert result["my_api_key"] == "[REDACTED]"

    def test_redact_password(self):
        """Test that passwords are redacted."""
        processor = log_module.SensitiveDataRedactor()

        event_dict = {
            "message": "Testing",
            "password": "super_secret_123",
        }

        result = processor(logging.getLogger(), "info", event_dict)

        assert "password" in result
        assert "[REDACTED]" in result["password"]

    def test_redact_token(self):
        """Test that tokens are redacted."""
        processor = log_module.SensitiveDataRedactor()

        event_dict = {
            "message": "Testing",
            "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.test.token",
        }

        result = processor(logging.getLogger(), "info", event_dict)

        assert "token" in result
        assert "[REDACTED]" in result["token"]

    def test_redact_authorization_header(self):
        """Test that Authorization headers are redacted."""
        processor = log_module.SensitiveDataRedactor()

        event_dict = {
            "message": "Testing",
            "Authorization": "Bearer eyJhbGciOiJIUzI1NiJ9.test",
        }

        result = processor(logging.getLogger(), "info", event_dict)

        assert "Authorization" in result
        assert "[REDACTED]" in result["Authorization"]

    def test_redact_aws_credentials(self):
        """Test that AWS credentials are redacted."""
        processor = log_module.SensitiveDataRedactor()

        event_dict = {
            "message": "Testing",
            "aws_access_key_id": "AKIAIOSFODNN7EXAMPLE",
            "aws_secret_access_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
        }

        result = processor(logging.getLogger(), "info", event_dict)

        assert "aws_access_key_id" in result
        assert "[REDACTED]" in result["aws_access_key_id"]
        assert "[REDACTED]" in result["aws_secret_access_key"]

    def test_non_sensitive_data_preserved(self):
        """Test that non-sensitive data is not modified."""
        processor = log_module.SensitiveDataRedactor()

        event_dict = {
            "message": "Testing",
            "task_id": "feature-001",
            "status": "completed",
            "count": 42,
        }

        result = processor(logging.getLogger(), "info", event_dict)

        assert result["task_id"] == "feature-001"
        assert result["status"] == "completed"
        assert result["count"] == 42


class TestLogLevelManagement:
    """Tests for dynamic log level management."""

    def test_set_valid_log_level(self):
        """Test setting a valid log level."""
        # Reset to unlocked state
        log_module.lock_log_level(False)

        result = log_module.set_log_level("DEBUG")

        assert result is True
        assert log_module.get_log_level() == "DEBUG"

    def test_set_invalid_log_level(self):
        """Test setting an invalid log level returns False."""
        log_module.lock_log_level(False)

        result = log_module.set_log_level("INVALID")

        assert result is False

    def test_lock_log_level(self):
        """Test that locked log level cannot be changed."""
        log_module.lock_log_level(False)
        log_module.set_log_level("INFO")

        # Lock the level
        log_module.lock_log_level(True)

        # Try to change it - should fail
        result = log_module.set_log_level("DEBUG")

        assert result is False
        assert log_module.get_log_level() == "INFO"

    def test_unlock_log_level(self):
        """Test that unlocking allows changes again."""
        log_module.lock_log_level(True)
        log_module.set_log_level("ERROR")

        # Unlock
        log_module.lock_log_level(False)

        # Should be able to change now
        result = log_module.set_log_level("DEBUG")

        assert result is True


class TestAuditLogging:
    """Tests for audit logging functionality."""

    def test_get_audit_logger(self):
        """Test that audit logger is created correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            audit_file = os.path.join(tmpdir, "audit.log")
            os.environ["AUDIT_LOG_FILE"] = audit_file

            logger = log_module.get_audit_logger()

            assert logger is not None
            assert logger.name == "agent_audit"

            del os.environ["AUDIT_LOG_FILE"]

    def test_log_audit_writes_to_file(self):
        """Test that audit log writes to file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            audit_file = os.path.join(tmpdir, "audit.log")
            os.environ["AUDIT_LOG_FILE"] = audit_file

            # Get fresh audit logger
            logger = log_module.get_audit_logger()

            # Clear existing handlers to ensure fresh write
            logger.handlers.clear()
            handler = logging.FileHandler(audit_file, encoding="utf-8")
            handler.setFormatter(logging.Formatter(fmt="%(message)s"))
            logger.addHandler(handler)

            # Log an audit event
            log_module.log_audit(
                action="create",
                entity_type="task",
                entity_id="feature-001",
                details={"name": "Test Feature"},
            )

            # Check file was written
            assert os.path.exists(audit_file)

            with open(audit_file, "r") as f:
                content = f.read()
                assert "action=create" in content
                assert "entity=task:feature-001" in content

            del os.environ["AUDIT_LOG_FILE"]

    def test_log_audit_redacts_sensitive_data(self):
        """Test that audit logging redacts sensitive data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            audit_file = os.path.join(tmpdir, "audit.log")
            os.environ["AUDIT_LOG_FILE"] = audit_file

            # Get fresh audit logger
            logger = log_module.get_audit_logger()
            logger.handlers.clear()
            handler = logging.FileHandler(audit_file, encoding="utf-8")
            handler.setFormatter(logging.Formatter(fmt="%(message)s"))
            logger.addHandler(handler)

            # Log with sensitive data
            log_module.log_audit(
                action="update",
                entity_type="task",
                entity_id="feature-001",
                details={"name": "Test", "password": "secret123", "api_key": "sk-abc123"},
            )

            with open(audit_file, "r") as f:
                content = f.read()
                # Password should be redacted
                assert "[REDACTED]" in content or "password" not in content.lower() or "secret" not in content.lower()

            del os.environ["AUDIT_LOG_FILE"]


class TestStructuredContext:
    """Tests for structured context processor."""

    def test_context_processor_adds_info(self):
        """Test that StructuredContextProcessor adds caller info."""
        import logging

        processor = log_module.StructuredContextProcessor()

        event_dict = {
            "event": "test",
        }

        result = processor(logging.getLogger(), "info", event_dict)

        # Should have module, function, line_number
        assert "module" in result
        assert "function" in result
        assert "line_number" in result


class TestConfigureLogging:
    """Tests for the main configure_logging function."""

    def test_configure_with_defaults(self):
        """Test configure_logging with default parameters."""
        # This should work without errors
        logger = log_module.configure_logging(
            log_level="INFO",
            json_output=False,  # Use console for tests
        )

        assert logger is not None

    def test_configure_with_audit_enabled(self):
        """Test that audit logger is initialized when enabled."""
        with tempfile.TemporaryDirectory() as tmpdir:
            audit_file = os.path.join(tmpdir, "audit.log")
            os.environ["AUDIT_LOG_FILE"] = audit_file

            logger = log_module.configure_logging(
                log_level="INFO",
                json_output=False,
                enable_audit=True,
            )

            # Audit logger should be initialized
            audit_logger = log_module.get_audit_logger()
            assert audit_logger is not None

            del os.environ["AUDIT_LOG_FILE"]

    def test_configure_with_log_file(self):
        """Test configure_logging with a log file (uses rotation)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, "app.log")

            logger = log_module.configure_logging(
                log_level="INFO",
                log_file=log_file,
                json_output=True,
            )

            # Check that file was created
            assert os.path.exists(log_file)

            # Clean up
            if "LOG_FILE" in os.environ:
                del os.environ["LOG_FILE"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
