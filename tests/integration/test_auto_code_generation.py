"""Integration test for auto-code-generation feature."""

from unittest.mock import Mock

import pytest

from src.core.orchestrator import Orchestrator
from src.core.providers.ollama_provider import OllamaProvider
from src.models.conversation import ConversationSession
from src.tools.code_executor import CodeExecutorTool


@pytest.fixture
def mock_code_executor():
    """Mock code executor that returns predictable results."""
    from unittest.mock import AsyncMock

    from src.tools.base_tool import ToolResult, ToolStatus

    tool = Mock(spec=CodeExecutorTool)

    # Mock execute_with_fallback as AsyncMock
    tool.execute_with_fallback = AsyncMock(
        return_value=ToolResult(
            tool_name="CodeExecutorTool",
            status=ToolStatus.SUCCESS,
            data={
                "stdout": "Found 16 valid combinations:\n  A = 3.5\n  B = 7.2\n...\n\nTotal: 16 combinations",
                "stderr": "",
                "exit_code": 0,
            },
            execution_time_ms=150,
            fallback_used=False,
        )
    )

    return tool


@pytest.mark.asyncio
async def test_auto_code_generation_robot_problem(mock_code_executor):
    """Test that the robot box problem triggers auto-code-generation."""
    # Setup
    mock_local_connector = Mock(spec=OllamaProvider)

    # Mock LLM response
    async def mock_generate(messages, temperature=0.7, max_tokens=None):
        from src.core.llm_connector import LLMResponse

        return LLMResponse(
            content="Based on the calculation, there are 16 different combinations.",
            token_count=15,
            cost=0.0,
            model_used="granite4:micro-h",
            finish_reason="stop",
            metadata={},
        )

    mock_local_connector.generate = mock_generate

    # Create orchestrator with mocked code executor
    orchestrator = Orchestrator(
        local_connector=mock_local_connector,
        external_connectors={},
        tools={"code_exec": mock_code_executor},
        cost_limit=1.0,
    )

    # Create conversation
    conversation = ConversationSession(
        user_id="test",
        cost_limit=1.0,
        request_source="test",
    )

    # The problematic query
    query = """Kai is training a robot to carry boxes.
Box weights: A=3.5kg, B=7.2kg, C=4.8kg, D=2.3kg, E=6.1kg
The robot can carry maximum 12kg.
Use Python to calculate: How many different combinations can the robot carry?"""

    # Process query
    response = await orchestrator.process_query(
        query_text=query,
        conversation=conversation,
    )

    # Verify code executor was called
    assert mock_code_executor.execute_with_fallback.call_count == 1

    # Verify code was auto-generated
    call_args = mock_code_executor.execute_with_fallback.call_args
    params = call_args[0][0]

    assert "code" in params
    assert params.get("auto_generated") is True

    # Verify generated code looks right
    code = params["code"]
    assert "combinations" in code
    assert "3.5" in code
    assert "12" in code

    # Verify response was generated
    assert response is not None
    assert response.content is not None


@pytest.mark.asyncio
async def test_auto_code_generation_arithmetic():
    """Test auto-generation for simple arithmetic."""
    from unittest.mock import AsyncMock

    from src.tools.base_tool import ToolResult, ToolStatus

    mock_local_connector = Mock(spec=OllamaProvider)
    mock_code_executor = Mock(spec=CodeExecutorTool)

    # Mock executor to return result
    mock_code_executor.execute_with_fallback = AsyncMock(
        return_value=ToolResult(
            tool_name="CodeExecutorTool",
            status=ToolStatus.SUCCESS,
            data={"stdout": "1543 * 892 = 1376356\n", "stderr": "", "exit_code": 0},
            execution_time_ms=50,
        )
    )

    # Mock LLM
    async def mock_generate(messages, temperature=0.7, max_tokens=None):
        from src.core.llm_connector import LLMResponse

        return LLMResponse(
            content="The result is 1,376,356.",
            token_count=10,
            cost=0.0,
            model_used="granite4:micro-h",
            finish_reason="stop",
            metadata={},
        )

    mock_local_connector.generate = mock_generate

    orchestrator = Orchestrator(
        local_connector=mock_local_connector,
        external_connectors={},
        tools={"code_exec": mock_code_executor},
        cost_limit=1.0,
    )

    conversation = ConversationSession(
        user_id="test",
        cost_limit=1.0,
        request_source="test",
    )

    # Simple arithmetic query
    query = "What's 1543 * 892?"

    await orchestrator.process_query(
        query_text=query,
        conversation=conversation,
    )

    # Verify code was generated and executed
    assert mock_code_executor.execute_with_fallback.call_count == 1

    # Check the generated code
    call_args = mock_code_executor.execute_with_fallback.call_args
    params = call_args[0][0]
    code = params["code"]

    assert "1543" in code
    assert "892" in code
    assert "*" in code


@pytest.mark.asyncio
async def test_no_auto_generation_for_non_computational():
    """Test that non-computational queries don't trigger auto-generation."""
    mock_local_connector = Mock(spec=OllamaProvider)
    mock_code_executor = Mock(spec=CodeExecutorTool)

    async def mock_generate(messages, temperature=0.7, max_tokens=None):
        from src.core.llm_connector import LLMResponse

        return LLMResponse(
            content="Python is a high-level programming language.",
            token_count=12,
            cost=0.0,
            model_used="granite4:micro-h",
            finish_reason="stop",
            metadata={},
        )

    mock_local_connector.generate = mock_generate

    orchestrator = Orchestrator(
        local_connector=mock_local_connector,
        external_connectors={},
        tools={"code_exec": mock_code_executor},
        cost_limit=1.0,
    )

    conversation = ConversationSession(
        user_id="test",
        cost_limit=1.0,
        request_source="test",
    )

    # Non-computational query
    query = "What is Python?"

    await orchestrator.process_query(
        query_text=query,
        conversation=conversation,
    )

    # Verify code executor was NOT called
    assert mock_code_executor.execute_with_fallback.call_count == 0
