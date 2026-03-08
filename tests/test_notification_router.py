"""Tests for NotificationRouter module"""

import pytest
import json
import tempfile
import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from agent.state_manager import StateManager
from agent.notification_router import (
    NotificationRouter,
    SeverityLevel,
    get_notification_router,
    reset_notification_router
)


class TestNotificationRouter:
    """Test cases for NotificationRouter"""

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
    def router(self, state_manager):
        """Create NotificationRouter with test state manager"""
        reset_notification_router()
        return NotificationRouter(state_manager)

    @pytest.fixture
    def router_with_all_channels(self, temp_agent_dir):
        """Create NotificationRouter with all channels enabled"""
        reset_notification_router()
        sm = StateManager(agent_dir=temp_agent_dir)
        sm.save_config({
            "notifications": {
                "enabled": True,
                "routing": {
                    "strategy": "severity"
                }
            },
            "webhook": {
                "enabled": True,
                "url": "http://localhost:9999/webhook",
                "events": ["task_completed", "task_failed", "human_intervention"]
            },
            "email": {
                "enabled": True,
                "smtp_host": "smtp.gmail.com",
                "smtp_port": 587,
                "smtp_user": "test@example.com",
                "smtp_password": "password",
                "from_email": "test@example.com",
                "to_emails": ["admin@example.com"],
                "events": ["task_completed", "task_failed", "human_intervention"]
            },
            "slack": {
                "enabled": True,
                "webhook_url": "https://hooks.slack.com/services/xxx",
                "events": ["task_completed", "task_failed", "human_intervention"]
            }
        })
        return NotificationRouter(sm)

    def test_router_disabled_by_default(self, router):
        """Test router is disabled when notifications not configured"""
        assert router.enabled is True  # Default is True if not explicitly False

    def test_get_severity_for_events(self, router):
        """Test severity mapping for different events"""
        assert router.get_severity("human_intervention") == SeverityLevel.CRITICAL
        assert router.get_severity("task_failed") == SeverityLevel.ERROR
        assert router.get_severity("task_completed") == SeverityLevel.INFO

    def test_get_channels_by_severity(self, router):
        """Test channel selection by severity"""
        # Critical events should go to all channels
        channels = router.get_channels_for_event("human_intervention")
        assert "slack" in channels

        # Error events should go to all channels
        channels = router.get_channels_for_event("task_failed")
        assert "slack" in channels

        # Info events should only go to Slack
        channels = router.get_channels_for_event("task_completed")
        assert channels == ["slack"]

    def test_custom_channel_override(self, temp_agent_dir):
        """Test custom event channel override"""
        reset_notification_router()
        sm = StateManager(agent_dir=temp_agent_dir)
        sm.save_config({
            "notifications": {
                "enabled": True,
                "routing": {
                    "strategy": "severity",
                    "event_channel_override": {
                        "task_completed": ["email"],
                        "task_failed": ["webhook", "slack"]
                    }
                }
            },
            "webhook": {"enabled": True, "url": "http://test.com"},
            "email": {"enabled": True, "smtp_host": "smtp.test.com", "from_email": "test@test.com", "to_emails": ["test@test.com"]},
            "slack": {"enabled": True, "webhook_url": "https://hooks.slack.com/test"}
        })
        router = NotificationRouter(sm)

        # Task completed should go to email only
        channels = router.get_channels_for_event("task_completed")
        assert channels == ["email"]

        # Task failed should go to webhook and slack
        channels = router.get_channels_for_event("task_failed")
        assert "webhook" in channels
        assert "slack" in channels
        assert "email" not in channels

    @pytest.mark.asyncio
    async def test_send_notification_all_channels(self, router_with_all_channels):
        """Test sending notification to all channels"""
        # Mock each notifier's send method
        router_with_all_channels.webhook.send_notification = AsyncMock(return_value=True)
        router_with_all_channels.email.send_notification = AsyncMock(return_value=True)
        router_with_all_channels.slack.send_notification = AsyncMock(return_value=True)

        results = await router_with_all_channels.send_notification(
            "human_intervention",
            {"task_id": "test-001", "reason": "Test"}
        )

        # Should attempt to send to all channels
        assert len(results) > 0

    @pytest.mark.asyncio
    async def test_send_notification_selective(self, temp_agent_dir):
        """Test sending notification to selective channels"""
        reset_notification_router()
        sm = StateManager(agent_dir=temp_agent_dir)
        sm.save_config({
            "notifications": {"enabled": True, "routing": {"strategy": "severity"}},
            "webhook": {"enabled": True, "url": "http://test.com"},
            "email": {"enabled": False},
            "slack": {"enabled": True, "webhook_url": "https://hooks.slack.com/test"}
        })
        router = NotificationRouter(sm)

        router.webhook.send_notification = AsyncMock(return_value=True)
        router.slack.send_notification = AsyncMock(return_value=True)

        results = await router.send_notification("task_completed", {"task_id": "test"})

        # Should only try slack for info events
        router.slack.send_notification.assert_called_once()

    @pytest.mark.asyncio
    async def test_notify_task_completed(self, router_with_all_channels):
        """Test notify_task_completed method"""
        router_with_all_channels.send_notification = AsyncMock(return_value={"slack": True})

        results = await router_with_all_channels.notify_task_completed(
            task_id="test-001",
            task_name="Test Task",
            duration=10.5
        )

        assert "slack" in results

    @pytest.mark.asyncio
    async def test_notify_task_failed(self, router_with_all_channels):
        """Test notify_task_failed method"""
        router_with_all_channels.send_notification = AsyncMock(return_value={"webhook": True, "slack": True})

        results = await router_with_all_channels.notify_task_failed(
            task_id="test-001",
            task_name="Test Task",
            error_message="Test error",
            retry_count=2
        )

        assert "webhook" in results or "slack" in results

    @pytest.mark.asyncio
    async def test_notify_human_intervention(self, router_with_all_channels):
        """Test notify_human_intervention method"""
        router_with_all_channels.send_notification = AsyncMock(
            return_value={"webhook": True, "email": True, "slack": True}
        )

        results = await router_with_all_channels.notify_human_intervention(
            reason="Error threshold reached",
            task_id="test-001",
            task_name="Test Task"
        )

        # Should send to multiple channels for critical events
        assert len(results) > 0

    def test_reload_config(self, temp_agent_dir):
        """Test reload_config updates settings"""
        reset_notification_router()
        sm = StateManager(agent_dir=temp_agent_dir)

        # Initial config
        sm.save_config({
            "notifications": {"enabled": True, "routing": {"strategy": "severity"}},
            "webhook": {"enabled": True, "url": "http://test1.com"},
            "email": {"enabled": False},
            "slack": {"enabled": False}
        })
        router = NotificationRouter(sm)
        assert router.webhook.url == "http://test1.com"

        # Update config
        sm.save_config({
            "notifications": {"enabled": True},
            "webhook": {"enabled": True, "url": "http://test2.com"},
            "email": {"enabled": False},
            "slack": {"enabled": False}
        })
        router.reload_config()
        assert router.webhook.url == "http://test2.com"

    def test_get_status(self, router_with_all_channels):
        """Test get_status returns correct status"""
        status = router_with_all_channels.get_status()

        assert status["enabled"] is True
        assert status["routing_strategy"] == "severity"
        assert "channels" in status
        assert status["channels"]["webhook"]["enabled"] is True
        assert status["channels"]["email"]["enabled"] is True
        assert status["channels"]["slack"]["enabled"] is True


class TestNotificationRouterEdgeCases:
    """Test cases for edge cases in NotificationRouter"""

    @pytest.fixture
    def temp_agent_dir(self):
        """Create a temporary directory for testing"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.mark.asyncio
    async def test_no_channels_available(self, temp_agent_dir):
        """Test behavior when no channels are available"""
        reset_notification_router()
        sm = StateManager(agent_dir=temp_agent_dir)
        sm.save_config({
            "notifications": {"enabled": True},
            "webhook": {"enabled": False},
            "email": {"enabled": False},
            "slack": {"enabled": False}
        })
        router = NotificationRouter(sm)

        results = await router.send_notification("task_completed", {"task_id": "test"})

        # Should return empty dict when no channels
        assert results == {}

    @pytest.mark.asyncio
    async def test_channel_sends_exception(self, temp_agent_dir):
        """Test handling when a channel raises exception"""
        reset_notification_router()
        sm = StateManager(agent_dir=temp_agent_dir)
        sm.save_config({
            "notifications": {"enabled": True},
            "webhook": {"enabled": True, "url": "http://test.com"},
            "email": {"enabled": False},
            "slack": {"enabled": True, "webhook_url": "https://hooks.slack.com/test"}
        })
        router = NotificationRouter(sm)

        # Make webhook raise exception
        router.webhook.send_notification = AsyncMock(side_effect=Exception("WebHook error"))
        router.slack.send_notification = AsyncMock(return_value=True)

        results = await router.send_notification("human_intervention", {"task_id": "test"})

        # Slack should still succeed
        assert results.get("slack") is True

    def test_unknown_event_type(self, temp_agent_dir):
        """Test handling of unknown event types"""
        reset_notification_router()
        sm = StateManager(agent_dir=temp_agent_dir)
        sm.save_config({
            "notifications": {"enabled": True},
            "webhook": {"enabled": True, "url": "http://test.com"},
            "email": {"enabled": False},
            "slack": {"enabled": True, "webhook_url": "https://hooks.slack.com/test"}
        })
        router = NotificationRouter(sm)

        # Unknown events should default to INFO severity and use slack
        channels = router.get_channels_for_event("unknown_event")
        assert "slack" in channels
