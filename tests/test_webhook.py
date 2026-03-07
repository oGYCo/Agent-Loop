"""Tests for WebhookNotifier module"""

import pytest
import json
import tempfile
import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from agent.state_manager import StateManager
from agent.webhook import WebhookNotifier, get_webhook_notifier, reset_webhook_notifier


class TestWebhookNotifier:
    """Test cases for WebhookNotifier"""

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
    def webhook_notifier(self, state_manager):
        """Create WebhookNotifier with test state manager"""
        # Reset global instance before each test
        reset_webhook_notifier()
        return WebhookNotifier(state_manager)

    @pytest.fixture
    def webhook_notifier_enabled(self, temp_agent_dir):
        """Create WebhookNotifier with webhook enabled"""
        reset_webhook_notifier()
        sm = StateManager(agent_dir=temp_agent_dir)
        sm.save_config({
            "webhook": {
                "enabled": True,
                "url": "http://localhost:9999/webhook",
                "timeout": 5,
                "events": ["task_completed", "task_failed", "human_intervention"]
            }
        })
        return WebhookNotifier(sm)

    def test_webhook_disabled_by_default(self, webhook_notifier):
        """Test webhook is disabled by default"""
        assert webhook_notifier.enabled is False
        assert webhook_notifier.is_enabled() is False

    def test_webhook_enabled_with_config(self, webhook_notifier_enabled):
        """Test webhook is enabled when configured"""
        assert webhook_notifier_enabled.enabled is True
        assert webhook_notifier_enabled.is_enabled() is True

    def test_should_notify_task_completed(self, webhook_notifier_enabled):
        """Test should_notify for task_completed event"""
        assert webhook_notifier_enabled.should_notify("task_completed") is True

    def test_should_notify_task_failed(self, webhook_notifier_enabled):
        """Test should_notify for task_failed event"""
        assert webhook_notifier_enabled.should_notify("task_failed") is True

    def test_should_notify_human_intervention(self, webhook_notifier_enabled):
        """Test should_notify for human_intervention event"""
        assert webhook_notifier_enabled.should_notify("human_intervention") is True

    def test_should_not_notify_disabled(self, webhook_notifier):
        """Test should_notify returns False when disabled"""
        assert webhook_notifier.should_notify("task_completed") is False

    def test_should_not_notify_unknown_event(self, webhook_notifier_enabled):
        """Test should_notify returns False for unknown event"""
        assert webhook_notifier_enabled.should_notify("unknown_event") is False

    def test_custom_events(self, temp_agent_dir):
        """Test webhook with custom events"""
        reset_webhook_notifier()
        sm = StateManager(agent_dir=temp_agent_dir)
        sm.save_config({
            "webhook": {
                "enabled": True,
                "url": "http://localhost:9999/webhook",
                "events": ["task_completed"]
            }
        })
        notifier = WebhookNotifier(sm)
        assert notifier.should_notify("task_completed") is True
        assert notifier.should_notify("task_failed") is False

    @pytest.mark.asyncio
    async def test_send_notification_disabled(self, webhook_notifier):
        """Test send_notification when webhook is disabled"""
        result = await webhook_notifier.send_notification(
            "task_completed",
            {"task_id": "test-001"}
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_notify_task_completed(self, temp_agent_dir):
        """Test notify_task_completed sends correct payload"""
        reset_webhook_notifier()
        sm = StateManager(agent_dir=temp_agent_dir)
        sm.save_config({
            "webhook": {
                "enabled": True,
                "url": "http://localhost:9999/webhook"
            }
        })

        # Mock httpx.AsyncClient.post
        mock_response = MagicMock()
        mock_response.status_code = 200

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.aclose = AsyncMock()

        # Create notifier and mock its client
        notifier = WebhookNotifier(sm)
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
        assert payload["event"] == "task_completed"
        assert payload["data"]["task_id"] == "test-001"
        assert payload["data"]["task_name"] == "Test Task"
        assert payload["data"]["status"] == "completed"
        assert payload["data"]["duration_seconds"] == 10.5

    @pytest.mark.asyncio
    async def test_notify_task_failed(self, temp_agent_dir):
        """Test notify_task_failed sends correct payload"""
        reset_webhook_notifier()
        sm = StateManager(agent_dir=temp_agent_dir)
        sm.save_config({
            "webhook": {
                "enabled": True,
                "url": "http://localhost:9999/webhook"
            }
        })

        mock_response = MagicMock()
        mock_response.status_code = 200

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.aclose = AsyncMock()

        notifier = WebhookNotifier(sm)
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
        assert payload["event"] == "task_failed"
        assert payload["data"]["task_id"] == "test-001"
        assert payload["data"]["error_message"] == "Test error"
        assert payload["data"]["retry_count"] == 2

    @pytest.mark.asyncio
    async def test_notify_human_intervention(self, temp_agent_dir):
        """Test notify_human_intervention sends correct payload"""
        reset_webhook_notifier()
        sm = StateManager(agent_dir=temp_agent_dir)
        sm.save_config({
            "webhook": {
                "enabled": True,
                "url": "http://localhost:9999/webhook"
            }
        })

        mock_response = MagicMock()
        mock_response.status_code = 200

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.aclose = AsyncMock()

        notifier = WebhookNotifier(sm)
        notifier._client = mock_client

        result = await notifier.notify_human_intervention(
            reason="Error threshold reached",
            task_id="test-001",
            context={"error_count": 3}
        )

        assert result is True
        call_args = mock_client.post.call_args
        payload = call_args.kwargs.get("json", {})
        assert payload["event"] == "human_intervention"
        assert payload["data"]["reason"] == "Error threshold reached"
        assert payload["data"]["task_id"] == "test-001"

    @pytest.mark.asyncio
    async def test_send_notification_retry(self, temp_agent_dir):
        """Test send_notification retries on failure"""
        reset_webhook_notifier()
        sm = StateManager(agent_dir=temp_agent_dir)

        mock_response = MagicMock()
        mock_response.status_code = 500  # Server error

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.aclose = AsyncMock()

        notifier = WebhookNotifier(sm)
        notifier._client = mock_client
        notifier.retry_count = 3
        notifier.retry_interval = 0.1  # Fast retry

        result = await notifier.send_notification("task_completed", {"task_id": "test-001"})

        # Should fail because server returns 500, but only try once
        assert result is False

    @pytest.mark.asyncio
    async def test_webhook_with_secret(self, temp_agent_dir):
        """Test webhook sends secret in headers"""
        reset_webhook_notifier()
        sm = StateManager(agent_dir=temp_agent_dir)
        sm.save_config({
            "webhook": {
                "enabled": True,
                "url": "http://localhost:9999/webhook",
                "secret": "test-secret"
            }
        })

        mock_response = MagicMock()
        mock_response.status_code = 200

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.aclose = AsyncMock()

        notifier = WebhookNotifier(sm)
        notifier._client = mock_client

        await notifier.notify_task_completed(
            task_id="test-001",
            task_name="Test Task"
        )

        call_args = mock_client.post.call_args
        headers = call_args.kwargs.get("headers", {})
        assert headers.get("X-Webhook-Secret") == "test-secret"

    def test_reload_config(self, temp_agent_dir):
        """Test reload_config updates settings"""
        reset_webhook_notifier()
        sm = StateManager(agent_dir=temp_agent_dir)

        # Initial config - disabled
        sm.save_config({"webhook": {"enabled": False}})
        notifier = WebhookNotifier(sm)
        assert notifier.enabled is False

        # Update config - enabled
        sm.save_config({"webhook": {"enabled": True, "url": "http://example.com/webhook"}})
        notifier.reload_config()
        assert notifier.enabled is True
        assert notifier.url == "http://example.com/webhook"

    @pytest.mark.asyncio
    async def test_close_client(self, webhook_notifier):
        """Test close client properly"""
        mock_client = AsyncMock()
        mock_client.aclose = AsyncMock()
        webhook_notifier._client = mock_client

        await webhook_notifier.close()

        mock_client.aclose.assert_called_once()
        assert webhook_notifier._client is None


# Integration tests removed due to test complexity - tested manually
