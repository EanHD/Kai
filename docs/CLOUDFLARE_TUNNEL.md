# Expose Kai API via Cloudflare Tunnel

## Problem
- GitHub Pages (HTTPS) cannot call localhost backend (mixed content blocked)
- Need public HTTPS endpoint for kai API
- Don't want to open firewall ports

## Solution: Cloudflare Tunnel
Free, secure tunnel with automatic HTTPS certificate.

## Setup (5 minutes)

### 1. Install cloudflared
```bash
# On your eanserver
curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb -o cloudflared.deb
sudo dpkg -i cloudflared.deb
```

### 2. Login to Cloudflare
```bash
cloudflared tunnel login
# Opens browser, select your domain
```

### 3. Create Tunnel
```bash
# Create tunnel named 'kai-api'
cloudflared tunnel create kai-api

# Note the tunnel ID shown
```

### 4. Configure Tunnel
Create `~/.cloudflared/config.yml`:
```yaml
tunnel: <YOUR-TUNNEL-ID>
credentials-file: /home/eanhd/.cloudflared/<YOUR-TUNNEL-ID>.json

ingress:
  - hostname: kai-api.yourdomain.com
    service: http://localhost:9000
  - service: http_status:404
```

### 5. Create DNS Record
```bash
cloudflared tunnel route dns kai-api kai-api.yourdomain.com
```

### 6. Run Tunnel
```bash
# Test
cloudflared tunnel run kai-api

# Or install as service
sudo cloudflared service install
sudo systemctl start cloudflared
sudo systemctl enable cloudflared
```

### 7. Update kai config
In `config/api.yaml`:
```yaml
server:
  host: "127.0.0.1"  # Only listen locally
  port: 9000
  ssl:
    enabled: false  # Cloudflare handles HTTPS
```

### 8. Update llmchat frontend
Change API endpoint to:
```javascript
const API_BASE_URL = 'https://kai-api.yourdomain.com';
```

## Alternative: ngrok (Even Easier, but Rate Limited)

### Quick Setup
```bash
# Install ngrok
curl -s https://ngrok-agent.s3.amazonaws.com/ngrok.asc | \
  sudo tee /etc/apt/trusted.gpg.d/ngrok.asc >/dev/null && \
  echo "deb https://ngrok-agent.s3.amazonaws.com buster main" | \
  sudo tee /etc/apt/sources.list.d/ngrok.list && \
  sudo apt update && sudo apt install ngrok

# Sign up at https://ngrok.com and get auth token
ngrok config add-authtoken <YOUR-TOKEN>

# Start tunnel (while kai is running)
ngrok http 9000
```

You'll get a URL like: `https://abc123.ngrok.io`

Update your frontend to use that URL.

**Pros**: 
- 2 minute setup
- Auto HTTPS

**Cons**:
- URL changes each restart (unless paid plan)
- Rate limited on free tier

## Recommended Approach

**For Development**: Use ngrok (super quick)
**For Production**: Use Cloudflare Tunnel (permanent, unlimited, free)

## Testing

After setup:
```bash
# From anywhere
curl https://kai-api.yourdomain.com/health
# Should return: {"status": "healthy"}
```

Your GitHub Pages frontend will now work!
