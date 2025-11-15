"""Shared fixtures for integration tests."""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pytest
import yaml

from src.core.providers.ollama_provider import OllamaProvider
from src.core.providers.openrouter_provider import OpenRouterProvider


@pytest.fixture(scope="session")
def test_config():
    """Load test configuration."""
    config_path = Path(__file__).parent / "test_config.yaml"
    with open(config_path) as f:
        return yaml.safe_load(f)


@pytest.fixture
async def ollama_provider(test_config):
    """Create Ollama provider with proper config dict."""
    granite_config = test_config["models"]["granite"]

    model_config = {
        "model_id": "granite",
        "model_name": granite_config["model_name"],
        "provider": "ollama",
        "capabilities": granite_config.get("capabilities", []),
        "context_window": granite_config.get("context_window", 4096),
        "cost_per_1k_input": 0.0,
        "cost_per_1k_output": 0.0,
    }

    provider = OllamaProvider(
        model_config=model_config,
        base_url=granite_config.get("base_url", "http://localhost:11434"),
    )

    yield provider

    # Cleanup
    if hasattr(provider, "client"):
        await provider.client.aclose()


@pytest.fixture
async def openrouter_provider(test_config):
    """Create OpenRouter provider with proper config dict."""
    if "OPENROUTER_API_KEY" not in os.environ:
        pytest.skip("OPENROUTER_API_KEY not set")

    grok_config = test_config["models"]["grok-fast"]

    model_config = {
        "model_id": "grok-fast",
        "model_name": grok_config["model_name"],
        "provider": "openrouter",
        "capabilities": grok_config.get("capabilities", []),
        "context_window": grok_config.get("context_window", 8192),
        "cost_per_1k_input": grok_config.get("cost_per_1k_input", 0.0001),
        "cost_per_1k_output": grok_config.get("cost_per_1k_output", 0.0002),
    }

    provider = OpenRouterProvider(
        model_config=model_config,
        api_key=os.environ["OPENROUTER_API_KEY"],
    )

    yield provider

    # Cleanup
    if hasattr(provider, "client"):
        await provider.client.aclose()


@pytest.fixture(scope="module")
def event_loop_policy():
    """Set event loop policy for async tests."""
    import asyncio

    # Use default policy
    policy = asyncio.get_event_loop_policy()
    return policy
