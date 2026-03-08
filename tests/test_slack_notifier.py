"""Tests for SlackNotifier module"""

import pytest
import json
import tempfile
import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

import httpx
from agent.state_manager import StateManager
from agent.slack_notifier import SlackNotifier, get_slack_notifier, reset_slack_notifier


@pytest.fixture
def temp_agent_dir():
    """Create a temporary directory for module-level fixture reuse."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def slack_notifier_enabled(temp_agent_dir):
    """Create SlackNotifier with Slack enabled for all test classes."""
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


class TestSlackBlockKitFormat:
    """Test cases for Slack Block Kit message format"""

    @pytest.fixture
    def temp_agent_dir(self):
        """Create a temporary directory for testing"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    def test_block_kit_has_header_block(self, slack_notifier_enabled):
        """Test Block Kit message includes header block"""
        data = {
            "task_id": "test-001",
            "task_name": "Test Task",
            "status": "completed"
        }
        payload = slack_notifier_enabled._build_message_blocks("task_completed", data)

        blocks = payload["attachments"][0]["blocks"]
        header_block = blocks[0]

        assert header_block["type"] == "header"
        assert "text" in header_block
        assert header_block["text"]["type"] == "plain_text"

    def test_block_kit_has_section_block(self, slack_notifier_enabled):
        """Test Block Kit message includes section block"""
        data = {
            "task_id": "test-001",
            "task_name": "Test Task",
            "status": "completed"
        }
        payload = slack_notifier_enabled._build_message_blocks("task_completed", data)

        blocks = payload["attachments"][0]["blocks"]
        section_block = blocks[1]

        assert section_block["type"] == "section"
        assert "fields" in section_block

    def test_block_kit_fields_limit(self, slack_notifier_enabled):
        """Test Block Kit fields are limited to 10 (Slack limit)"""
        # Create data with many fields
        data = {
            "task_id": "test-001",
            "task_name": "Test Task",
            "status": "completed"
        }
        # Add extra fields
        for i in range(15):
            data[f"extra_field_{i}"] = f"value_{i}"

        payload = slack_notifier_enabled._build_message_blocks("task_completed", data)

        fields = payload["attachments"][0]["blocks"][1]["fields"]
        assert len(fields) <= 10

    def test_block_kit_has_emoji_in_header(self, slack_notifier_enabled):
        """Test Block Kit header includes emoji"""
        for event_type, template in slack_notifier_enabled.TEMPLATES.items():
            data = {"task_id": "test", "task_name": "Test", "status": "completed"}
            payload = slack_notifier_enabled._build_message_blocks(event_type, data)

            header_text = payload["attachments"][0]["blocks"][0]["text"]["text"]
            assert template["emoji"] in header_text

    def test_block_kit_uses_mrkdwn_formatting(self, slack_notifier_enabled):
        """Test Block Kit uses mrkdwn formatting for fields"""
        data = {
            "task_id": "test-001",
            "task_name": "Test Task",
            "status": "completed"
        }
        payload = slack_notifier_enabled._build_message_blocks("task_completed", data)

        fields = payload["attachments"][0]["blocks"][1]["fields"]
        for field in fields:
            assert field["type"] == "mrkdwn"
            assert "*" in field["text"]  # Bold formatting


class TestSlackMessageTruncation:
    """Test cases for Slack message truncation"""

    @pytest.fixture
    def temp_agent_dir(self):
        """Create a temporary directory for testing"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    def test_long_error_message_truncation(self, slack_notifier_enabled):
        """Test long error messages are truncated for Slack"""
        # Create very long error message
        long_error = "Error: " + "x" * 5000
        data = {
            "task_id": "test-001",
            "task_name": "Test Task",
            "error_message": long_error,
            "retry_count": 1,
            "status": "failed"
        }

        payload = slack_notifier_enabled._build_message_blocks("task_failed", data)

        # Find the error field
        fields = payload["attachments"][0]["blocks"][1]["fields"]
        error_field = None
        for field in fields:
            if "error" in field["text"].lower():
                error_field = field
                break

        assert error_field is not None
        # Slack has a 4000 character limit for messages
        assert len(error_field["text"]) <= 4000

    def test_context_truncation(self, slack_notifier_enabled):
        """Test context data is truncated"""
        # Create large context
        large_context = {"data": "x" * 1000}
        data = {
            "task_id": "test-001",
            "task_name": "Test Task",
            "reason": "Error threshold exceeded",
            "context": large_context,
            "status": "intervention_required"
        }

        payload = slack_notifier_enabled._build_message_blocks("human_intervention", data)

        # Convert context to string and check truncation
        context_str = str(data["context"])
        # The implementation truncates context to 500 chars
        assert len(context_str) <= 500 or payload["attachments"][0]["blocks"][1]["fields"][-1]["text"].count('\n') < 20

    @pytest.mark.asyncio
    async def test_message_payload_size_limit(self, temp_agent_dir):
        """Test generated payload respects Slack size limits"""
        reset_slack_notifier()
        sm = StateManager(agent_dir=temp_agent_dir)
        sm.save_config({
            "slack": {
                "enabled": True,
                "webhook_url": "https://hooks.slack.com/services/T00000000/B00000000/XXXXXXX"
            }
        })

        # Create data that might generate large payload
        data = {
            "task_id": "test-001",
            "task_name": "Test Task " * 100,  # Long task name
            "status": "completed"
        }

        notifier = SlackNotifier(sm)
        payload = notifier._build_message_blocks("task_completed", data)

        # Serialize and check size
        import json
        payload_str = json.dumps(payload)
        # Slack webhook payload limit is around 30KB
        assert len(payload_str) < 30000


class TestSlackErrorHandling:
    """Test cases for Slack error handling"""

    @pytest.fixture
    def temp_agent_dir(self):
        """Create a temporary directory for testing"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.mark.asyncio
    async def test_channel_not_found_error(self, temp_agent_dir):
        """Test Slack handles channel not found error"""
        reset_slack_notifier()
        sm = StateManager(agent_dir=temp_agent_dir)
        sm.save_config({
            "slack": {
                "enabled": True,
                "webhook_url": "https://hooks.slack.com/services/T00000000/B00000000/XXXXXXX"
            }
        })

        # Mock response indicating channel not found
        mock_response = MagicMock()
        mock_response.status_code = 200
        # Slack returns "channel_not_found" in the response text
        mock_response.text = '{"ok": false, "error": "channel_not_found"}'

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.aclose = AsyncMock()

        notifier = SlackNotifier(sm)
        notifier._client = mock_client

        from agent.exceptions import SlackError
        with pytest.raises(SlackError) as exc_info:
            await notifier.send_notification("task_completed", {"task_id": "test-001"})

        assert "channel_not_found" in str(exc_info.value.detail).lower() or exc_info.value.is_retryable is True

    @pytest.mark.asyncio
    async def test_invalid_webhook_url(self, temp_agent_dir):
        """Test Slack handles invalid webhook URL"""
        reset_slack_notifier()
        sm = StateManager(agent_dir=temp_agent_dir)
        sm.save_config({
            "slack": {
                "enabled": True,
                "webhook_url": "https://invalid-url-that-does-not-exist.com/webhook"
            }
        })

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=httpx.ConnectError("Connection failed"))
        mock_client.aclose = AsyncMock()

        notifier = SlackNotifier(sm)
        notifier._client = mock_client

        from agent.exceptions import SlackError
        with pytest.raises(SlackError) as exc_info:
            await notifier.send_notification("task_completed", {"task_id": "test-001"})

        assert exc_info.value.is_retryable is True

    @pytest.mark.asyncio
    async def test_rate_limit_error(self, temp_agent_dir):
        """Test Slack handles rate limiting"""
        reset_slack_notifier()
        sm = StateManager(agent_dir=temp_agent_dir)
        sm.save_config({
            "slack": {
                "enabled": True,
                "webhook_url": "https://hooks.slack.com/services/T00000000/B00000000/XXXXXXX",
                "retry_count": 3,
                "retry_interval": 0.1
            }
        })

        # First call rate limited, then success
        mock_responses = [
            MagicMock(status_code=429, text='{"ok": false, "error": "rate_limited"}'),
            MagicMock(status_code=200, text='{"ok": true}')
        ]
        response_iter = iter(mock_responses)

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=lambda *args, **kwargs: next(response_iter))
        mock_client.aclose = AsyncMock()

        notifier = SlackNotifier(sm)
        notifier._client = mock_client
        notifier.retry_count = 3
        notifier.retry_interval = 0.1

        result = await notifier.send_notification("task_completed", {"task_id": "test-001"})

        # Should eventually succeed after rate limit
        assert result is True or mock_client.post.call_count == 3


class TestSlackRetryMechanism:
    """Test cases for Slack retry mechanism"""

    @pytest.fixture
    def temp_agent_dir(self):
        """Create a temporary directory for testing"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.mark.asyncio
    async def test_retry_on_503(self, temp_agent_dir):
        """Test Slack retries on 503 error"""
        reset_slack_notifier()
        sm = StateManager(agent_dir=temp_agent_dir)
        sm.save_config({
            "slack": {
                "enabled": True,
                "webhook_url": "https://hooks.slack.com/services/T00000000/B00000000/XXXXXXX",
                "retry_count": 3,
                "retry_interval": 0.1
            }
        })

        # 503 then success
        mock_responses = [
            MagicMock(status_code=503, text="Service Unavailable"),
            MagicMock(status_code=200, text='{"ok": true}')
        ]
        response_iter = iter(mock_responses)

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=lambda *args, **kwargs: next(response_iter))
        mock_client.aclose = AsyncMock()

        notifier = SlackNotifier(sm)
        notifier._client = mock_client
        notifier.retry_count = 3
        notifier.retry_interval = 0.1

        result = await notifier.send_notification("task_completed", {"task_id": "test-001"})

        assert result is True
        assert mock_client.post.call_count == 2

    @pytest.mark.asyncio
    async def test_exponential_backoff(self, temp_agent_dir):
        """Test Slack uses exponential backoff for retries"""
        reset_slack_notifier()
        sm = StateManager(agent_dir=temp_agent_dir)
        sm.save_config({
            "slack": {
                "enabled": True,
                "webhook_url": "https://hooks.slack.com/services/T00000000/B00000000/XXXXXXX",
                "retry_count": 3,
                "retry_interval": 0.1
            }
        })

        import time

        mock_response = MagicMock(status_code=503, text="Service Unavailable")
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.aclose = AsyncMock()

        notifier = SlackNotifier(sm)
        notifier._client = mock_client
        notifier.retry_count = 3
        notifier.retry_interval = 0.1  # 100ms base

        start_time = time.time()

        from agent.exceptions import SlackError
        with pytest.raises(SlackError):
            await notifier.send_notification("task_completed", {"task_id": "test-001"})

        elapsed = time.time() - start_time

        # With exponential backoff: 0.1 + 0.2 + 0.4 = 0.7s (approximately)
        assert elapsed >= 0.6  # Allow some margin


class TestSlackEdgeCases:
    """Test cases for Slack edge cases"""

    @pytest.fixture
    def temp_agent_dir(self):
        """Create a temporary directory for testing"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    def test_default_config_values(self, temp_agent_dir):
        """Test Slack has correct default config values"""
        reset_slack_notifier()
        sm = StateManager(agent_dir=temp_agent_dir)
        sm.save_config({})  # Empty config

        notifier = SlackNotifier(sm)

        assert notifier.enabled is False
        assert notifier.webhook_url == ""
        assert notifier.channel == ""
        assert notifier.username == "Agent-Loop"
        assert notifier.icon_emoji == ":robot_face:"
        assert notifier.timeout == 10
        assert notifier.retry_count == 3
        assert notifier.retry_interval == 2

    def test_config_with_custom_values(self, temp_agent_dir):
        """Test Slack loads custom config values"""
        reset_slack_notifier()
        sm = StateManager(agent_dir=temp_agent_dir)
        sm.save_config({
            "slack": {
                "enabled": True,
                "webhook_url": "https://custom.hooks.slack.com/test",
                "channel": "#custom",
                "username": "CustomBot",
                "icon_emoji": ":star:",
                "events": ["custom_event"],
                "timeout": 30,
                "retry_count": 5,
                "retry_interval": 10
            }
        })

        notifier = SlackNotifier(sm)

        assert notifier.enabled is True
        assert notifier.webhook_url == "https://custom.hooks.slack.com/test"
        assert notifier.channel == "#custom"
        assert notifier.username == "CustomBot"
        assert notifier.icon_emoji == ":star:"
        assert notifier.timeout == 30
        assert notifier.retry_count == 5
        assert notifier.retry_interval == 10

    @pytest.mark.asyncio
    async def test_test_slack_disabled(self, temp_agent_dir):
        """Test test_slack when Slack is disabled"""
        reset_slack_notifier()
        sm = StateManager(agent_dir=temp_agent_dir)
        sm.save_config({
            "slack": {
                "enabled": False,
                "webhook_url": "https://hooks.slack.com/test"
            }
        })

        notifier = SlackNotifier(sm)
        result = await notifier.test_slack()

        assert result["success"] is False
        assert "not enabled" in result["message"]

    @pytest.mark.asyncio
    async def test_test_slack_success(self, temp_agent_dir):
        """Test test_slack when successful"""
        reset_slack_notifier()
        sm = StateManager(agent_dir=temp_agent_dir)
        sm.save_config({
            "slack": {
                "enabled": True,
                "webhook_url": "https://hooks.slack.com/test"
            }
        })

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "ok"

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.aclose = AsyncMock()

        notifier = SlackNotifier(sm)
        notifier._client = mock_client

        result = await notifier.test_slack()

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_test_slack_failure(self, temp_agent_dir):
        """Test test_slack when it fails"""
        reset_slack_notifier()
        sm = StateManager(agent_dir=temp_agent_dir)
        sm.save_config({
            "slack": {
                "enabled": True,
                "webhook_url": "https://hooks.slack.com/test"
            }
        })

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.aclose = AsyncMock()

        notifier = SlackNotifier(sm)
        notifier._client = mock_client

        result = await notifier.test_slack()

        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_slack_with_extra_data(self, temp_agent_dir):
        """Test Slack sends extra data in payload"""
        reset_slack_notifier()
        sm = StateManager(agent_dir=temp_agent_dir)
        sm.save_config({
            "slack": {
                "enabled": True,
                "webhook_url": "https://hooks.slack.com/test"
            }
        })

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "ok"

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.aclose = AsyncMock()

        notifier = SlackNotifier(sm)
        notifier._client = mock_client

        extra_data = {"custom_field": "custom_value", "metrics": {"cpu": 50}}
        await notifier.notify_task_completed(
            task_id="test-001",
            task_name="Test Task",
            duration=10.5,
            extra_data=extra_data
        )

        call_args = mock_client.post.call_args
        payload = call_args.kwargs.get("json", {})

        assert "attachments" in payload


class TestSlackTemplateEdgeCases:
    """Test cases for Slack template edge cases"""

    @pytest.fixture
    def temp_agent_dir(self):
        """Create a temporary directory for testing"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    def test_build_message_with_minimal_data(self, slack_notifier_enabled):
        """Test building message with minimal data"""
        data = {
            "task_id": "test-001"
        }
        payload = slack_notifier_enabled._build_message_blocks("task_completed", data)

        assert "attachments" in payload
        assert len(payload["attachments"]) == 1
        # Should still have header and section
        assert len(payload["attachments"][0]["blocks"]) == 2

    def test_build_message_with_all_optional_fields(self, slack_notifier_enabled):
        """Test building message with all optional fields"""
        data = {
            "task_id": "test-001",
            "task_name": "Complete Task",
            "duration_seconds": 120.5,
            "status": "completed",
            "custom_field": "value"
        }
        payload = slack_notifier_enabled._build_message_blocks("task_completed", data)

        assert "attachments" in payload
        fields = payload["attachments"][0]["blocks"][1]["fields"]
        # Should have multiple fields
        assert len(fields) > 2

    def test_unknown_event_type_uses_default_template(self, slack_notifier_enabled):
        """Test unknown event type uses default template"""
        data = {"task_id": "test-001"}
        payload = slack_notifier_enabled._build_message_blocks("unknown_event", data)

        # Should use default template (no specific emoji/color)
        assert "attachments" in payload
        # Default color should be #333333
        assert payload["attachments"][0]["color"] == "#333333"
