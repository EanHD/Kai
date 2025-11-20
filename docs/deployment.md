# Deployment Guide

## Development

```bash
# Install dependencies
uv sync

# Run with hot reload
uv run python main.py

# Or with uvicorn directly
uv run uvicorn main:app --reload --port 9000
```

## Production

### Option 1: Uvicorn (Simple)

```bash
# Single worker
uv run uvicorn main:app --host 0.0.0.0 --port 9000

# Multiple workers
uv run uvicorn main:app --host 0.0.0.0 --port 9000 --workers 4
```

### Option 2: Gunicorn with Uvicorn Workers (Recommended)

```bash
uv add gunicorn

uv run gunicorn main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:9000
```

### Option 3: Docker

**Dockerfile**:
```dockerfile
FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY . .

EXPOSE 9000

CMD ["uv", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "9000", "--workers", "4"]
```

**Build and Run**:
```bash
docker build -t kai-api .
docker run -p 9000:9000 kai-api
```

## Cloudflare Tunnel (Custom Domain)

To use your own domain (e.g., `api.eanhd.com`) instead of a random URL:

1. **Run the setup script**:

   ```bash
   ./setup_tunnel.sh
   ```

   Follow the prompts to login to Cloudflare, create a tunnel, and route your DNS.

2. **Start Production**:

   ```bash
   ./prod.sh
   ```

   The script will automatically detect your tunnel configuration and use it.

## Environment Variables

```bash
# Override config values
export KAI_API_PORT=9000
export KAI_API_LOG_LEVEL=INFO
```

## Reverse Proxy (Nginx)

```nginx
server {
    listen 80;
    server_name api.example.com;

    location / {
        proxy_pass http://localhost:9000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        
        # For SSE streaming
        proxy_buffering off;
        proxy_cache off;
        proxy_set_header Connection '';
        proxy_http_version 1.1;
        chunked_transfer_encoding off;
    }
}
```

## Monitoring

- Health endpoint: `GET /health`
- Metrics: Use FastAPI middleware or Prometheus
- Logs: Configure in `config/api.yaml`

## Security

1. Enable authentication: Set `auth.enabled: true` in config
2. Use HTTPS in production
3. Restrict CORS origins
4. Set rate limits
5. Use environment variables for secrets
