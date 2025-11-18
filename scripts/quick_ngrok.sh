#!/bin/bash
# Quick ngrok setup for kai API

echo "🚀 Quick HTTPS Tunnel Setup for Kai API"
echo ""

# Check if ngrok is installed
if ! command -v ngrok &> /dev/null; then
    echo "📦 Installing ngrok..."
    curl -s https://ngrok-agent.s3.amazonaws.com/ngrok.asc | \
      sudo tee /etc/apt/trusted.gpg.d/ngrok.asc >/dev/null && \
      echo "deb https://ngrok-agent.s3.amazonaws.com buster main" | \
      sudo tee /etc/apt/sources.list.d/ngrok.list && \
      sudo apt update && sudo apt install ngrok
    
    echo ""
    echo "⚠️  You need an ngrok auth token:"
    echo "   1. Sign up at https://ngrok.com"
    echo "   2. Get your token from https://dashboard.ngrok.com/get-started/your-authtoken"
    echo "   3. Run: ngrok config add-authtoken <YOUR-TOKEN>"
    echo ""
    exit 1
fi

# Check if kai is running
if ! curl -s http://localhost:9000/health > /dev/null 2>&1; then
    echo "⚠️  Kai API is not running on port 9000"
    echo "   Start it with: cd ~/projects/kai && python main.py"
    echo ""
    exit 1
fi

echo "✅ Kai API is running"
echo "🌐 Starting ngrok tunnel..."
echo ""
echo "Copy the HTTPS URL shown below and use it in your frontend:"
echo ""

ngrok http 9000
