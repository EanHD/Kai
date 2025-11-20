#!/bin/bash
# Kai Installation & Setup Script
# Sets up the complete environment: Python, uv, Ollama, Cloudflare, and Configs.

set -e

echo "🚀 Starting Kai Setup..."

# 1. Check System Dependencies
echo "📦 Checking dependencies..."

# Check for Python 3.11+
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed."
    exit 1
fi
PY_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
if (( $(echo "$PY_VERSION < 3.11" | bc -l) )); then
    echo "❌ Python 3.11+ required. Found $PY_VERSION"
    exit 1
fi
echo "✅ Python $PY_VERSION found."

# Check/Install uv
if ! command -v uv &> /dev/null; then
    echo "⬇️  Installing uv (Python package manager)..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    source $HOME/.cargo/env
else
    echo "✅ uv found."
fi

# Check/Install Cloudflared
if ! command -v cloudflared &> /dev/null; then
    echo "⬇️  Installing cloudflared..."
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -o cloudflared
        chmod +x cloudflared
        sudo mv cloudflared /usr/local/bin/
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        brew install cloudflared
    fi
else
    echo "✅ cloudflared found."
fi

# Check/Install Ollama
if ! command -v ollama &> /dev/null; then
    echo "⬇️  Installing Ollama..."
    curl -fsSL https://ollama.com/install.sh | sh
else
    echo "✅ Ollama found."
fi

# 2. Setup Project Environment
echo "🛠️  Setting up project environment..."

# Install Python dependencies
echo "📦 Installing Python dependencies with uv..."
uv sync

# 3. Setup Models
echo "🧠 Setting up AI models..."

# Check if Ollama is running
if ! pgrep -x "ollama" > /dev/null; then
    echo "🔄 Starting Ollama server..."
    ollama serve > /dev/null 2>&1 &
    sleep 5
fi

# Pull Granite model (Local)
echo "⬇️  Pulling granite4:micro-h (Local Model)..."
ollama pull granite4:micro-h

# 4. Configuration
echo "⚙️  Checking configuration..."
if [ ! -f .env ]; then
    echo "⚠️  .env file missing. Creating from template..."
    if [ -f .env.example ]; then
        cp .env.example .env
    else
        touch .env
        echo "# Kai Environment Variables" >> .env
        echo "OPENROUTER_API_KEY=" >> .env
        echo "BRAVE_API_KEY=" >> .env
        echo "TAVILY_API_KEY=" >> .env
    fi
    echo "❗ Please edit .env and add your API keys."
fi

echo "✅ Setup Complete! Run './dev.sh' to start the server."
