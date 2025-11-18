# Example GitHub Actions Workflows for Kai with HTTPS

## Example 1: Testing with Self-Signed Certificate

```yaml
name: Test Kai API (Self-Signed HTTPS)

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    
    steps:
      - name: Checkout code
        uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
      
      - name: Generate SSL certificate
        run: |
          ./scripts/generate_ssl_cert.sh
      
      - name: Start Kai API server
        run: |
          # Enable HTTPS in config
          sed -i 's/enabled: false/enabled: true/' config/api.yaml
          
          # Start server in background
          python main.py &
          
          # Wait for server to start
          sleep 10
        
      - name: Test HTTPS endpoint
        run: |
          # Test health endpoint (skip cert verification for self-signed)
          curl -k https://localhost:9000/v1/health
          
          # Test chat endpoint
          curl -k https://localhost:9000/v1/chat/completions \
            -H "Content-Type: application/json" \
            -d '{
              "model": "gpt-3.5-turbo",
              "messages": [{"role": "user", "content": "Hello"}]
            }'
```

## Example 2: Production Deployment with Let's Encrypt

```yaml
name: Deploy Kai API (Production HTTPS)

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    
    steps:
      - name: Checkout code
        uses: actions/checkout@v3
      
      - name: Set up SSL certificates from secrets
        run: |
          mkdir -p certs
          echo "${{ secrets.SSL_CERTIFICATE }}" > certs/cert.pem
          echo "${{ secrets.SSL_PRIVATE_KEY }}" > certs/key.pem
          chmod 600 certs/key.pem
      
      - name: Configure HTTPS
        run: |
          sed -i 's/enabled: false/enabled: true/' config/api.yaml
      
      - name: Deploy to server
        run: |
          # Your deployment commands here
          # Example: scp files to server, restart service, etc.
```

## Example 3: Docker Deployment with HTTPS

```yaml
name: Deploy Kai API (Docker + HTTPS)

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    
    steps:
      - name: Checkout code
        uses: actions/checkout@v3
      
      - name: Set up certificates
        run: |
          mkdir -p certs
          echo "${{ secrets.SSL_CERTIFICATE }}" > certs/cert.pem
          echo "${{ secrets.SSL_PRIVATE_KEY }}" > certs/key.pem
          chmod 600 certs/key.pem
      
      - name: Build Docker image
        run: |
          docker build -t kai-api:latest .
      
      - name: Run container with HTTPS
        run: |
          docker run -d \
            -p 9000:9000 \
            -v $(pwd)/certs:/app/certs \
            -v $(pwd)/config:/app/config \
            -e SSL_ENABLED=true \
            kai-api:latest
      
      - name: Test HTTPS endpoint
        run: |
          sleep 10
          curl https://localhost:9000/v1/health
```

## Example 4: Integration Tests with HTTPS

```yaml
name: Integration Tests (HTTPS)

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    
    services:
      kai-api:
        image: kai-api:test
        ports:
          - 9000:9000
        env:
          SSL_ENABLED: true
    
    steps:
      - name: Checkout code
        uses: actions/checkout@v3
      
      - name: Run integration tests
        run: |
          pytest tests/integration/ \
            --api-url=https://localhost:9000 \
            --ssl-verify=false
```

## Example 5: Multi-Environment Deployment

```yaml
name: Multi-Environment Deploy

on:
  push:
    branches: [main, develop]

jobs:
  deploy:
    runs-on: ubuntu-latest
    
    strategy:
      matrix:
        environment: [staging, production]
    
    steps:
      - name: Checkout code
        uses: actions/checkout@v3
      
      - name: Configure environment
        run: |
          if [ "${{ matrix.environment }}" == "production" ]; then
            echo "Using production certificates"
            echo "${{ secrets.PROD_SSL_CERT }}" > certs/cert.pem
            echo "${{ secrets.PROD_SSL_KEY }}" > certs/key.pem
          else
            echo "Using staging certificates"
            echo "${{ secrets.STAGING_SSL_CERT }}" > certs/cert.pem
            echo "${{ secrets.STAGING_SSL_KEY }}" > certs/key.pem
          fi
          chmod 600 certs/key.pem
      
      - name: Deploy
        run: |
          # Environment-specific deployment
          ./deploy.sh ${{ matrix.environment }}
```

## Setting Up GitHub Secrets

To use certificates in GitHub Actions, add them as secrets:

```bash
# Get certificate content
cat certs/cert.pem | base64

# Get private key content
cat certs/key.pem | base64

# Add to GitHub:
# Settings → Secrets and variables → Actions → New repository secret
# Name: SSL_CERTIFICATE, Value: <base64 cert content>
# Name: SSL_PRIVATE_KEY, Value: <base64 key content>
```

Then in workflow:
```yaml
- name: Restore certificates
  run: |
    mkdir -p certs
    echo "${{ secrets.SSL_CERTIFICATE }}" | base64 -d > certs/cert.pem
    echo "${{ secrets.SSL_PRIVATE_KEY }}" | base64 -d > certs/key.pem
    chmod 600 certs/key.pem
```

## Notes

- For self-signed certificates, use `curl -k` or equivalent to skip verification
- For production, use real certificates from Let's Encrypt or a trusted CA
- Always set proper permissions on private keys: `chmod 600`
- Store certificates as GitHub encrypted secrets, never commit them
- Test HTTPS endpoints after deployment to verify SSL is working
