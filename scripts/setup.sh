#!/bin/bash
# KAI Setup Script - One-command installation

set -e  # Exit on error

echo "🚀 KAI Assistant Setup"
echo "======================"
echo

# Check Python version
echo "📋 Checking Python version..."
PYTHON_VERSION=$(python3 --version 2>&1 | grep -oP '\d+\.\d+' || echo "0.0")
REQUIRED_VERSION="3.11"

if [ "$(printf '%s\n' "$REQUIRED_VERSION" "$PYTHON_VERSION" | sort -V | head -n1)" != "$REQUIRED_VERSION" ]; then
    echo "❌ Python 3.11+ required (found $PYTHON_VERSION)"
    exit 1
fi
echo "✅ Python $PYTHON_VERSION"

# Check for uv package manager
echo
echo "📦 Checking uv package manager..."
if ! command -v uv &> /dev/null; then
    echo "⚙️  Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.cargo/bin:$PATH"
    echo "✅ uv installed"
else
    echo "✅ uv already installed"
fi

# Create virtual environment
echo
echo "🐍 Setting up virtual environment..."
if [ ! -d ".venv" ]; then
    uv venv --python python3.11
    echo "✅ Virtual environment created with Python 3.11"
else
    echo "✅ Virtual environment exists"
fi

# Activate venv
source .venv/bin/activate

# Install dependencies
echo
echo "📚 Installing dependencies..."
uv pip install -e .
echo "✅ Dependencies installed"

# Check for Ollama
echo
echo "🤖 Checking Ollama..."
if command -v ollama &> /dev/null; then
    echo "✅ Ollama installed"
    
    # Check if Ollama is running
    if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
        echo "✅ Ollama service running"
        
        # Pull required model
        echo
        echo "📥 Pulling Granite model..."
        if ollama list | grep -q "granite4:micro-h"; then
            echo "✅ granite4:micro-h already available"
        else
            echo "⚙️  Pulling granite4:micro-h (this may take a few minutes)..."
            ollama pull granite4:micro-h
            echo "✅ Model pulled successfully"
        fi
    else
        echo "⚠️  Ollama installed but not running"
        echo "   Start with: ollama serve"
    fi
else
    echo "❌ Ollama not found"
    echo "   Install from: https://ollama.ai"
    echo "   Then run: ollama pull granite4:micro-h"
fi

# Setup environment file
echo
echo "🔧 Setting up environment..."
if [ ! -f ".env" ]; then
    if [ -f ".env.template" ]; then
        cp .env.template .env
        echo "✅ Created .env from template"
        echo "⚠️  Please edit .env and add your API keys:"
        echo "   - OPENROUTER_API_KEY (required for external models)"
        echo "   - BRAVE_API_KEY (optional for web search)"
    else
        echo "⚠️  No .env.template found"
    fi
else
    echo "✅ .env already exists"
fi

# Check Docker (for code execution)
echo
echo "🐳 Checking Docker..."
if command -v docker &> /dev/null; then
    if docker ps > /dev/null 2>&1; then
        echo "✅ Docker installed and running"
    else
        echo "⚠️  Docker installed but not running"
        echo "   Start Docker to enable code execution"
    fi
else
    echo "⚠️  Docker not found (optional, needed for code execution)"
    echo "   Install from: https://docs.docker.com/get-docker/"
fi

# Run health check
echo
echo "🏥 Running health check..."
python scripts/health_check.py

echo
echo "======================================"
echo "✅ Setup Complete!"
echo "======================================"
echo
echo "Next steps:"
echo "1. Edit .env and add your API keys"
echo "2. Test CLI: python -m src.cli.main"
echo "3. Start API: ./scripts/start_api"
echo "4. Run tests: ./run_master_tests.sh --quick"
echo
echo "Documentation: README.md"
echo "======================================"
