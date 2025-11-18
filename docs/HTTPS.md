# HTTPS/SSL Configuration

This guide explains how to enable HTTPS for the Kai API server to securely communicate with external services like GitHub Actions.

## Overview

The Kai API server supports both HTTP and HTTPS protocols. HTTPS is essential when:
- Communicating with GitHub Actions or other CI/CD systems
- Exposing the API to external networks
- Meeting security compliance requirements
- Protecting sensitive data in transit

## Quick Start

### 1. Generate SSL Certificate

For development and testing:

```bash
./scripts/generate_ssl_cert.sh
```

This creates a self-signed certificate in the `certs/` directory:
- `certs/cert.pem` - SSL certificate
- `certs/key.pem` - Private key

### 2. Enable HTTPS

Edit `config/api.yaml`:

```yaml
server:
  ssl:
    enabled: true  # Enable HTTPS
    certfile: "certs/cert.pem"
    keyfile: "certs/key.pem"
```

### 3. Start the Server

```bash
python main.py
```

The server will start with HTTPS on port 9000. You'll see:
```
🔒 HTTPS enabled with certificate: certs/cert.pem
```

## Production Deployment

### Using Let's Encrypt (Recommended)

For production, use certificates from a trusted Certificate Authority like Let's Encrypt:

```bash
# Install certbot
sudo apt-get install certbot

# Generate certificate
sudo certbot certonly --standalone -d your-domain.com

# Update config/api.yaml
server:
  ssl:
    enabled: true
    certfile: "/etc/letsencrypt/live/your-domain.com/fullchain.pem"
    keyfile: "/etc/letsencrypt/live/your-domain.com/privkey.pem"
```

### Using Custom CA Certificate

If you have a certificate from a corporate CA:

```yaml
server:
  ssl:
    enabled: true
    certfile: "path/to/cert.pem"
    keyfile: "path/to/key.pem"
    ca_certs: "path/to/ca-bundle.pem"  # Optional CA bundle
```

## GitHub Actions Integration

When using Kai with GitHub Actions workflows:

### 1. Self-Signed Certificates

If using self-signed certificates in testing:

```yaml
# .github/workflows/test.yml
- name: Test Kai API
  run: |
    # Disable SSL verification for self-signed certs (testing only)
    curl -k https://localhost:9000/v1/health
  env:
    REQUESTS_CA_BUNDLE: ""
```

### 2. Trusted Certificates

For production with trusted certificates:

```yaml
# .github/workflows/deploy.yml
- name: Deploy with Kai
  run: |
    curl https://your-domain.com:9000/v1/health
```

### 3. Certificate in GitHub Secrets

Store certificates as GitHub secrets for CI/CD:

```bash
# Add certificate to GitHub secrets
gh secret set KAI_SSL_CERT < certs/cert.pem
gh secret set KAI_SSL_KEY < certs/key.pem
```

Then in your workflow:

```yaml
- name: Setup SSL
  run: |
    echo "${{ secrets.KAI_SSL_CERT }}" > certs/cert.pem
    echo "${{ secrets.KAI_SSL_KEY }}" > certs/key.pem
    chmod 600 certs/key.pem
```

## Configuration Reference

### SSL Settings

```yaml
server:
  ssl:
    enabled: false        # Enable HTTPS (default: false)
    certfile: null        # Path to SSL certificate
    keyfile: null         # Path to SSL private key
    ca_certs: null        # Optional: CA certificate bundle
```

### Port Configuration

HTTPS typically uses port 443, but you can use any port:

```yaml
server:
  port: 443              # Standard HTTPS port (requires root/sudo)
  # OR
  port: 9000             # Custom port (no special privileges)
```

**Note**: Ports below 1024 require root privileges on Linux. For non-root deployments, use ports 9000+ or use a reverse proxy.

## Reverse Proxy Setup

For production, use a reverse proxy like Nginx or Traefik to handle SSL termination:

### Nginx Example

```nginx
server {
    listen 443 ssl;
    server_name your-domain.com;

    ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;

    location / {
        proxy_pass http://localhost:9000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Then keep Kai on HTTP:
```yaml
server:
  ssl:
    enabled: false  # Nginx handles SSL
```

## Testing HTTPS

### Test Health Endpoint

```bash
# HTTP (default)
curl http://localhost:9000/v1/health

# HTTPS
curl https://localhost:9000/v1/health

# Self-signed cert (skip verification)
curl -k https://localhost:9000/v1/health
```

### Test Chat Completion

```bash
curl -k https://localhost:9000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-3.5-turbo",
    "messages": [{"role": "user", "content": "Hello"}]
  }'
```

## Troubleshooting

### Certificate Not Found

```
⚠️  SSL enabled but certfile/keyfile not configured - falling back to HTTP
```

**Solution**: Verify certificate paths in `config/api.yaml` are correct and files exist.

### Permission Denied

```
Error: [Errno 13] Permission denied: 'certs/key.pem'
```

**Solution**: Ensure key file has correct permissions:
```bash
chmod 600 certs/key.pem
```

### Port Already in Use

```
Error: [Errno 98] Address already in use
```

**Solution**: Change port in `config/api.yaml` or stop conflicting service.

### SSL Handshake Failed

```
SSL: CERTIFICATE_VERIFY_FAILED
```

**Solutions**:
- For development: Use `-k` flag with curl to skip verification
- For production: Use certificate from trusted CA (Let's Encrypt)
- Add CA certificate to system trust store

### GitHub Actions Connection Failed

**Self-signed certificate issues**:
```yaml
- name: Test API
  run: curl -k https://localhost:9000/v1/health
```

**Or disable SSL verification in Python**:
```python
import requests
requests.get('https://localhost:9000/v1/health', verify=False)
```

## Security Best Practices

1. **Never commit private keys** - Add `certs/` to `.gitignore`
2. **Use strong keys** - Minimum 2048-bit RSA (4096-bit recommended)
3. **Rotate certificates** - Replace before expiration
4. **Restrict key permissions** - `chmod 600` on private keys
5. **Use trusted CAs in production** - Avoid self-signed certs
6. **Enable HTTPS-only** - Redirect HTTP to HTTPS in production
7. **Keep certificates updated** - Automate renewal with certbot

## See Also

- [API Reference](api.md) - API endpoints and usage
- [Configuration](CONFIGURATION.md) - Full configuration options
- [Deployment](deployment.md) - Production deployment guide
- [Troubleshooting](troubleshooting.md) - Common issues
