#!/bin/bash
# Kai Production Launcher
# Starts the API server and Cloudflare Tunnel in the background (detached)

echo "🚀 Starting Kai (Production Mode)..."

# Ensure logs directory exists
mkdir -p logs

# 1. Start API Server
echo "Mw Starting API Server (Background)..."
nohup uv run main.py > logs/api.log 2>&1 &
API_PID=$!
echo "✅ API Server running (PID: $API_PID)"

# Wait for API
sleep 5

# 2. Start Cloudflare Tunnel
echo "🌐 Starting Cloudflare Tunnel (Background)..."

if [ -f ~/.cloudflared/config.yml ]; then
    echo "✅ Found existing tunnel configuration."
    nohup cloudflared tunnel run > logs/tunnel.log 2>&1 &
    TUNNEL_PID=$!
    echo "✅ Named Tunnel running (PID: $TUNNEL_PID)"
    echo "🔗 Custom Domain should be active."
else
    echo "⚠️  No named tunnel config found. Using ad-hoc tunnel..."
    nohup cloudflared tunnel --url http://localhost:9000 > logs/tunnel.log 2>&1 &
    TUNNEL_PID=$!
    echo "✅ Ad-hoc Tunnel running (PID: $TUNNEL_PID)"
    
    echo "----------------------------------------------------------------"
    echo "🔗 Tunnel URL:"
    sleep 5
    grep -o 'https://.*\.trycloudflare.com' logs/tunnel.log | head -1
fi

echo "----------------------------------------------------------------"
echo "📝 Logs: logs/api.log, logs/tunnel.log"
echo "----------------------------------------------------------------"
echo "To stop: kill $API_PID $TUNNEL_PID"
