# Troubleshooting Guide

Solutions to common issues with Agent-Loop.

## Installation Issues

### uv sync fails

**Problem:** `uv sync` fails with dependency errors

**Solution:**
```bash
# Clear uv cache and retry
rm -rf .uv-cache
uv sync --no-cache

# Or update uv
uv self update
```

### Python version not supported

**Problem:** "Python 3.11+ required"

**Solution:**
```bash
# Check Python version
python --version

# Use pyenv or conda to install Python 3.11+
pyenv install 3.11
pyenv local 3.11
```

---

## Configuration Issues

### API token not found

**Problem:** "ANTHROPIC_AUTH_TOKEN is required"

**Solution:**
```bash
# Set environment variable
export ANTHROPIC_AUTH_TOKEN="your-token-here"

# Or create .env file
echo 'ANTHROPIC_AUTH_TOKEN=your-token-here' > .env
```

### Invalid API endpoint

**Problem:** "Failed to connect to API"

**Solution:**
```bash
# Verify base URL
export ANTHROPIC_BASE_URL="https://api.minimaxi.com/anthropic"

# Test connectivity
curl -I $ANTHROPIC_BASE_URL
```

---

## Runtime Issues

### Agent hangs during execution

**Problem:** Agent seems stuck, no output

**Solutions:**
1. Check network connectivity
2. Increase timeout in config
3. Check API rate limits

```bash
# Run with verbose output
uv run python main.py run --verbose
```

### Too many errors

**Problem:** "Human intervention required" after many errors

**Solution:**
Increase the threshold in config:
```json
{
  "max_errors_before_intervention": 10
}
```

### Session fails to resume

**Problem:** Cannot resume from previous session

**Solution:**
```bash
# Check session history
uv run python main.py session list

# Manually reset state
rm .agent/state.json
uv run python main.py init
```

---

## Task Execution Issues

### Task not selected

**Problem:** Tasks exist but aren't being executed

**Solution:**
Ensure tasks have correct status:
```json
{
  "status": "pending",
  "passes": false
}
```

### Verify command fails

**Problem:** Task passes but verify_command fails

**Solution:**
- Check the verify_command in task or config
- Verify the command runs correctly locally

### Context limit exceeded

**Problem:** "Context window limit exceeded"

**Solution:**
```json
{
  "context_window_limit": 50000
}
```

---

## API Server Issues

### Port already in use

**Problem:** "Port 8000 is already in use"

**Solution:**
```bash
# Find and kill the process
lsof -i :8000
kill -9 <PID>

# Or use a different port
uv run python api.py --port 8080
```

### CORS errors

**Problem:** "CORS policy blocked request"

**Solution:**
Configure CORS in config.json:
```json
{
  "cors": {
    "enabled": true,
    "allow_origins": ["http://localhost:3000"]
  }
}
```

### Rate limit exceeded

**Problem:** "Too many requests"

**Solution:**
Wait for rate limit reset or adjust limits:
```json
{
  "rate_limit": {
    "enabled": true,
    "default_limit": "200/minute"
  }
}
```

---

## Notification Issues

### Email not sending

**Problem:** Email notifications not working

**Debug:**
1. Check email configuration is enabled
2. Verify SMTP credentials
3. Test with `POST /api/v1/email/test`

**Common fixes:**
- Use App Password for Gmail
- Check `to_emails` is not empty
- Verify firewall allows outbound SMTP

### Slack webhook fails

**Problem:** Slack notifications not arriving

**Debug:**
1. Verify webhook URL
2. Test with `POST /api/v1/slack/test`
3. Check Slack app permissions

---

## Docker Issues

### Container won't start

**Problem:** Docker container exits immediately

**Debug:**
```bash
# View logs
docker-compose logs agent-loop

# Check environment file
cat .env
```

### Volume permissions

**Problem:** "Permission denied" errors

**Solution:**
```bash
# Fix permissions
chmod -R 755 .
chown -R $(id -u):$(id -g) .agent/
```

---

## Performance Issues

### Slow execution

**Problem:** Agent runs very slowly

**Solutions:**
1. Reduce context_window_limit
2. Reduce number of context_files
3. Use faster model
4. Check network latency

### High memory usage

**Problem:** Memory usage grows over time

**Solutions:**
- Enable session cleanup
- Reduce max iterations
- Restart agent periodically

---

## Data Recovery

### Corrupted config.json

**Problem:** Config file is invalid JSON

**Solution:**
```bash
# Backup corrupted file
cp .agent/config.json .agent/config.json.broken

# Regenerate default config
uv run python main.py init
```

### Lost task data

**Problem:** feature_list.json is corrupted

**Solution:**
Check git history:
```bash
git log --oneline .agent/feature_list.json
git show HEAD:.agent/feature_list.json > .agent/feature_list.json
```

---

## Getting Help

### Enable Debug Logging

```bash
export LOG_LEVEL=DEBUG
uv run python main.py run
```

### Check System Status

```bash
uv run python main.py status
```

### View Recent Logs

```bash
# CLI logs
uv run python main.py logs

# API logs (when using Docker)
docker-compose logs -f agent-api
```

### Report Issues

When reporting an issue, include:
1. Agent-Loop version: `uv run python main.py --version`
2. Python version: `python --version`
3. Full error message
4. Steps to reproduce
5. Config (without secrets)
