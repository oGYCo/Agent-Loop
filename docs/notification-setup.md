# Notification Setup Guide

Configure Agent-Loop to send notifications via Email, Slack, or Webhooks.

## Notification Events

All notification types support the following events:

| Event | Description |
|-------|-------------|
| `task_completed` | Triggered when a task completes successfully |
| `task_failed` | Triggered when a task fails |
| `human_intervention` | Triggered when human intervention is required |
| `session_started` | Triggered when a new session starts |
| `session_ended` | Triggered when a session ends |

## Email Notifications

### Prerequisites

- SMTP server credentials (Gmail, Outlook, etc.)
- App password if using Gmail (requires 2FA)

### Configuration

Edit `.agent/config.json`:

```json
{
  "email": {
    "enabled": true,
    "smtp_host": "smtp.gmail.com",
    "smtp_port": 587,
    "smtp_user": "your-email@gmail.com",
    "smtp_password": "your-app-password",
    "use_tls": true,
    "from_name": "Agent-Loop",
    "from_email": "agent-loop@yourcompany.com",
    "to_emails": ["admin@yourcompany.com", "team@yourcompany.com"],
    "events": ["task_completed", "task_failed", "human_intervention"],
    "timeout": 30
  }
}
```

### Gmail Setup

1. Enable 2-Factor Authentication on your Google account
2. Go to https://myaccount.google.com/apppasswords
3. Generate an App Password for "Mail"
4. Use the App Password as `smtp_password`

### Testing Email

```bash
# Test via API
curl -X POST http://localhost:8000/api/v1/email/test \
  -H "Content-Type: application/json" \
  -d '{
    "smtp_host": "smtp.gmail.com",
    "smtp_port": 587,
    "smtp_user": "your-email@gmail.com",
    "smtp_password": "your-app-password",
    "to_emails": ["test@example.com"]
  }'

# Or via CLI (if implemented)
uv run python main.py test-email
```

### Email Template

Emails are sent with the following format:

**Subject:** `[Agent-Loop] Task Completed: {task_name}`

**Body:**
```
Agent-Loop Notification

Event: Task Completed
Task: {task_name}
Description: {task_description}
Status: {status}
Time: {timestamp}

View details at: {dashboard_url}
```

---

## Slack Notifications

### Prerequisites

- Slack workspace
- Incoming Webhook URL

### Creating a Slack Webhook

1. Go to https://api.slack.com/messaging/webhooks
2. Select your workspace
3. Create a new Slack app (or use existing)
4. Enable "Incoming Webhooks"
5. Create a new webhook URL
6. Copy the webhook URL

### Configuration

Edit `.agent/config.json`:

```json
{
  "slack": {
    "enabled": true,
    "webhook_url": "https://hooks.slack.com/services/YOUR/WEBHOOK/URL",
    "channel": "#agent-loop",
    "username": "Agent-Loop",
    "icon_emoji": ":robot_face:",
    "events": ["task_completed", "task_failed", "human_intervention"],
    "timeout": 10,
    "retry_count": 3,
    "retry_interval": 2
  }
}
```

### Customizing Appearance

| Option | Description |
|--------|-------------|
| `channel` | Override the default channel from webhook |
| `username` | Custom bot name |
| `icon_emoji` | Emoji icon for the bot |
| `icon_url` | Custom icon URL (optional) |

### Testing Slack

```bash
curl -X POST http://localhost:8000/api/v1/slack/test \
  -H "Content-Type: application/json" \
  -d '{
    "webhook_url": "https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
  }'
```

### Slack Block Kit Messages

Agent-Loop sends rich messages using Slack Block Kit:

```json
{
  "blocks": [
    {
      "type": "header",
      "text": {
        "type": "plain_text",
        "text": "Task Completed :white_check_mark:"
      }
    },
    {
      "type": "section",
      "fields": [
        {"type": "mrkdwn", "text": "*Task:*\nFeature Implementation"},
        {"type": "mrkdwn", "text": "*Status:*\nCompleted"}
      ]
    },
    {
      "type": "context",
      "elements": [
        {"type": "mrkdwn", "text": "Agent-Loop • 2026-03-08 10:30 AM"}
      ]
    }
  ]
}
```

---

## Webhook Notifications

### Prerequisites

- Publicly accessible endpoint URL
- (Optional) Secret for request signing

### Configuration

Edit `.agent/config.json`:

```json
{
  "webhook": {
    "enabled": true,
    "url": "https://your-server.com/webhook",
    "secret": "your-webhook-secret",
    "timeout": 10,
    "events": ["task_completed", "task_failed", "human_intervention"],
    "retry_count": 3,
    "retry_interval": 2
  }
}
```

### Webhook Payload

```json
{
  "event": "task_completed",
  "timestamp": "2026-03-08T10:30:00Z",
  "data": {
    "task_id": "feat-001",
    "task_name": "Implement Feature",
    "task_description": "Description here",
    "status": "completed",
    "duration_seconds": 120,
    "session_id": "sess-abc123"
  }
}
```

### Request Headers

| Header | Description |
|--------|-------------|
| `Content-Type` | `application/json` |
| `X-Agent-Loop-Event` | Event type |
| `X-Agent-Loop-Signature` | HMAC-SHA256 signature (if secret configured) |

### Signature Verification

Verify webhook authenticity using the signature:

```python
import hmac
import hashlib

def verify_signature(payload: bytes, signature: str, secret: str) -> bool:
    expected = hmac.new(
        secret.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)
```

### Testing Webhooks

```bash
curl -X POST http://localhost:8000/api/v1/webhook/test \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://your-server.com/webhook",
    "secret": "your-secret"
  }'
```

---

## Multiple Notification Channels

You can enable multiple notification channels simultaneously:

```json
{
  "email": {
    "enabled": true,
    "events": ["task_completed", "task_failed"]
  },
  "slack": {
    "enabled": true,
    "events": ["task_completed", "task_failed", "human_intervention"]
  },
  "webhook": {
    "enabled": true,
    "url": "https://your-server.com/webhook",
    "events": ["task_completed"]
  }
}
```

---

## Troubleshooting

### Email Issues

- **Connection refused**: Check SMTP host and port
- **Authentication failed**: Verify username/app password
- **TLS errors**: Ensure `use_tls: true` for port 587

### Slack Issues

- **Invalid webhook**: Verify the webhook URL is correct
- **Channel not found**: Bot needs to be invited to the channel
- **Rate limited**: Slack has rate limits for webhooks

### Webhook Issues

- **Connection timeout**: Ensure endpoint is publicly accessible
- **SSL errors**: Use valid HTTPS certificates
- **404 errors**: Verify endpoint path is correct

### Debug Mode

Enable debug logging to troubleshoot:

```bash
export LOG_LEVEL=DEBUG
uv run python main.py run
```
