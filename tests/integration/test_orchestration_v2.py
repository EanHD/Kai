"""Integration tests for Orchestration V2 pipeline."""

import pytest
import os
from unittest.mock import AsyncMock, MagicMock, patch

from src.core.orchestrator import Orchestrator
from src.core.llm_connector import LLMConnector, LLMResponse
from src.models.conversation import ConversationSession
from src.core.plan_types import Plan, PlanStep, StepType, ComplexityLevel


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
        content='{"final_answer": "Test answer from V2 pipeline", "short_summary": "Test", "citations_used": []}',
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
def orchestrator_v2(mock_local_connector):
    """Create orchestrator with V2 enabled."""
    os.environ["KAI_ORCHESTRATION_V2"] = "true"
    
    orchestrator = Orchestrator(
        local_connector=mock_local_connector,
        external_connectors={},
        tools={},
    )
    
    return orchestrator


@pytest.mark.asyncio
async def test_simple_query_v2_pipeline(orchestrator_v2, mock_conversation):
    """Test that simple query goes through V2 pipeline."""
    query = "What is 2 + 2?"
    
    response = await orchestrator_v2.process_query(query, mock_conversation)
    
    # Verify response
    assert response is not None
    assert response.content == "Test answer from V2 pipeline"
    assert response.metadata.get("orchestration_version") == "v2"
    assert "plan_id" in response.metadata
    assert response.metadata.get("intent") == "test"


@pytest.mark.asyncio
async def test_v2_disabled_uses_v1(mock_local_connector, mock_conversation):
    """Test that V2 disabled falls back to V1."""
    os.environ["KAI_ORCHESTRATION_V2"] = "false"
    
    orchestrator = Orchestrator(
        local_connector=mock_local_connector,
        external_connectors={},
        tools={},
    )
    
    # V1 will likely fail with our simple mock, but that's ok
    # We just want to verify it doesn't try V2
    assert orchestrator.use_orchestration_v2 is False


@pytest.mark.asyncio
async def test_v2_error_fallback(mock_local_connector, mock_conversation):
    """Test that V2 errors fall back gracefully."""
    os.environ["KAI_ORCHESTRATION_V2"] = "true"
    
    # Make plan analyzer fail
    mock_local_connector.generate = AsyncMock(side_effect=Exception("Test error"))
    
    orchestrator = Orchestrator(
        local_connector=mock_local_connector,
        external_connectors={},
        tools={},
    )
    
    response = await orchestrator.process_query("test", mock_conversation)
    
    # Should get fallback error message
    assert response is not None
    # Accept either orchestrator or presenter fallback messages
    assert ("issue processing your request" in response.content or 
            "issue generating the final answer" in response.content)
    assert response.metadata.get("orchestration_version") in ["v2_fallback", "v2"]
    # Error should be logged somewhere
    assert response.metadata is not None


@pytest.mark.asyncio
async def test_v2_with_tools(mock_local_connector, mock_conversation):
    """Test V2 with tools configured."""
    os.environ["KAI_ORCHESTRATION_V2"] = "true"
    
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
    assert response.metadata.get("orchestration_version") == "v2"


def test_orchestrator_initialization_v2_components(mock_local_connector):
    """Test that V2 components are initialized."""
    os.environ["KAI_ORCHESTRATION_V2"] = "true"
    
    orchestrator = Orchestrator(
        local_connector=mock_local_connector,
        external_connectors={},
        tools={},
    )
    
    # Verify all V2 components exist
    assert hasattr(orchestrator, 'plan_analyzer')
    assert hasattr(orchestrator, 'specialist_verifier')
    assert hasattr(orchestrator, 'plan_executor')
    assert hasattr(orchestrator, 'presenter')
    assert orchestrator.use_orchestration_v2 is True


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
async def test_v2_logging(orchestrator_v2, mock_conversation, caplog):
    """Test that V2 logs key events."""
    import logging
    caplog.set_level(logging.INFO)
    
    await orchestrator_v2.process_query("test query", mock_conversation)
    
    # Check for key log messages
    log_text = caplog.text
    assert "Orchestration V2" in log_text
    assert "Plan generated" in log_text
    assert "Plan executed" in log_text
    assert "Finalization complete" in log_text
