#!/bin/bash
# Cloudflare Tunnel Setup Script for Custom Domains
# Helps configure a persistent tunnel for e.g. api.eanhd.com

set -e

echo "🌐 Cloudflare Tunnel Setup"
echo "--------------------------------"

# 1. Check cloudflared
if ! command -v cloudflared &> /dev/null; then
    echo "❌ cloudflared not found. Please run ./install.sh first."
    exit 1
fi

# 2. Login
echo "🔑 Checking authentication..."
if [ ! -f ~/.cloudflared/cert.pem ]; then
    echo "⚠️  Not logged in. Opening browser to login..."
    cloudflared tunnel login
else
    echo "✅ Already logged in."
fi

# 3. Create Tunnel
TUNNEL_NAME="kai-tunnel"
echo "--------------------------------"
read -p "Enter tunnel name [default: $TUNNEL_NAME]: " INPUT_NAME
TUNNEL_NAME=${INPUT_NAME:-$TUNNEL_NAME}

# Check if tunnel exists
if cloudflared tunnel list | grep -q "$TUNNEL_NAME"; then
    echo "✅ Tunnel '$TUNNEL_NAME' already exists."
else
    echo "Mw Creating tunnel '$TUNNEL_NAME'..."
    cloudflared tunnel create "$TUNNEL_NAME"
fi

# Get Tunnel ID
TUNNEL_ID=$(cloudflared tunnel list | grep "$TUNNEL_NAME" | awk '{print $1}')
echo "🆔 Tunnel ID: $TUNNEL_ID"

# 4. Configure
echo "--------------------------------"
echo "📝 Generating config.yml..."
mkdir -p ~/.cloudflared

cat > ~/.cloudflared/config.yml <<EOF
tunnel: $TUNNEL_ID
credentials-file: /home/$USER/.cloudflared/$TUNNEL_ID.json

ingress:
  - hostname: HOSTNAME_PLACEHOLDER
    service: http://localhost:9000
  - service: http_status:404
EOF

echo "✅ Config created at ~/.cloudflared/config.yml"

# 5. Route DNS
echo "--------------------------------"
read -p "Enter the full hostname to route (e.g. api.eanhd.com): " HOSTNAME

if [ -z "$HOSTNAME" ]; then
    echo "❌ Hostname required."
    exit 1
fi

# Update config with real hostname
sed -i "s/HOSTNAME_PLACEHOLDER/$HOSTNAME/" ~/.cloudflared/config.yml

echo "Mw Routing DNS for $HOSTNAME..."
cloudflared tunnel route dns "$TUNNEL_NAME" "$HOSTNAME"

echo "--------------------------------"
echo "✅ Setup Complete!"
echo ""
echo "To run the tunnel:"
echo "  cloudflared tunnel run $TUNNEL_NAME"
echo ""
echo "Or use ./prod.sh which will detect this configuration."
