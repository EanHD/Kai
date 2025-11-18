#!/bin/bash
# Setup locally-trusted HTTPS certificates using mkcert

set -e

echo "🔧 Setting up locally-trusted HTTPS certificates..."

# Check if mkcert is installed
if ! command -v mkcert &> /dev/null; then
    echo "📦 Installing mkcert..."
    
    # Detect OS and install mkcert
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        # Linux
        if command -v apt-get &> /dev/null; then
            sudo apt-get update
            sudo apt-get install -y libnss3-tools
            curl -JLO "https://dl.filippo.io/mkcert/latest?for=linux/amd64"
            chmod +x mkcert-v*-linux-amd64
            sudo mv mkcert-v*-linux-amd64 /usr/local/bin/mkcert
        elif command -v yum &> /dev/null; then
            sudo yum install -y nss-tools
            curl -JLO "https://dl.filippo.io/mkcert/latest?for=linux/amd64"
            chmod +x mkcert-v*-linux-amd64
            sudo mv mkcert-v*-linux-amd64 /usr/local/bin/mkcert
        fi
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        brew install mkcert
    fi
fi

# Install local CA
echo "🔐 Installing local Certificate Authority..."
mkcert -install

# Create certs directory
mkdir -p certs

# Generate certificates for localhost
echo "📝 Generating certificates for localhost..."
cd certs
mkcert localhost 127.0.0.1 ::1

# Rename to expected filenames
mv localhost+2.pem cert.pem
mv localhost+2-key.pem key.pem

# Set proper permissions
chmod 600 key.pem
chmod 644 cert.pem

echo ""
echo "✅ Locally-trusted certificates created!"
echo "📁 Location: certs/"
echo "   - cert.pem (certificate)"
echo "   - key.pem (private key)"
echo ""
echo "🎉 Your browser will now trust https://localhost:9000"
echo ""
echo "Next steps:"
echo "1. Enable HTTPS in config/api.yaml (ssl.enabled: true)"
echo "2. Restart the kai server: python main.py"
echo "3. Visit https://localhost:9000/health - no warnings!"
echo ""

