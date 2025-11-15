"""Integration tests for Orchestration pipeline."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.core.llm_connector import LLMConnector, LLMResponse
from src.core.orchestrator import Orchestrator
from src.models.conversation import ConversationSession


@pytest.fixture
def mock_local_connector():
    """Create mock local connector (Granite)."""
    connector = AsyncMock(spec=LLMConnector)

    # Mock plan analyzer response (returns JSON plan)
    plan_response = LLMResponse(
        content='{"intent": "test", "complexity": "simple", "safety_level": "normal", "capabilities": [], "steps": [{"id": "finalize", "type": "finalization", "model": "granite", "description": "answer", "input": {}, "depends_on": [], "required": true}]}',
        token_count=100,
        cost=0.001,
        model_used="granite",
        finish_reason="stop",
    )

    # Mock presenter response (returns finalized answer)
    presenter_response = LLMResponse(
        content='{"final_answer": "Test answer from orchestration", "short_summary": "Test", "citations_used": []}',
        token_count=50,
        cost=0.0005,
        model_used="granite",
        finish_reason="stop",
    )

    connector.generate = AsyncMock(side_effect=[plan_response, presenter_response])

    return connector


@pytest.fixture
def mock_conversation():
    """Create mock conversation session."""
    session = MagicMock(spec=ConversationSession)
    session.session_id = "test-session"
    return session


@pytest.fixture
def orchestrator(mock_local_connector):
    """Create orchestrator."""
    return Orchestrator(
        local_connector=mock_local_connector,
        external_connectors={},
        tools={},
    )


@pytest.mark.asyncio
async def test_simple_query_pipeline(orchestrator, mock_conversation):
    """Test that simple query goes through orchestration pipeline."""
    query = "What is 2 + 2?"

    response = await orchestrator.process_query(query, mock_conversation)

    # Verify response
    assert response is not None
    assert response.content == "Test answer from orchestration"


@pytest.mark.asyncio
async def test_error_fallback(mock_local_connector, mock_conversation):
    """Test that errors fall back gracefully."""
    # Make plan analyzer fail
    mock_local_connector.generate = AsyncMock(side_effect=Exception("Test error"))

    orchestrator = Orchestrator(
        local_connector=mock_local_connector,
        external_connectors={},
        tools={},
    )

    response = await orchestrator.process_query("test", mock_conversation)

    # Should get fallback error message (could be from orchestrator or presenter)
    assert response is not None
    assert (
        "issue processing your request" in response.content
        or "issue generating the final answer" in response.content
    )


@pytest.mark.asyncio
async def test_with_tools(mock_local_connector, mock_conversation):
    """Test orchestration with tools configured."""
    # Mock tool
    mock_tool = AsyncMock()
    mock_tool.execute_with_fallback = AsyncMock(
        return_value=MagicMock(
            status=MagicMock(value="success"),
            data={"result": 4},
            error=None,
            execution_time_ms=10,
        )
    )

    orchestrator = Orchestrator(
        local_connector=mock_local_connector,
        external_connectors={},
        tools={"code_exec": mock_tool},
    )

    response = await orchestrator.process_query("Calculate 2+2", mock_conversation)

    # Should complete successfully
    assert response is not None


def test_orchestrator_initialization_components(mock_local_connector):
    """Test that orchestration components are initialized."""
    orchestrator = Orchestrator(
        local_connector=mock_local_connector,
        external_connectors={},
        tools={},
    )

    # Verify all components exist
    assert hasattr(orchestrator, "plan_analyzer")
    assert hasattr(orchestrator, "specialist_verifier")
    assert hasattr(orchestrator, "plan_executor")
    assert hasattr(orchestrator, "presenter")


def test_specialist_connector_routing():
    """Test that specialist connectors are correctly identified."""
    mock_local = AsyncMock(spec=LLMConnector)
    mock_grok = AsyncMock(spec=LLMConnector)
    mock_claude = AsyncMock(spec=LLMConnector)

    orchestrator = Orchestrator(
        local_connector=mock_local,
        external_connectors={
            "grok-beta": mock_grok,
            "claude-sonnet-4": mock_claude,
        },
        tools={},
    )

    # Verify specialist verifier got correct connectors
    assert orchestrator.specialist_verifier.fast_connector is mock_grok
    assert orchestrator.specialist_verifier.strong_connector is mock_claude


@pytest.mark.asyncio
async def test_logging(orchestrator, mock_conversation, caplog):
    """Test that orchestration logs key events."""
    import logging

    caplog.set_level(logging.INFO)

    await orchestrator.process_query("test query", mock_conversation)

    # Check for key log messages
    log_text = caplog.text
    assert "Processing query" in log_text
    assert "Plan:" in log_text
    assert "Executed:" in log_text
    assert "Complete:" in log_text
