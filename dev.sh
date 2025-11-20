#!/bin/bash
# Kai Development Launcher
# Starts the API server and Cloudflare Tunnel

set -e

# Trap Ctrl+C to kill background processes
trap "kill 0" EXIT

echo "🚀 Starting Kai (Dev Mode)..."

# 1. Start API Server
echo "Mw Starting API Server..."
uv run main.py &
API_PID=$!

# Wait for API to be ready
echo "⏳ Waiting for API to initialize..."
sleep 5

# 2. Start Cloudflare Tunnel
echo "🌐 Starting Cloudflare Tunnel..."
# Use the share script logic inline or call it
if ! command -v cloudflared &> /dev/null; then
    echo "❌ cloudflared not found. Run ./install.sh"
    exit 1
fi

echo "----------------------------------------------------------------"

if [ -f ~/.cloudflared/config.yml ]; then
    echo "✅ Found existing tunnel configuration."
    echo "🔗 Starting named tunnel (using config.yml)..."
    cloudflared tunnel run &
    TUNNEL_PID=$!
    echo "✅ Tunnel active. Access at your configured domain (e.g. https://api.eanhd.com)"
else
    echo "🔗 Public URL will appear below:"
    cloudflared tunnel --url http://localhost:9000 2>&1 | grep -o 'https://.*\.trycloudflare.com' &
    TUNNEL_PID=$!
fi

# Keep script running
wait
