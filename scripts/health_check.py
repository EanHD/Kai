#!/usr/bin/env python3
"""Health check script for KAI assistant.

Verifies all services and dependencies are properly configured.
"""

import asyncio
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def check_python_version():
    """Check Python version >= 3.11."""
    import sys

    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 11):
        return False, f"Python 3.11+ required (found {version.major}.{version.minor})"
    return True, f"Python {version.major}.{version.minor}.{version.micro}"


def check_ollama():
    """Check if Ollama is running and has required model."""
    try:
        import httpx

        response = httpx.get("http://localhost:11434/api/tags", timeout=2.0)
        if response.status_code == 200:
            models = response.json().get("models", [])
            has_granite = any("granite" in m.get("name", "") for m in models)
            if has_granite:
                return True, "Ollama running with granite model"
            else:
                return (
                    False,
                    "Ollama running but granite4:micro-h not found. Run: ollama pull granite4:micro-h",
                )
        return False, f"Ollama returned status {response.status_code}"
    except Exception as e:
        return False, f"Ollama not accessible: {e}"


def check_docker():
    """Check if Docker is available."""
    import subprocess

    try:
        result = subprocess.run(["docker", "ps"], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            return True, "Docker running"
        return False, f"Docker not running: {result.stderr}"
    except FileNotFoundError:
        return False, "Docker not installed"
    except Exception as e:
        return False, f"Docker check failed: {e}"


def check_env_vars():
    """Check required environment variables."""
    from dotenv import load_dotenv

    load_dotenv()

    checks = {
        "OPENROUTER_API_KEY": os.getenv("OPENROUTER_API_KEY"),
        "BRAVE_API_KEY": os.getenv("BRAVE_API_KEY"),
    }

    missing = []
    optional_missing = []

    for key, value in checks.items():
        if not value or value == "your-key-here":
            if key == "BRAVE_API_KEY":
                optional_missing.append(key)
            else:
                missing.append(key)

    if missing:
        return False, f"Missing required: {', '.join(missing)}"
    elif optional_missing:
        return True, f"OK (optional missing: {', '.join(optional_missing)})"
    return True, "All API keys configured"


def check_dependencies():
    """Check critical Python dependencies."""
    try:
        import httpx
        import langsmith
        import pydantic
        import yaml

        return True, "Core dependencies installed"
    except ImportError as e:
        return False, f"Missing dependency: {e.name}"


async def check_code_execution():
    """Test code execution tool."""
    try:
        from src.tools.code_exec_wrapper import CodeExecWrapper

        wrapper = CodeExecWrapper({"enabled": True})
        result = await wrapper.execute(
            {
                "language": "python",
                "mode": "task",
                "task": "battery_pack_energy",
                "variables": {
                    "cells_in_series": 13,
                    "cells_in_parallel": 4,
                    "cell_nominal_voltage_v": 3.6,
                    "cell_nominal_capacity_ah": 3.4,
                },
            }
        )

        if "error" in result.data:
            return False, f"Execution failed: {result.data['error']}"

        energy = result.data.get("pack_energy_kwh", 0)
        expected = 0.636
        if abs(energy - expected) < 0.01:
            return True, f"Code execution working ({energy:.3f} kWh)"
        return False, f"Calculation incorrect: got {energy}, expected {expected}"

    except Exception as e:
        return False, f"Code execution error: {e}"


def check_imports():
    """Test critical imports."""
    try:
        from src.api.adapter import APIAdapter
        from src.cli.main import main
        from src.core.orchestrator import Orchestrator
        from src.core.plan_analyzer import PlanAnalyzer
        from src.core.providers.ollama_provider import OllamaProvider
        from src.tools.code_exec_wrapper import CodeExecWrapper

        return True, "All core modules importable"
    except ImportError as e:
        return False, f"Import failed: {e}"


async def main():
    """Run all health checks."""
    print("🏥 KAI Health Check")
    print("=" * 50)
    print()

    checks = [
        ("Python Version", check_python_version),
        ("Dependencies", check_dependencies),
        ("Core Imports", check_imports),
        ("Environment Variables", check_env_vars),
        ("Ollama Service", check_ollama),
        ("Docker", check_docker),
    ]

    # Async checks
    async_checks = [("Code Execution", check_code_execution)]

    results = []
    for name, check_func in checks:
        try:
            success, message = check_func()
            results.append((name, success, message))
            status = "✅" if success else "❌"
            print(f"{status} {name}: {message}")
        except Exception as e:
            results.append((name, False, str(e)))
            print(f"❌ {name}: Error - {e}")

    # Run async checks
    for name, check_func in async_checks:
        try:
            success, message = await check_func()
            results.append((name, success, message))
            status = "✅" if success else "❌"
            print(f"{status} {name}: {message}")
        except Exception as e:
            results.append((name, False, str(e)))
            print(f"❌ {name}: Error - {e}")

    print()
    print("=" * 50)

    # Summary
    passed = sum(1 for _, success, _ in results if success)
    total = len(results)
    critical_failed = any(
        not success
        for name, success, _ in results
        if name in ["Python Version", "Dependencies", "Core Imports", "Ollama Service"]
    )

    if critical_failed:
        print("❌ CRITICAL CHECKS FAILED")
        print("Fix the issues above before using KAI")
        return 1
    elif passed == total:
        print(f"✅ ALL CHECKS PASSED ({passed}/{total})")
        print("KAI is ready to use!")
        return 0
    else:
        print(f"⚠️  SOME CHECKS FAILED ({passed}/{total} passed)")
        print("KAI will work with limited functionality")
        return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
