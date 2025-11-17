#!/bin/bash
# Setup script for systems without AVX support (e.g., Pentium G3258)
# Uses older compatible package versions instead of building from source

set -e

echo "🔧 Setting up Kai for non-AVX CPU..."
echo ""

# Get project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

# Check Python 3.11 is available
if ! command -v python3.11 &> /dev/null; then
    echo "❌ Error: python3.11 not found"
    echo "Install with: sudo apt install python3.11 python3.11-venv"
    exit 1
fi

echo "✓ Found Python 3.11: $(python3.11 --version)"

# Remove existing venv
if [ -d ".venv" ]; then
    echo "🗑️  Removing existing virtual environment..."
    rm -rf .venv
fi

# Create fresh venv with system Python
echo "📦 Creating virtual environment..."
python3.11 -m venv .venv
source .venv/bin/activate

# Upgrade pip and install build tools
echo "⬆️  Upgrading pip and setuptools..."
pip install --upgrade pip setuptools wheel

# Install older numpy without AVX requirements
echo "🔢 Installing numpy 1.24.4 (compatible with non-AVX CPUs)..."
pip install 'numpy<2.0'

# Install older pyarrow that works without AVX
echo "📦 Installing pyarrow 14.0.1 (compatible with non-AVX CPUs)..."
pip install 'pyarrow==14.0.1'

# Install lancedb with specific version constraints
echo "📚 Installing lancedb with compatible dependencies..."
pip install 'lancedb>=0.3.0,<0.15.0'

# Install remaining dependencies WITHOUT the uvloop package (has AVX)
echo "📦 Installing Kai dependencies (excluding AVX-dependent packages)..."

# Temporarily modify pyproject.toml to exclude uvicorn[standard]
sed -i 's/uvicorn\[standard\]/uvicorn/g' pyproject.toml

# Install Kai
pip install -e .

# Restore pyproject.toml
git checkout pyproject.toml 2>/dev/null || true

echo ""
echo "⚠️  NOTE: uvloop is NOT installed (requires AVX)"
echo "   Uvicorn will use asyncio instead (slightly slower but compatible)"

echo ""
echo "✅ Setup complete!"
echo ""
echo "🎯 Your Kai installation is now compatible with CPUs without AVX support"
echo ""
echo "Run Kai with: ./kai"
echo ""
