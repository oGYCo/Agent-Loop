"""Tests for SlackNotifier module"""

import pytest
import json
import tempfile
import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from agent.state_manager import StateManager
from agent.slack_notifier import SlackNotifier, get_slack_notifier, reset_slack_notifier


class TestSlackNotifier:
    """Test cases for SlackNotifier"""

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
    def slack_notifier(self, state_manager):
        """Create SlackNotifier with test state manager"""
        reset_slack_notifier()
        return SlackNotifier(state_manager)

    @pytest.fixture
    def slack_notifier_enabled(self, temp_agent_dir):
        """Create SlackNotifier with Slack enabled"""
        reset_slack_notifier()
        sm = StateManager(agent_dir=temp_agent_dir)
        sm.save_config({
            "slack": {
                "enabled": True,
                "webhook_url": "https://hooks.slack.com/services/T00000000/B00000000/XXXXXXX",
                "channel": "#agent-loop",
                "username": "Test Agent",
                "icon_emoji": ":robot_face:",
                "events": ["task_completed", "task_failed", "human_intervention"]
            }
        })
        return SlackNotifier(sm)

    def test_slack_disabled_by_default(self, slack_notifier):
        """Test Slack is disabled by default"""
        assert slack_notifier.enabled is False
        assert slack_notifier.is_enabled() is False

    def test_slack_enabled_with_config(self, slack_notifier_enabled):
        """Test Slack is enabled when configured"""
        assert slack_notifier_enabled.enabled is True
        assert slack_notifier_enabled.is_enabled() is True
        assert slack_notifier_enabled.webhook_url == "https://hooks.slack.com/services/T00000000/B00000000/XXXXXXX"
        assert slack_notifier_enabled.channel == "#agent-loop"

    def test_should_notify_task_completed(self, slack_notifier_enabled):
        """Test should_notify for task_completed event"""
        assert slack_notifier_enabled.should_notify("task_completed") is True

    def test_should_notify_task_failed(self, slack_notifier_enabled):
        """Test should_notify for task_failed event"""
        assert slack_notifier_enabled.should_notify("task_failed") is True

    def test_should_notify_human_intervention(self, slack_notifier_enabled):
        """Test should_notify for human_intervention event"""
        assert slack_notifier_enabled.should_notify("human_intervention") is True

    def test_should_not_notify_disabled(self, slack_notifier):
        """Test should_notify returns False when disabled"""
        assert slack_notifier.should_notify("task_completed") is False

    def test_should_not_notify_unknown_event(self, slack_notifier_enabled):
        """Test should_notify returns False for unknown event"""
        assert slack_notifier_enabled.should_notify("unknown_event") is False

    def test_custom_events(self, temp_agent_dir):
        """Test Slack with custom events"""
        reset_slack_notifier()
        sm = StateManager(agent_dir=temp_agent_dir)
        sm.save_config({
            "slack": {
                "enabled": True,
                "webhook_url": "https://hooks.slack.com/services/T00000000/B00000000/XXXXXXX",
                "events": ["task_completed"]
            }
        })
        notifier = SlackNotifier(sm)
        assert notifier.should_notify("task_completed") is True
        assert notifier.should_notify("task_failed") is False

    @pytest.mark.asyncio
    async def test_send_notification_disabled(self, slack_notifier):
        """Test send_notification when Slack is disabled"""
        result = await slack_notifier.send_notification(
            "task_completed",
            {"task_id": "test-001"}
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_notify_task_completed(self, temp_agent_dir):
        """Test notify_task_completed sends correct payload"""
        reset_slack_notifier()
        sm = StateManager(agent_dir=temp_agent_dir)
        sm.save_config({
            "slack": {
                "enabled": True,
                "webhook_url": "https://hooks.slack.com/services/T00000000/B00000000/XXXXXXX",
                "channel": "#test"
            }
        })

        # Mock httpx.AsyncClient.post
        mock_response = MagicMock()
        mock_response.status_code = 200

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.aclose = AsyncMock()

        # Create notifier and mock its client
        notifier = SlackNotifier(sm)
        notifier._client = mock_client

        result = await notifier.notify_task_completed(
            task_id="test-001",
            task_name="Test Task",
            duration=10.5
        )

        assert result is True
        mock_client.post.assert_called_once()

        # Verify payload
        call_args = mock_client.post.call_args
        payload = call_args.kwargs.get("json", {})
        assert "attachments" in payload
        assert payload["channel"] == "#test"

    @pytest.mark.asyncio
    async def test_notify_task_failed(self, temp_agent_dir):
        """Test notify_task_failed sends correct payload"""
        reset_slack_notifier()
        sm = StateManager(agent_dir=temp_agent_dir)
        sm.save_config({
            "slack": {
                "enabled": True,
                "webhook_url": "https://hooks.slack.com/services/T00000000/B00000000/XXXXXXX"
            }
        })

        mock_response = MagicMock()
        mock_response.status_code = 200

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.aclose = AsyncMock()

        notifier = SlackNotifier(sm)
        notifier._client = mock_client

        result = await notifier.notify_task_failed(
            task_id="test-001",
            task_name="Test Task",
            error_message="Test error",
            retry_count=2
        )

        assert result is True
        call_args = mock_client.post.call_args
        payload = call_args.kwargs.get("json", {})
        assert "attachments" in payload

    @pytest.mark.asyncio
    async def test_notify_human_intervention(self, temp_agent_dir):
        """Test notify_human_intervention sends correct payload"""
        reset_slack_notifier()
        sm = StateManager(agent_dir=temp_agent_dir)
        sm.save_config({
            "slack": {
                "enabled": True,
                "webhook_url": "https://hooks.slack.com/services/T00000000/B00000000/XXXXXXX"
            }
        })

        mock_response = MagicMock()
        mock_response.status_code = 200

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.aclose = AsyncMock()

        notifier = SlackNotifier(sm)
        notifier._client = mock_client

        result = await notifier.notify_human_intervention(
            reason="Error threshold reached",
            task_id="test-001",
            context={"error_count": 3}
        )

        assert result is True
        call_args = mock_client.post.call_args
        payload = call_args.kwargs.get("json", {})
        assert "attachments" in payload

    @pytest.mark.asyncio
    async def test_build_message_blocks_task_completed(self, slack_notifier_enabled):
        """Test _build_message_blocks for task_completed"""
        data = {
            "task_id": "test-001",
            "task_name": "Test Task",
            "duration_seconds": 10.5,
            "status": "completed"
        }
        payload = slack_notifier_enabled._build_message_blocks("task_completed", data)

        assert "attachments" in payload
        assert len(payload["attachments"]) == 1
        assert payload["attachments"][0]["color"] == "#4CAF50"

    @pytest.mark.asyncio
    async def test_build_message_blocks_task_failed(self, slack_notifier_enabled):
        """Test _build_message_blocks for task_failed"""
        data = {
            "task_id": "test-001",
            "task_name": "Test Task",
            "error_message": "Connection timeout",
            "retry_count": 2,
            "status": "failed"
        }
        payload = slack_notifier_enabled._build_message_blocks("task_failed", data)

        assert "attachments" in payload
        assert payload["attachments"][0]["color"] == "#f44336"

    @pytest.mark.asyncio
    async def test_build_message_blocks_human_intervention(self, slack_notifier_enabled):
        """Test _build_message_blocks for human_intervention"""
        data = {
            "task_id": "test-001",
            "task_name": "Test Task",
            "reason": "Error threshold reached",
            "status": "intervention_required"
        }
        payload = slack_notifier_enabled._build_message_blocks("human_intervention", data)

        assert "attachments" in payload
        assert payload["attachments"][0]["color"] == "#ff9800"

    @pytest.mark.asyncio
    async def test_send_notification_retry(self, temp_agent_dir):
        """Test send_notification retries on failure"""
        reset_slack_notifier()
        sm = StateManager(agent_dir=temp_agent_dir)

        mock_response = MagicMock()
        mock_response.status_code = 500  # Server error

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.aclose = AsyncMock()

        notifier = SlackNotifier(sm)
        notifier._client = mock_client
        notifier.retry_count = 3
        notifier.retry_interval = 0.1  # Fast retry

        result = await notifier.send_notification("task_completed", {"task_id": "test-001"})

        # Should fail because server returns 500
        assert result is False

    @pytest.mark.asyncio
    async def test_slack_with_channel_and_username(self, temp_agent_dir):
        """Test Slack sends channel and username"""
        reset_slack_notifier()
        sm = StateManager(agent_dir=temp_agent_dir)
        sm.save_config({
            "slack": {
                "enabled": True,
                "webhook_url": "https://hooks.slack.com/services/T00000000/B00000000/XXXXXXX",
                "channel": "#my-channel",
                "username": "MyBot",
                "icon_emoji": ":wave:"
            }
        })

        mock_response = MagicMock()
        mock_response.status_code = 200

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.aclose = AsyncMock()

        notifier = SlackNotifier(sm)
        notifier._client = mock_client

        await notifier.notify_task_completed(
            task_id="test-001",
            task_name="Test Task"
        )

        call_args = mock_client.post.call_args
        payload = call_args.kwargs.get("json", {})
        assert payload.get("channel") == "#my-channel"
        assert payload.get("username") == "MyBot"
        assert payload.get("icon_emoji") == ":wave:"

    def test_reload_config(self, temp_agent_dir):
        """Test reload_config updates settings"""
        reset_slack_notifier()
        sm = StateManager(agent_dir=temp_agent_dir)

        # Initial config - disabled
        sm.save_config({"slack": {"enabled": False}})
        notifier = SlackNotifier(sm)
        assert notifier.enabled is False

        # Update config - enabled
        sm.save_config({"slack": {"enabled": True, "webhook_url": "https://example.com/webhook"}})
        notifier.reload_config()
        assert notifier.enabled is True
        assert notifier.webhook_url == "https://example.com/webhook"

    @pytest.mark.asyncio
    async def test_close_client(self, slack_notifier):
        """Test close client properly"""
        mock_client = AsyncMock()
        mock_client.aclose = AsyncMock()
        slack_notifier._client = mock_client

        await slack_notifier.close()

        mock_client.aclose.assert_called_once()
        assert slack_notifier._client is None


class TestSlackNotifierTemplates:
    """Test cases for Slack templates"""

    @pytest.fixture
    def slack_notifier(self):
        """Create SlackNotifier instance"""
        reset_slack_notifier()
        return SlackNotifier()

    def test_templates_exist(self, slack_notifier):
        """Test all required templates exist"""
        assert "task_completed" in slack_notifier.TEMPLATES
        assert "task_failed" in slack_notifier.TEMPLATES
        assert "human_intervention" in slack_notifier.TEMPLATES

    def test_templates_have_required_fields(self, slack_notifier):
        """Test templates have required fields"""
        for template_name, template in slack_notifier.TEMPLATES.items():
            assert "emoji" in template, f"Missing emoji in {template_name}"
            assert "color" in template, f"Missing color in {template_name}"
            assert "title" in template, f"Missing title in {template_name}"

    def test_templates_have_correct_colors(self, slack_notifier):
        """Test templates have correct colors"""
        assert slack_notifier.TEMPLATES["task_completed"]["color"] == "#4CAF50"
        assert slack_notifier.TEMPLATES["task_failed"]["color"] == "#f44336"
        assert slack_notifier.TEMPLATES["human_intervention"]["color"] == "#ff9800"
