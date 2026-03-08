# Deployment Guide

Production deployment guide for Agent-Loop.

## Deployment Options

1. **Docker Compose** (Recommended) - Full stack with monitoring
2. **Docker** - Single container
3. **Systemd** - Direct process management
4. **Python Package** - pip installation

---

## Docker Compose Deployment

### Prerequisites

- Docker 20.10+
- Docker Compose 2.0+
- At least 2GB RAM

### Quick Start

```bash
# 1. Clone repository
git clone https://github.com/oGYCo/agent-loop.git
cd agent-loop

# 2. Copy environment template
cp .env.example .env

# 3. Edit configuration
nano .env

# 4. Start all services
docker-compose up -d

# 5. Verify services
docker-compose ps
```

### Environment Configuration

```bash
# .env file
ANTHROPIC_AUTH_TOKEN=your-api-token
ANTHROPIC_BASE_URL=https://api.minimaxi.com/anthropic

# Optional: Logging
LOG_LEVEL=INFO

# Optional: API Keys (comma-separated)
API_KEYS=key1,key2,key3

# Optional: Grafana
GRAFANA_USER=admin
GRAFANA_PASSWORD=admin
```

### Services

| Service | Port | Description |
|---------|------|-------------|
| agent-api | 8000 | REST API + Web Dashboard |
| prometheus | 9090 | Metrics collection |
| grafana | 3000 | Visualization dashboard |

### Accessing Services

- **API Dashboard**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **Prometheus**: http://localhost:9090
- **Grafana**: http://localhost:3000 (admin/admin)

### Common Commands

```bash
# Start services
docker-compose up -d

# Stop services
docker-compose down

# View logs
docker-compose logs -f

# Restart service
docker-compose restart agent-api

# Scale agent-loop instances
docker-compose up -d --scale agent-loop=2
```

### Data Persistence

- `.agent/` directory is mounted as volume
- Logs stored in `./logs/`
- Prometheus data in `./prometheus/`

---

## Single Container Deployment

### Build Image

```bash
docker build -t agent-loop .
```

### Run Container

```bash
docker run -d \
  --name agent-loop \
  -p 8000:8000 \
  -v $(pwd)/.agent:/app/.agent \
  -v $(pwd)/logs:/app/logs \
  --env-file .env \
  agent-loop
```

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `ANTHROPIC_AUTH_TOKEN` | API token | Yes |
| `ANTHROPIC_BASE_URL` | API endpoint | No |
| `LOG_LEVEL` | Logging level | No |
| `PORT` | API server port | No (default: 8000) |

---

## Systemd Deployment

### Create Service File

```bash
# /etc/systemd/system/agent-loop.service
[Unit]
Description=Agent-Loop AI Agent
After=network.target

[Service]
Type=simple
User=agent
Group=agent
WorkingDirectory=/opt/agent-loop
Environment="PATH=/opt/agent-loop/.venv/bin"
Environment="ANTHROPIC_AUTH_TOKEN=your-token"
ExecStart=/opt/agent-loop/.venv/bin/python main.py run
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### Install and Start

```bash
# Copy files
sudo cp -r agent-loop /opt/
sudo useradd -r -s /bin/false agent

# Set permissions
sudo chown -R agent:agent /opt/agent-loop

# Enable and start
sudo systemctl daemon-reload
sudo systemctl enable agent-loop
sudo systemctl start agent-loop

# Check status
sudo systemctl status agent-loop
```

---

## Reverse Proxy Configuration

### Nginx

```nginx
# /etc/nginx/sites-available/agent-loop
server {
    listen 80;
    server_name agent.example.com;

    location / {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }

    location /ws {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

### Caddy

```
agent.example.com {
    reverse_proxy localhost:8000
}
```

---

## Production Checklist

### Security

- [ ] Use API keys for authentication
- [ ] Enable HTTPS
- [ ] Configure CORS properly
- [ ] Set up rate limiting
- [ ] Use secrets management

### Monitoring

- [ ] Configure Prometheus metrics
- [ ] Set up Grafana dashboard
- [ ] Configure log rotation
- [ ] Set up alerts

### Backup

- [ ] Backup `.agent/` directory
- [ ] Backup configuration files
- [ ] Backup logs

### Performance

- [ ] Tune resource limits
- [ ] Configure appropriate timeouts
- [ ] Monitor memory usage

---

## Docker Compose Production Example

```yaml
# docker-compose.prod.yml
version: '3.8'

services:
  agent-api:
    build: .
    ports:
      - "8000:8000"
    volumes:
      - ./data:/app/.agent
      - ./logs:/app/logs
    env_file:
      - .env.production
    restart: unless-stopped
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 4G
        reservations:
          cpus: '1'
          memory: 2G
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  prometheus:
    image: prom/prometheus:latest
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
      - ./prometheus-data:/prometheus
    restart: unless-stopped

  grafana:
    image: grafana/grafana:latest
    ports:
      - "3000:3000"
    volumes:
      - ./grafana provisioning:/etc/grafana/provisioning
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=${GRAFANA_PASSWORD}
    restart: unless-stopped
```

---

## Troubleshooting

### Container exits immediately

```bash
# Check logs
docker-compose logs agent-api

# Common issues:
# - Missing environment variables
# - Invalid API credentials
# - Port already in use
```

### High memory usage

```bash
# Check container stats
docker stats

# Limit memory in docker-compose.yml
deploy:
  resources:
    limits:
      memory: 2G
```

### Can't connect to API

```bash
# Check if container is running
docker-compose ps

# Check firewall
sudo ufw status
```
