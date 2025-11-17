# CPU Compatibility Guide

## Overview

Kai is designed to work on a wide range of CPUs, including older processors without AVX/AVX2 support. However, some Python packages (particularly `pyarrow` and `numpy`) ship pre-compiled binaries optimized with AVX instructions that will cause **illegal instruction** crashes on older CPUs.

## Affected CPUs

CPUs **without AVX2 support** will encounter issues with default installation:
- Intel Pentium G3258 (2 cores, Haswell without AVX2)
- Intel Core 2 series
- AMD Phenom series
- Other pre-2013 Intel/AMD processors

**Symptoms:**
```bash
./kai
[1] 10384 illegal hardware instruction (core dumped) ./kai
```

## Solution: Install from Source

### Quick Fix (Recommended)

On the affected system, run our special setup script that builds packages from source without AVX:

```bash
cd /path/to/kai
./scripts/setup_no_avx.sh
```

This will:
1. Remove any existing `.venv`
2. Create a fresh virtual environment with system Python 3.11
3. Build `pyarrow` and `numpy` from source with AVX disabled
4. Install all other dependencies normally

**Note:** Building from source takes 10-20 minutes but only needs to be done once.

### Manual Installation

If you prefer manual control:

```bash
# Install build dependencies (Debian/Ubuntu)
sudo apt install python3.11 python3.11-dev python3.11-venv build-essential cmake

# Create virtual environment
python3.11 -m venv .venv
source .venv/bin/activate

# Upgrade pip and install build tools
pip install --upgrade pip setuptools wheel cmake cython

# Install numpy first
pip install numpy

# Build pyarrow from source without SIMD optimizations
export PYARROW_CMAKE_OPTIONS="-DARROW_SIMD_LEVEL=NONE -DARROW_RUNTIME_SIMD_LEVEL=NONE"
export PYARROW_PARALLEL=4
pip install --no-binary pyarrow pyarrow

# Install remaining dependencies
pip install -e .
```

## Verification

After setup, verify the installation works:

```bash
./kai
# Should start without illegal instruction errors

# Test a simple query
echo "hello, what is 2+2?" | ./kai
# Should respond with "4"
```

## Performance Impact

Building without AVX optimizations has **minimal impact** on Kai's performance because:
- Most computation happens in the LLM (Ollama/external APIs)
- Vector operations in `lancedb` are not CPU-bound in typical usage
- The bottleneck is model inference, not local array operations

Typical performance difference: < 5% slower for RAG searches

## Alternative: Use Pre-built Wheels

If building from source fails, you can use older package versions with broader CPU compatibility:

```bash
pip install pyarrow==10.0.1  # Older version may have broader compatibility
pip install numpy==1.24.0    # Older numpy without AVX requirements
```

**Warning:** Using older versions may have compatibility issues with newer `lancedb`.

## Why This Happens

Modern Python packages like `pyarrow` ship **optimized binary wheels** from PyPI that use:
- **AVX** (Advanced Vector Extensions) - 2008+ Intel CPUs
- **AVX2** (256-bit vectors) - 2013+ Intel CPUs
- **FMA** (Fused Multiply-Add) - 2013+ Intel CPUs

These optimizations make vector operations 2-4x faster on supported CPUs but cause **illegal instruction** crashes on older hardware.

## System Requirements

### Minimum (with setup_no_avx.sh)
- **CPU:** Any x86-64 processor (2005+)
- **RAM:** 2GB (4GB recommended for LLM inference)
- **Storage:** 2GB for dependencies + LLM models

### Recommended
- **CPU:** Intel Core i3 or newer (2013+) with AVX2
- **RAM:** 8GB
- **GPU:** Optional (Ollama can use GPU acceleration)

## Docker Alternative

If you have persistent issues, consider running Kai in Docker which provides a controlled environment:

```bash
docker compose up
```

Docker images use compatible binaries that work across CPU architectures.

## Getting Help

If you continue to have issues:
1. Check CPU capabilities: `cat /proc/cpuinfo | grep flags`
2. Verify Python version: `python3.11 --version`
3. Share error output in GitHub issues

## Related Documentation

- [Installation Guide](../README.md#installation)
- [Troubleshooting](troubleshooting.md)
- [Architecture](ARCHITECTURE.md)
