"""Production tests for offline/online mode switching.

Tests that the system correctly respects offline mode flags and
degrades gracefully when network access is disabled.
"""

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

pytestmark = pytest.mark.production

from src.core.orchestrator import Orchestrator
from src.tools.code_exec_wrapper import CodeExecWrapper
from src.tools.web_search import WebSearchTool


def mock_local_connector():
    """Create a mock local connector for testing."""
    connector = MagicMock()
    connector.generate = AsyncMock(return_value=MagicMock(content="test response"))
    connector.check_health = AsyncMock(return_value=True)
    return connector


@pytest.mark.asyncio
async def test_offline_mode_env_var():
    """Test that KAI_OFFLINE_MODE=true activates offline mode."""
    # Set environment variable
    os.environ["KAI_OFFLINE_MODE"] = "true"

    try:
        # Initialize orchestrator
        orchestrator = Orchestrator(
            local_connector=mock_local_connector(), tools={}, cost_limit=1.0
        )

        # Verify offline mode is active
        assert orchestrator.is_offline_mode(), (
            "Offline mode should be active when KAI_OFFLINE_MODE=true"
        )
    finally:
        # Clean up environment
        del os.environ["KAI_OFFLINE_MODE"]


@pytest.mark.asyncio
async def test_online_mode_env_var():
    """Test that KAI_OFFLINE_MODE=false keeps online mode."""
    # Set environment variable
    os.environ["KAI_OFFLINE_MODE"] = "false"

    try:
        # Initialize orchestrator
        orchestrator = Orchestrator(
            local_connector=mock_local_connector(), tools={}, cost_limit=1.0
        )

        # Verify offline mode is NOT active
        assert not orchestrator.is_offline_mode(), (
            "Online mode should be active when KAI_OFFLINE_MODE=false"
        )
    finally:
        # Clean up environment
        del os.environ["KAI_OFFLINE_MODE"]


@pytest.mark.asyncio
async def test_offline_mode_config_file():
    """Test that offline_mode in config activates offline mode."""
    # Set up tools with offline mode in config
    web_search = WebSearchTool(config={"offline_mode": True})
    tools = {"web_search": web_search}

    # Initialize orchestrator
    orchestrator = Orchestrator(local_connector=mock_local_connector(), tools=tools, cost_limit=1.0)

    # Verify offline mode is active
    assert orchestrator.is_offline_mode(), (
        "Offline mode should be active when config offline_mode=True"
    )


@pytest.mark.asyncio
async def test_web_search_blocked_in_offline_mode():
    """Test that web search returns error in offline mode."""
    # Set up tools with offline mode
    web_search = WebSearchTool(config={"offline_mode": True})

    # Execute search
    result = await web_search.execute({"query": "test query"})

    # Verify search was blocked
    assert result.status.value == "failed", "Web search should fail in offline mode"
    assert "offline" in result.error.lower(), "Error message should mention offline mode"
    assert result.data.get("offline_mode", False), "Result data should indicate offline mode"


@pytest.mark.asyncio
async def test_web_search_allowed_in_online_mode():
    """Test that web search executes normally in online mode."""
    # Set up tools with online mode (offline_mode=False)
    web_search = WebSearchTool(config={"offline_mode": False})

    # Execute search
    result = await web_search.execute({"query": "Python programming"})

    # Verify search attempted (may succeed or fail based on network)
    # We're just checking it wasn't blocked by offline mode
    if result.status.value == "failed":
        # If it failed, should NOT be due to offline mode
        if result.error:
            assert "offline mode" not in result.error.lower(), (
                "Failure should not be due to offline mode when online"
            )


@pytest.mark.asyncio
async def test_code_exec_works_in_offline_mode():
    """Test that code execution still works in offline mode."""
    # Set environment variable for offline mode
    os.environ["KAI_OFFLINE_MODE"] = "true"

    try:
        # Set up code executor (should work offline)
        code_exec = CodeExecWrapper(config={})

        # Execute simple math calculation
        result = await code_exec.execute(
            {
                "language": "python",
                "mode": "task",
                "task": "generic_math",
                "variables": {"expression": "2 + 2"},
            }
        )

        # Verify execution succeeded
        assert result.status.value == "success", "Code execution should work in offline mode"
        # The generic_math task returns stdout, not a parsed result
        assert result.data.get("stdout") is not None, "Should have stdout output"
    finally:
        # Clean up environment
        del os.environ["KAI_OFFLINE_MODE"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
