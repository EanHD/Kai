#!/usr/bin/env python3
"""
Diagnostic script to identify which package causes SIGILL on non-AVX CPUs.
Run this on the server to find the problematic package.
"""

import sys
import traceback

def test_package(name):
    """Test importing a single package."""
    try:
        __import__(name)
        print(f"✓ {name}")
        return True
    except Exception as e:
        print(f"✗ {name}: {e}")
        traceback.print_exc()
        return False

def test_module(name):
    """Test importing a module from our codebase."""
    try:
        parts = name.split('.')
        mod = __import__(name)
        for part in parts[1:]:
            mod = getattr(mod, part)
        print(f"✓ {name}")
        return True
    except Exception as e:
        print(f"✗ {name}: {e}")
        traceback.print_exc()
        return False

print("=" * 60)
print("CPU Compatibility Diagnostic")
print("=" * 60)

print("\n📦 Testing C Extension Packages:")
packages = [
    'numpy', 'pyarrow', 'lancedb',
    'multidict', 'yarl', 'frozenlist', 'propcache', 'aiohttp',
    'tiktoken', 'regex', 'zstandard', 'orjson', 'ormsgpack', 'jiter', 'xxhash',
    'greenlet', 'cffi', 'cryptography',
    'lxml', 'primp'
]

failed_packages = []
for pkg in packages:
    if not test_package(pkg):
        failed_packages.append(pkg)
        print(f"\n⚠️  FOUND PROBLEMATIC PACKAGE: {pkg}")
        print("This package likely has AVX-compiled C extensions.")
        sys.exit(1)

print("\n✅ All C extension packages imported successfully!")

print("\n🔍 Testing Kai Source Modules:")
modules = [
    'src',
    'src.cli',
    'src.cli.main',
    'src.core',
    'src.core.orchestrator',
    'src.tools',
    'src.embeddings',
]

for mod in modules:
    if not test_module(mod):
        print(f"\n⚠️  FOUND PROBLEMATIC MODULE: {mod}")
        sys.exit(1)

print("\n✅ All source modules imported successfully!")

print("\n🎯 Running full CLI import:")
try:
    from src.cli.main import main
    print("✓ CLI main function imported")
except Exception as e:
    print(f"✗ Failed to import CLI main: {e}")
    traceback.print_exc()
    sys.exit(1)

print("\n" + "=" * 60)
print("✅ All diagnostics passed!")
print("The crash might be in initialization code.")
print("=" * 60)
