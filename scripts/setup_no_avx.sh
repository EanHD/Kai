#!/bin/bash
# Setup script for systems without AVX support (e.g., Pentium G3258)
# This script builds pyarrow from source to avoid AVX instructions

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
    echo "Install with: sudo apt install python3.11 python3.11-venv python3.11-dev"
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
echo "⬆️  Upgrading pip and installing build tools..."
pip install --upgrade pip setuptools wheel

# Install cmake and cython needed for building pyarrow
echo "📚 Installing build dependencies..."
pip install cmake cython

# Install numpy first (needed by pyarrow)
echo "🔢 Installing numpy (may take a few minutes)..."
pip install numpy

# Install pyarrow from source WITHOUT AVX
echo "🏗️  Building pyarrow from source (this will take 10-20 minutes)..."
echo "   Note: Building without AVX/AVX2 optimizations for CPU compatibility"

# Set environment variables to disable SIMD optimizations
export PYARROW_CMAKE_OPTIONS="-DARROW_SIMD_LEVEL=NONE -DARROW_RUNTIME_SIMD_LEVEL=NONE"
export PYARROW_PARALLEL=4  # Use 4 cores for building

# Install pyarrow from source
pip install --no-binary pyarrow pyarrow

# Install remaining dependencies normally
echo "📦 Installing remaining dependencies..."
pip install -e .

echo ""
echo "✅ Setup complete!"
echo ""
echo "🎯 Your Kai installation is now compatible with CPUs without AVX support"
echo ""
echo "Run Kai with: ./kai"
echo ""
