#!/bin/bash
# Generate self-signed SSL certificate for development/testing
# For production, use certificates from a trusted CA like Let's Encrypt

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}Generating self-signed SSL certificate for Kai API server${NC}"
echo ""

# Create certs directory if it doesn't exist
CERTS_DIR="certs"
if [ ! -d "$CERTS_DIR" ]; then
    mkdir -p "$CERTS_DIR"
    echo -e "${GREEN}✓${NC} Created certs directory"
fi

# Generate private key and certificate
openssl req -x509 -newkey rsa:4096 -nodes \
    -out "$CERTS_DIR/cert.pem" \
    -keyout "$CERTS_DIR/key.pem" \
    -days 365 \
    -subj "/C=US/ST=State/L=City/O=Organization/CN=localhost"

echo ""
echo -e "${GREEN}✓${NC} Certificate generated successfully!"
echo ""
echo "Files created:"
echo "  - $CERTS_DIR/cert.pem (certificate)"
echo "  - $CERTS_DIR/key.pem (private key)"
echo ""
echo "To enable HTTPS:"
echo "  1. Edit config/api.yaml"
echo "  2. Set server.ssl.enabled: true"
echo "  3. Restart the API server"
echo ""
echo -e "${YELLOW}⚠️  This is a self-signed certificate for development only!${NC}"
echo "   For production, use a certificate from a trusted CA (e.g., Let's Encrypt)"
echo ""
