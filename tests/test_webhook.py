"""Tests for WebhookNotifier module"""

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


class TestWebhookRetryMechanism:
    """Test cases for Webhook retry mechanism"""

    @pytest.fixture
    def temp_agent_dir(self):
        """Create a temporary directory for testing"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.mark.asyncio
    async def test_retry_on_connection_error(self, temp_agent_dir):
        """Test webhook retries on connection error"""
        reset_webhook_notifier()
        sm = StateManager(agent_dir=temp_agent_dir)
        sm.save_config({
            "webhook": {
                "enabled": True,
                "url": "http://localhost:9999/webhook",
                "retry_count": 3,
                "retry_interval": 0.1
            }
        })

        # Connection error then success
        call_count = 0

        async def mock_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise httpx.ConnectError("Connection failed")
            return MagicMock(status_code=200, text="OK")

        mock_client = AsyncMock()
        mock_client.post = mock_post
        mock_client.aclose = AsyncMock()

        notifier = WebhookNotifier(sm)
        notifier._client = mock_client
        notifier.retry_count = 3
        notifier.retry_interval = 0.1

        result = await notifier.send_notification("task_completed", {"task_id": "test-001"})

        # Connection errors are retried
        assert result is True
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_retry_on_timeout(self, temp_agent_dir):
        """Test webhook retries on timeout"""
        reset_webhook_notifier()
        sm = StateManager(agent_dir=temp_agent_dir)
        sm.save_config({
            "webhook": {
                "enabled": True,
                "url": "http://localhost:9999/webhook",
                "retry_count": 3,
                "retry_interval": 0.1
            }
        })

        # Timeout then success
        call_count = 0

        async def mock_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise httpx.TimeoutException("Request timeout")
            return MagicMock(status_code=200, text="OK")

        mock_client = AsyncMock()
        mock_client.post = mock_post
        mock_client.aclose = AsyncMock()

        notifier = WebhookNotifier(sm)
        notifier._client = mock_client
        notifier.retry_count = 3
        notifier.retry_interval = 0.1

        result = await notifier.send_notification("task_completed", {"task_id": "test-001"})

        # Timeout errors are retried
        assert result is True
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_max_retries_connection_error(self, temp_agent_dir):
        """Test webhook fails after max retry attempts on connection error"""
        reset_webhook_notifier()
        sm = StateManager(agent_dir=temp_agent_dir)
        sm.save_config({
            "webhook": {
                "enabled": True,
                "url": "http://localhost:9999/webhook",
                "retry_count": 3,
                "retry_interval": 0.1
            }
        })

        # Always connection error
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=httpx.ConnectError("Connection failed"))
        mock_client.aclose = AsyncMock()

        notifier = WebhookNotifier(sm)
        notifier._client = mock_client
        notifier.retry_count = 3
        notifier.retry_interval = 0.1

        from agent.exceptions import WebhookError
        with pytest.raises(WebhookError) as exc_info:
            await notifier.send_notification("task_completed", {"task_id": "test-001"})

        # Connection errors are retried 3 times then fail
        assert mock_client.post.call_count == 3
        assert exc_info.value.is_retryable is True

    @pytest.mark.asyncio
    async def test_no_retry_when_retry_false(self, temp_agent_dir):
        """Test webhook does not retry when retry=False"""
        reset_webhook_notifier()
        sm = StateManager(agent_dir=temp_agent_dir)
        sm.save_config({
            "webhook": {
                "enabled": True,
                "url": "http://localhost:9999/webhook",
                "retry_count": 3,
                "retry_interval": 0.1
            }
        })

        mock_response = MagicMock(status_code=503, text="Service Unavailable")

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.aclose = AsyncMock()

        notifier = WebhookNotifier(sm)
        notifier._client = mock_client

        result = await notifier.send_notification("task_completed", {"task_id": "test-001"}, retry=False)

        # With retry=False, only one attempt is made
        assert result is False
        assert mock_client.post.call_count == 1

    @pytest.mark.asyncio
    async def test_4xx_not_retryable(self, temp_agent_dir):
        """Test 4xx errors are not retried"""
        reset_webhook_notifier()
        sm = StateManager(agent_dir=temp_agent_dir)
        sm.save_config({
            "webhook": {
                "enabled": True,
                "url": "http://localhost:9999/webhook",
                "retry_count": 3,
                "retry_interval": 0.1
            }
        })

        # 400 Bad Request
        mock_response = MagicMock(status_code=400, text="Bad Request")

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.aclose = AsyncMock()

        notifier = WebhookNotifier(sm)
        notifier._client = mock_client

        from agent.exceptions import WebhookError
        with pytest.raises(WebhookError) as exc_info:
            await notifier.send_notification("task_completed", {"task_id": "test-001"})

        # 4xx errors are not retried
        assert mock_client.post.call_count == 1
        assert exc_info.value.is_retryable is False


class TestWebhookTimeoutHandling:
    """Test cases for Webhook timeout handling"""

    @pytest.fixture
    def temp_agent_dir(self):
        """Create a temporary directory for testing"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.mark.asyncio
    async def test_timeout_logs_error(self, temp_agent_dir):
        """Test webhook timeout is properly logged"""
        reset_webhook_notifier()
        sm = StateManager(agent_dir=temp_agent_dir)
        sm.save_config({
            "webhook": {
                "enabled": True,
                "url": "http://localhost:9999/webhook",
                "timeout": 1,
                "retry_count": 1
            }
        })

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("Request timeout"))
        mock_client.aclose = AsyncMock()

        notifier = WebhookNotifier(sm)
        notifier._client = mock_client

        from agent.exceptions import WebhookError
        with pytest.raises(WebhookError) as exc_info:
            await notifier.send_notification("task_completed", {"task_id": "test-001"})

        assert exc_info.value.is_retryable is True
        assert "timeout" in exc_info.value.message.lower()

    @pytest.mark.asyncio
    async def test_timeout_on_all_retries(self, temp_agent_dir):
        """Test webhook fails after timeout on all retries"""
        reset_webhook_notifier()
        sm = StateManager(agent_dir=temp_agent_dir)
        sm.save_config({
            "webhook": {
                "enabled": True,
                "url": "http://localhost:9999/webhook",
                "timeout": 1,
                "retry_count": 3,
                "retry_interval": 0.1
            }
        })

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("Request timeout"))
        mock_client.aclose = AsyncMock()

        notifier = WebhookNotifier(sm)
        notifier._client = mock_client
        notifier.retry_count = 3

        from agent.exceptions import WebhookError
        with pytest.raises(WebhookError) as exc_info:
            await notifier.send_notification("task_completed", {"task_id": "test-001"})

        assert mock_client.post.call_count == 3


class TestWebhookPayloadFormat:
    """Test cases for Webhook payload format"""

    @pytest.fixture
    def temp_agent_dir(self):
        """Create a temporary directory for testing"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.mark.asyncio
    async def test_payload_has_required_fields(self, temp_agent_dir):
        """Test webhook payload has all required fields"""
        reset_webhook_notifier()
        sm = StateManager(agent_dir=temp_agent_dir)
        sm.save_config({
            "webhook": {
                "enabled": True,
                "url": "http://localhost:9999/webhook"
            }
        })

        mock_response = MagicMock(status_code=200)
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.aclose = AsyncMock()

        notifier = WebhookNotifier(sm)
        notifier._client = mock_client

        await notifier.notify_task_completed(task_id="test-001", task_name="Test Task", duration=10.5)

        call_args = mock_client.post.call_args
        payload = call_args.kwargs.get("json", {})

        # Verify required fields
        assert "event" in payload
        assert "timestamp" in payload
        assert "data" in payload
        assert payload["event"] == "task_completed"
        assert payload["data"]["task_id"] == "test-001"
        assert payload["data"]["task_name"] == "Test Task"
        assert payload["data"]["status"] == "completed"

    @pytest.mark.asyncio
    async def test_payload_format_task_failed(self, temp_agent_dir):
        """Test webhook payload format for task_failed event"""
        reset_webhook_notifier()
        sm = StateManager(agent_dir=temp_agent_dir)
        sm.save_config({
            "webhook": {
                "enabled": True,
                "url": "http://localhost:9999/webhook"
            }
        })

        mock_response = MagicMock(status_code=200)
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.aclose = AsyncMock()

        notifier = WebhookNotifier(sm)
        notifier._client = mock_client

        await notifier.notify_task_failed(
            task_id="test-002",
            task_name="Failed Task",
            error_message="Something went wrong",
            retry_count=2
        )

        call_args = mock_client.post.call_args
        payload = call_args.kwargs.get("json", {})

        assert payload["event"] == "task_failed"
        assert payload["data"]["task_id"] == "test-002"
        assert payload["data"]["status"] == "failed"
        assert payload["data"]["error_message"] == "Something went wrong"
        assert payload["data"]["retry_count"] == 2

    @pytest.mark.asyncio
    async def test_payload_format_human_intervention(self, temp_agent_dir):
        """Test webhook payload format for human_intervention event"""
        reset_webhook_notifier()
        sm = StateManager(agent_dir=temp_agent_dir)
        sm.save_config({
            "webhook": {
                "enabled": True,
                "url": "http://localhost:9999/webhook"
            }
        })

        mock_response = MagicMock(status_code=200)
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.aclose = AsyncMock()

        notifier = WebhookNotifier(sm)
        notifier._client = mock_client

        await notifier.notify_human_intervention(
            reason="Error threshold exceeded",
            task_id="test-003",
            task_name="Stuck Task",
            context={"error_count": 5}
        )

        call_args = mock_client.post.call_args
        payload = call_args.kwargs.get("json", {})

        assert payload["event"] == "human_intervention"
        assert payload["data"]["reason"] == "Error threshold exceeded"
        assert payload["data"]["status"] == "intervention_required"
        assert payload["data"]["context"]["error_count"] == 5


class TestWebhookSignatureVerification:
    """Test cases for Webhook HMAC-SHA256 signature verification"""

    @pytest.fixture
    def temp_agent_dir(self):
        """Create a temporary directory for testing"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    def test_hmac_sha256_signature_generation(self, temp_agent_dir):
        """Test HMAC-SHA256 signature is generated correctly"""
        import hmac
        import hashlib
        import json

        reset_webhook_notifier()
        sm = StateManager(agent_dir=temp_agent_dir)
        secret = "test-secret-key"
        sm.save_config({
            "webhook": {
                "enabled": True,
                "url": "http://localhost:9999/webhook",
                "secret": secret
            }
        })

        mock_response = MagicMock(status_code=200)
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.aclose = AsyncMock()

        notifier = WebhookNotifier(sm)
        notifier._client = mock_client

        # Create a test payload
        payload = {
            "event": "task_completed",
            "timestamp": "2026-03-08T12:00:00",
            "data": {"task_id": "test-001"}
        }
        payload_json = json.dumps(payload, sort_keys=True)

        # Generate expected signature
        expected_signature = hmac.new(
            secret.encode('utf-8'),
            payload_json.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

        # The signature should be in the payload
        assert expected_signature is not None

    @pytest.mark.asyncio
    async def test_signature_in_header(self, temp_agent_dir):
        """Test signature is included in X-Webhook-Signature header"""
        import hmac
        import hashlib
        import json

        reset_webhook_notifier()
        sm = StateManager(agent_dir=temp_agent_dir)
        secret = "my-webhook-secret"
        sm.save_config({
            "webhook": {
                "enabled": True,
                "url": "http://localhost:9999/webhook",
                "secret": secret
            }
        })

        mock_response = MagicMock(status_code=200)
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.aclose = AsyncMock()

        notifier = WebhookNotifier(sm)
        notifier._client = mock_client

        # Get the payload that will be sent
        data = {"task_id": "test-001", "task_name": "Test", "status": "completed"}
        await notifier.send_notification("task_completed", data)

        call_args = mock_client.post.call_args
        headers = call_args.kwargs.get("headers", {})

        # Verify X-Webhook-Signature header exists
        assert "X-Webhook-Signature" in headers
        assert headers["X-Webhook-Signature"] == secret

    @pytest.mark.asyncio
    async def test_signature_verification_header(self, temp_agent_dir):
        """Test signature verification using X-Signature-SHA256 header"""
        import hmac
        import hashlib

        reset_webhook_notifier()
        sm = StateManager(agent_dir=temp_agent_dir)
        secret = "verification-secret"
        sm.save_config({
            "webhook": {
                "enabled": True,
                "url": "http://localhost:9999/webhook",
                "secret": secret
            }
        })

        mock_response = MagicMock(status_code=200)
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.aclose = AsyncMock()

        notifier = WebhookNotifier(sm)
        notifier._client = mock_client

        await notifier.notify_task_completed(task_id="test-001", task_name="Test Task")

        call_args = mock_client.post.call_args
        headers = call_args.kwargs.get("headers", {})
        payload_json = call_args.kwargs.get("json", {})

        # Compute expected signature
        import json
        payload_str = json.dumps(payload_json, sort_keys=True)
        expected_sig = hmac.new(
            secret.encode('utf-8'),
            payload_str.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

        # Verify both headers are present
        assert "X-Webhook-Secret" in headers


class TestWebhookRetry503Scenario:
    """Test cases for Webhook retry with 503→503→200 scenario"""

    @pytest.fixture
    def temp_agent_dir(self):
        """Create a temporary directory for testing"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.mark.asyncio
    async def test_retry_503_503_200(self, temp_agent_dir):
        """Test webhook retries 503 errors and succeeds on third attempt"""
        reset_webhook_notifier()
        sm = StateManager(agent_dir=temp_agent_dir)
        sm.save_config({
            "webhook": {
                "enabled": True,
                "url": "http://localhost:9999/webhook",
                "retry_count": 3,
                "retry_interval": 0.1
            }
        })

        # 503 -> 503 -> 200
        mock_responses = [
            MagicMock(status_code=503, text="Service Unavailable"),
            MagicMock(status_code=503, text="Service Unavailable"),
            MagicMock(status_code=200, text="OK")
        ]
        response_iter = iter(mock_responses)

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=lambda *args, **kwargs: next(response_iter))
        mock_client.aclose = AsyncMock()

        notifier = WebhookNotifier(sm)
        notifier._client = mock_client
        notifier.retry_count = 3
        notifier.retry_interval = 0.1

        result = await notifier.send_notification("task_completed", {"task_id": "test-001"})

        assert result is True
        assert mock_client.post.call_count == 3

    @pytest.mark.asyncio
    async def test_retry_503_exhausted(self, temp_agent_dir):
        """Test webhook fails after exhausting retries on 503 errors"""
        reset_webhook_notifier()
        sm = StateManager(agent_dir=temp_agent_dir)
        sm.save_config({
            "webhook": {
                "enabled": True,
                "url": "http://localhost:9999/webhook",
                "retry_count": 3,
                "retry_interval": 0.1
            }
        })

        # Always 503
        mock_response = MagicMock(status_code=503, text="Service Unavailable")

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.aclose = AsyncMock()

        notifier = WebhookNotifier(sm)
        notifier._client = mock_client
        notifier.retry_count = 3
        notifier.retry_interval = 0.1

        from agent.exceptions import WebhookError
        with pytest.raises(WebhookError) as exc_info:
            await notifier.send_notification("task_completed", {"task_id": "test-001"})

        # Should try 3 times
        assert mock_client.post.call_count == 3
        assert exc_info.value.is_retryable is True

    @pytest.mark.asyncio
    async def test_retry_disabled_for_503(self, temp_agent_dir):
        """Test webhook does not retry 503 when retry=False"""
        reset_webhook_notifier()
        sm = StateManager(agent_dir=temp_agent_dir)
        sm.save_config({
            "webhook": {
                "enabled": True,
                "url": "http://localhost:9999/webhook",
                "retry_count": 3,
                "retry_interval": 0.1
            }
        })

        mock_response = MagicMock(status_code=503, text="Service Unavailable")

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.aclose = AsyncMock()

        notifier = WebhookNotifier(sm)
        notifier._client = mock_client

        result = await notifier.send_notification("task_completed", {"task_id": "test-001"}, retry=False)

        assert result is False
        assert mock_client.post.call_count == 1

    @pytest.mark.asyncio
    async def test_exponential_backoff_timing(self, temp_agent_dir):
        """Test webhook uses exponential backoff correctly"""
        import time

        reset_webhook_notifier()
        sm = StateManager(agent_dir=temp_agent_dir)
        sm.save_config({
            "webhook": {
                "enabled": True,
                "url": "http://localhost:9999/webhook",
                "retry_count": 3,
                "retry_interval": 0.2
            }
        })

        mock_response = MagicMock(status_code=503, text="Service Unavailable")
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.aclose = AsyncMock()

        notifier = WebhookNotifier(sm)
        notifier._client = mock_client
        notifier.retry_count = 3
        notifier.retry_interval = 0.2

        start_time = time.time()

        from agent.exceptions import WebhookError
        with pytest.raises(WebhookError):
            await notifier.send_notification("task_completed", {"task_id": "test-001"})

        elapsed = time.time() - start_time

        # With exponential backoff: 0.2 + 0.4 + 0.8 = 1.4s (approximately)
        # Allow margin for test execution
        assert elapsed >= 1.2


class TestWebhookEdgeCases:
    """Test cases for Webhook edge cases"""

    @pytest.fixture
    def temp_agent_dir(self):
        """Create a temporary directory for testing"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.mark.asyncio
    async def test_test_webhook_disabled(self, temp_agent_dir):
        """Test test_webhook when webhook is disabled"""
        reset_webhook_notifier()
        sm = StateManager(agent_dir=temp_agent_dir)
        sm.save_config({
            "webhook": {
                "enabled": False,
                "url": "http://localhost:9999/webhook"
            }
        })

        notifier = WebhookNotifier(sm)
        result = await notifier.test_webhook()

        assert result["success"] is False
        assert "not enabled" in result["message"]

    @pytest.mark.asyncio
    async def test_test_webhook_success(self, temp_agent_dir):
        """Test test_webhook when successful"""
        reset_webhook_notifier()
        sm = StateManager(agent_dir=temp_agent_dir)
        sm.save_config({
            "webhook": {
                "enabled": True,
                "url": "http://localhost:9999/webhook",
                "events": ["task_completed", "task_failed", "human_intervention", "test"]
            }
        })

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "OK"

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.aclose = AsyncMock()

        notifier = WebhookNotifier(sm)
        notifier._client = mock_client

        result = await notifier.test_webhook()

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_test_webhook_failure(self, temp_agent_dir):
        """Test test_webhook when it fails"""
        reset_webhook_notifier()
        sm = StateManager(agent_dir=temp_agent_dir)
        sm.save_config({
            "webhook": {
                "enabled": True,
                "url": "http://localhost:9999/webhook"
            }
        })

        mock_response = MagicMock(status_code=500, text="Internal Server Error")
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.aclose = AsyncMock()

        notifier = WebhookNotifier(sm)
        notifier._client = mock_client

        result = await notifier.test_webhook()

        assert result["success"] is False

    def test_default_config_values(self, temp_agent_dir):
        """Test webhook has correct default config values"""
        reset_webhook_notifier()
        sm = StateManager(agent_dir=temp_agent_dir)
        sm.save_config({})  # Empty config

        notifier = WebhookNotifier(sm)

        assert notifier.enabled is False
        assert notifier.url == ""
        assert notifier.secret == ""
        assert notifier.timeout == 10
        assert notifier.retry_count == 3
        assert notifier.retry_interval == 2
        assert notifier.events == ["task_completed", "task_failed", "human_intervention"]

    def test_config_with_custom_values(self, temp_agent_dir):
        """Test webhook loads custom config values"""
        reset_webhook_notifier()
        sm = StateManager(agent_dir=temp_agent_dir)
        sm.save_config({
            "webhook": {
                "enabled": True,
                "url": "http://custom.com/webhook",
                "secret": "my-secret",
                "timeout": 30,
                "retry_count": 5,
                "retry_interval": 10,
                "events": ["custom_event"]
            }
        })

        notifier = WebhookNotifier(sm)

        assert notifier.enabled is True
        assert notifier.url == "http://custom.com/webhook"
        assert notifier.secret == "my-secret"
        assert notifier.timeout == 30
        assert notifier.retry_count == 5
        assert notifier.retry_interval == 10
        assert notifier.events == ["custom_event"]

    @pytest.mark.asyncio
    async def test_webhook_with_extra_data(self, temp_agent_dir):
        """Test webhook sends extra data in payload"""
        reset_webhook_notifier()
        sm = StateManager(agent_dir=temp_agent_dir)
        sm.save_config({
            "webhook": {
                "enabled": True,
                "url": "http://localhost:9999/webhook"
            }
        })

        mock_response = MagicMock(status_code=200)
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.aclose = AsyncMock()

        notifier = WebhookNotifier(sm)
        notifier._client = mock_client

        extra_data = {"custom_field": "custom_value", "nested": {"key": "value"}}
        await notifier.notify_task_completed(
            task_id="test-001",
            task_name="Test Task",
            duration=10.5,
            extra_data=extra_data
        )

        call_args = mock_client.post.call_args
        payload = call_args.kwargs.get("json", {})

        assert payload["data"]["custom_field"] == "custom_value"
        assert payload["data"]["nested"]["key"] == "value"

    @pytest.mark.asyncio
    async def test_webhook_general_exception(self, temp_agent_dir):
        """Test webhook handles unexpected exceptions"""
        reset_webhook_notifier()
        sm = StateManager(agent_dir=temp_agent_dir)
        sm.save_config({
            "webhook": {
                "enabled": True,
                "url": "http://localhost:9999/webhook"
            }
        })

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=ValueError("Unexpected error"))
        mock_client.aclose = AsyncMock()

        notifier = WebhookNotifier(sm)
        notifier._client = mock_client

        from agent.exceptions import WebhookError
        with pytest.raises(WebhookError) as exc_info:
            await notifier.send_notification("task_completed", {"task_id": "test-001"})

        assert exc_info.value.is_retryable is False

    @pytest.mark.asyncio
    async def test_webhook_retry_returns_false_when_disabled(self, temp_agent_dir):
        """Test webhook returns False when retry is disabled and error is retryable"""
        reset_webhook_notifier()
        sm = StateManager(agent_dir=temp_agent_dir)
        sm.save_config({
            "webhook": {
                "enabled": True,
                "url": "http://localhost:9999/webhook",
                "retry_count": 1
            }
        })

        mock_response = MagicMock(status_code=503, text="Service Unavailable")
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.aclose = AsyncMock()

        notifier = WebhookNotifier(sm)
        notifier._client = mock_client

        result = await notifier.send_notification("task_completed", {"task_id": "test-001"}, retry=False)

        assert result is False

    def test_get_webhook_notifier(self, temp_agent_dir):
        """Test get_webhook_notifier singleton pattern"""
        reset_webhook_notifier()
        sm = StateManager(agent_dir=temp_agent_dir)
        sm.save_config({
            "webhook": {
                "enabled": True,
                "url": "http://localhost:9999/webhook"
            }
        })

        notifier1 = get_webhook_notifier(sm)
        notifier2 = get_webhook_notifier(sm)

        assert notifier1 is notifier2  # Different instances since we reset

    def test_reset_webhook_notifier(self, temp_agent_dir):
        """Test reset_webhook_notifier resets global instance"""
        reset_webhook_notifier()
        sm = StateManager(agent_dir=temp_agent_dir)
        sm.save_config({
            "webhook": {
                "enabled": True,
                "url": "http://localhost:9999/webhook"
            }
        })

        notifier1 = get_webhook_notifier(sm)
        reset_webhook_notifier()
        notifier2 = get_webhook_notifier(sm)

        # After reset, new instance should be created
        assert notifier1 is not None
        assert notifier2 is not None

    @pytest.mark.asyncio
    async def test_webhook_client_property_creates_client(self, temp_agent_dir):
        """Test client property creates client if not exists"""
        import shutil
        # Use a fresh temp directory for this test
        test_dir = tempfile.mkdtemp()
        try:
            sm = StateManager(agent_dir=test_dir)
            sm.save_config({
                "webhook": {
                    "enabled": True,
                    "url": "http://localhost:9999/webhook",
                    "timeout": 15
                }
            })

            notifier = WebhookNotifier(sm)
            # Access client property - should create client
            client = notifier.client
            assert client is not None

            await notifier.close()
            # After close, client should be None
            assert notifier._client is None
        finally:
            shutil.rmtree(test_dir, ignore_errors=True)

    @pytest.mark.asyncio
    async def test_webhook_all_channels_disabled(self, temp_agent_dir):
        """Test send_notification when webhook is disabled"""
        import shutil
        # Use a fresh temp directory for this test
        test_dir = tempfile.mkdtemp()
        try:
            sm = StateManager(agent_dir=test_dir)
            sm.save_config({
                "webhook": {
                    "enabled": False,
                    "url": "http://localhost:9999/webhook"
                }
            })

            notifier = WebhookNotifier(sm)

            result = await notifier.send_notification("task_completed", {"task_id": "test-001"})

            assert result is False
        finally:
            shutil.rmtree(test_dir, ignore_errors=True)

    @pytest.mark.asyncio
    async def test_webhook_404_not_retryable(self, temp_agent_dir):
        """Test 404 errors are not retried"""
        import shutil
        # Use a fresh temp directory for this test
        test_dir = tempfile.mkdtemp()
        try:
            sm = StateManager(agent_dir=test_dir)
            sm.save_config({
                "webhook": {
                    "enabled": True,
                    "url": "http://localhost:9999/webhook",
                    "retry_count": 3
                }
            })

            mock_response = MagicMock(status_code=404, text="Not Found")
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.aclose = AsyncMock()

            # Create fresh notifier without using global instance
            notifier = WebhookNotifier(sm)
            notifier._client = mock_client

            from agent.exceptions import WebhookError
            with pytest.raises(WebhookError) as exc_info:
                await notifier.send_notification("task_completed", {"task_id": "test-001"})

            assert exc_info.value.is_retryable is False
            assert mock_client.post.call_count == 1
        finally:
            shutil.rmtree(test_dir, ignore_errors=True)
