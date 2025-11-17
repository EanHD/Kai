#!/bin/bash
# Fix Docker permissions for non-root users

echo "🔧 Fixing Docker permissions..."
echo ""

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed"
    echo "Install with: curl -fsSL https://get.docker.com | sh"
    exit 1
fi

# Get current user
CURRENT_USER=$(whoami)

# Check if docker group exists
if ! getent group docker > /dev/null 2>&1; then
    echo "📦 Creating docker group..."
    sudo groupadd docker
fi

# Add user to docker group
echo "👤 Adding $CURRENT_USER to docker group..."
sudo usermod -aG docker $CURRENT_USER

# Change docker socket permissions
if [ -S /var/run/docker.sock ]; then
    echo "🔐 Setting docker socket permissions..."
    sudo chmod 666 /var/run/docker.sock
fi

echo ""
echo "✅ Docker permissions fixed!"
echo ""
echo "⚠️  IMPORTANT: You need to log out and log back in for group changes to take effect."
echo ""
echo "Or run this to apply immediately in current shell:"
echo "  newgrp docker"
echo ""
echo "Then test with:"
echo "  docker ps"
echo ""
