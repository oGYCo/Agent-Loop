"""Tests for EmailNotifier module"""

import pytest
import json
import tempfile
import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from agent.state_manager import StateManager
from agent.email_notifier import EmailNotifier, get_email_notifier, reset_email_notifier


class TestEmailNotifier:
    """Test cases for EmailNotifier"""

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
    def email_notifier(self, state_manager):
        """Create EmailNotifier with test state manager"""
        reset_email_notifier()
        return EmailNotifier(state_manager)

    @pytest.fixture
    def email_notifier_enabled(self, temp_agent_dir):
        """Create EmailNotifier with email enabled"""
        reset_email_notifier()
        sm = StateManager(agent_dir=temp_agent_dir)
        sm.save_config({
            "email": {
                "enabled": True,
                "smtp_host": "smtp.gmail.com",
                "smtp_port": 587,
                "smtp_user": "test@example.com",
                "smtp_password": "test-password",
                "use_tls": True,
                "from_name": "Test Agent",
                "from_email": "test@example.com",
                "to_emails": ["admin@example.com", "team@example.com"],
                "events": ["task_completed", "task_failed", "human_intervention"]
            }
        })
        return EmailNotifier(sm)

    def test_email_disabled_by_default(self, email_notifier):
        """Test email is disabled by default"""
        assert email_notifier.enabled is False
        assert email_notifier.is_enabled() is False

    def test_email_enabled_with_config(self, email_notifier_enabled):
        """Test email is enabled when configured"""
        assert email_notifier_enabled.enabled is True
        assert email_notifier_enabled.is_enabled() is True
        assert email_notifier_enabled.smtp_host == "smtp.gmail.com"
        assert len(email_notifier_enabled.to_emails) == 2

    def test_should_notify_task_completed(self, email_notifier_enabled):
        """Test should_notify for task_completed event"""
        assert email_notifier_enabled.should_notify("task_completed") is True

    def test_should_notify_task_failed(self, email_notifier_enabled):
        """Test should_notify for task_failed event"""
        assert email_notifier_enabled.should_notify("task_failed") is True

    def test_should_notify_human_intervention(self, email_notifier_enabled):
        """Test should_notify for human_intervention event"""
        assert email_notifier_enabled.should_notify("human_intervention") is True

    def test_should_not_notify_disabled(self, email_notifier):
        """Test should_notify returns False when disabled"""
        assert email_notifier.should_notify("task_completed") is False

    def test_should_not_notify_unknown_event(self, email_notifier_enabled):
        """Test should_notify returns False for unknown event"""
        assert email_notifier_enabled.should_notify("unknown_event") is False

    def test_custom_events(self, temp_agent_dir):
        """Test email with custom events"""
        reset_email_notifier()
        sm = StateManager(agent_dir=temp_agent_dir)
        sm.save_config({
            "email": {
                "enabled": True,
                "smtp_host": "smtp.gmail.com",
                "smtp_port": 587,
                "smtp_user": "test@example.com",
                "smtp_password": "password",
                "to_emails": ["admin@example.com"],
                "events": ["task_completed"]
            }
        })
        notifier = EmailNotifier(sm)
        assert notifier.should_notify("task_completed") is True
        assert notifier.should_notify("task_failed") is False

    @pytest.mark.asyncio
    async def test_send_notification_disabled(self, email_notifier):
        """Test send_notification when email is disabled"""
        result = await email_notifier.send_notification(
            "task_completed",
            {"task_id": "test-001"}
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_render_template_task_completed(self, email_notifier_enabled):
        """Test template rendering for task_completed"""
        variables = {
            "task_id": "test-001",
            "task_name": "Test Task",
            "duration": "10.50秒",
            "timestamp": "2026-03-08 12:00:00"
        }
        subject, body = email_notifier_enabled._render_template("task_completed", variables)
        assert "Test Task" in subject
        assert "test-001" in body
        assert "10.50秒" in body

    @pytest.mark.asyncio
    async def test_render_template_task_failed(self, email_notifier_enabled):
        """Test template rendering for task_failed"""
        variables = {
            "task_id": "test-001",
            "task_name": "Test Task",
            "error_message": "Connection timeout",
            "retry_count": 2,
            "timestamp": "2026-03-08 12:00:00"
        }
        subject, body = email_notifier_enabled._render_template("task_failed", variables)
        assert "Test Task" in subject
        assert "Connection timeout" in body

    @pytest.mark.asyncio
    async def test_render_template_human_intervention(self, email_notifier_enabled):
        """Test template rendering for human_intervention"""
        variables = {
            "task_id": "test-001",
            "task_name": "Test Task",
            "reason": "Error threshold reached",
            "timestamp": "2026-03-08 12:00:00"
        }
        subject, body = email_notifier_enabled._render_template("human_intervention", variables)
        assert "Test Task" in subject
        assert "Error threshold reached" in body

    @pytest.mark.asyncio
    @patch("agent.email_notifier.aiosmtplib.send")
    async def test_send_email_success(self, mock_send, email_notifier_enabled):
        """Test send_email successful"""
        mock_send.return_value = None  # Success

        result = await email_notifier_enabled.send_email(
            subject="Test Subject",
            body="<p>Test Body</p>"
        )

        assert result is True
        assert mock_send.called

    @pytest.mark.asyncio
    @patch("agent.email_notifier.aiosmtplib.send")
    async def test_send_email_failure(self, mock_send, email_notifier_enabled):
        """Test send_email failure"""
        mock_send.side_effect = Exception("SMTP Error")

        result = await email_notifier_enabled.send_email(
            subject="Test Subject",
            body="<p>Test Body</p>"
        )

        assert result is False

    @pytest.mark.asyncio
    @patch("agent.email_notifier.aiosmtplib.send")
    async def test_notify_task_completed(self, mock_send, email_notifier_enabled):
        """Test notify_task_completed sends email"""
        mock_send.return_value = None

        result = await email_notifier_enabled.notify_task_completed(
            task_id="test-001",
            task_name="Test Task",
            duration=10.5
        )

        assert result is True
        assert mock_send.called
        # Check email was sent to all recipients
        assert mock_send.call_count == 2

    @pytest.mark.asyncio
    @patch("agent.email_notifier.aiosmtplib.send")
    async def test_notify_task_failed(self, mock_send, email_notifier_enabled):
        """Test notify_task_failed sends email"""
        mock_send.return_value = None

        result = await email_notifier_enabled.notify_task_failed(
            task_id="test-001",
            task_name="Test Task",
            error_message="Test error",
            retry_count=2
        )

        assert result is True
        assert mock_send.called

    @pytest.mark.asyncio
    @patch("agent.email_notifier.aiosmtplib.send")
    async def test_notify_human_intervention(self, mock_send, email_notifier_enabled):
        """Test notify_human_intervention sends email"""
        mock_send.return_value = None

        result = await email_notifier_enabled.notify_human_intervention(
            reason="Error threshold reached",
            task_id="test-001",
            task_name="Test Task",
            context={"error_count": 3}
        )

        assert result is True
        assert mock_send.called

    def test_reload_config(self, temp_agent_dir):
        """Test reload_config updates settings"""
        reset_email_notifier()
        sm = StateManager(agent_dir=temp_agent_dir)

        # Initial config - disabled
        sm.save_config({"email": {"enabled": False}})
        notifier = EmailNotifier(sm)
        assert notifier.enabled is False

        # Update config - enabled
        sm.save_config({
            "email": {
                "enabled": True,
                "smtp_host": "smtp.example.com",
                "smtp_user": "user@example.com",
                "smtp_password": "password",
                "to_emails": ["test@example.com"]
            }
        })
        notifier.reload_config()
        assert notifier.enabled is True
        assert notifier.smtp_host == "smtp.example.com"

    @pytest.mark.asyncio
    async def test_test_email_disabled(self, email_notifier):
        """Test test_email when disabled"""
        result = await email_notifier.test_email()
        assert result["success"] is False
        assert "not enabled" in result["message"]

    @pytest.mark.asyncio
    @patch("agent.email_notifier.aiosmtplib.send")
    async def test_test_email_success(self, mock_send, email_notifier_enabled):
        """Test test_email when enabled"""
        mock_send.return_value = None

        result = await email_notifier_enabled.test_email()
        assert result["success"] is True
        assert mock_send.called

    @pytest.mark.asyncio
    @patch("agent.email_notifier.aiosmtplib.send")
    async def test_test_email_failure(self, mock_send, email_notifier_enabled):
        """Test test_email when sending fails"""
        mock_send.side_effect = Exception("SMTP Error")

        result = await email_notifier_enabled.test_email()
        assert result["success"] is False
        assert "Failed" in result["message"] or "Error" in result["message"]

    def test_email_no_recipients(self, temp_agent_dir):
        """Test email with no recipients configured"""
        reset_email_notifier()
        sm = StateManager(agent_dir=temp_agent_dir)
        sm.save_config({
            "email": {
                "enabled": True,
                "smtp_host": "smtp.gmail.com",
                "smtp_port": 587,
                "smtp_user": "test@example.com",
                "smtp_password": "password",
                "to_emails": []  # No recipients
            }
        })
        notifier = EmailNotifier(sm)
        assert notifier.is_enabled() is False


class TestEmailNotifierTemplates:
    """Test cases for email templates"""

    @pytest.fixture
    def email_notifier(self):
        """Create EmailNotifier instance"""
        reset_email_notifier()
        return EmailNotifier()

    def test_templates_exist(self, email_notifier):
        """Test all required templates exist"""
        assert "task_completed" in email_notifier.TEMPLATES
        assert "task_failed" in email_notifier.TEMPLATES
        assert "human_intervention" in email_notifier.TEMPLATES

    def test_templates_have_subject_and_body(self, email_notifier):
        """Test templates have subject and body"""
        for template_name, template in email_notifier.TEMPLATES.items():
            assert "subject" in template, f"Missing subject in {template_name}"
            assert "body" in template, f"Missing body in {template_name}"
            assert template["subject"], f"Empty subject in {template_name}"
            assert template["body"], f"Empty body in {template_name}"

    def test_templates_are_html(self, email_notifier):
        """Test templates are HTML"""
        for template_name, template in email_notifier.TEMPLATES.items():
            assert "<html" in template["body"].lower(), f"Not HTML in {template_name}"
