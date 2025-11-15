"""Quick smoke test to validate orchestrator works.

This is a simplified test that validates the basic orchestration flow
without worrying about exact tool initialization details.
"""

import sys
from pathlib import Path

import pytest

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import uuid

from src.core.orchestrator import Orchestrator
from src.core.providers.ollama_provider import OllamaProvider
from src.models.conversation import ConversationSession


@pytest.mark.asyncio
async def test_basic_orchestration_works():
    """Test that basic orchestration completes without errors."""

    # Minimal setup - just local model
    model_config = {
        "model_name": "granite4-micro",
        "provider": "ollama",
        "cost_per_1k_input": 0.0,
        "cost_per_1k_output": 0.0,
    }

    local_connector = OllamaProvider(
        model_config=model_config,
        base_url="http://localhost:11434",
    )

    orchestrator = Orchestrator(
        local_connector=local_connector,
        external_connectors={},
        tools={},  # No tools for this simple test
        cost_limit=1.0,
        soft_cap_threshold=0.8,
    )

    conversation = ConversationSession(
        session_id=str(uuid.uuid4()),
        user_id="smoke_test_user",
    )

    # Simple query
    query = "What is 5 times 8?"

    print(f"\n🧪 Testing basic orchestration with query: {query}")

    response = await orchestrator.process_query(
        query_text=query,
        conversation=conversation,
        source="api",
    )

    # Validate we got a response
    assert response is not None, "Should get a response"
    assert response.content, "Response should have content"
    assert len(response.content) > 0, "Response content should not be empty"

    print(f"✓ Got response: {response.content}")

    # Check if answer is correct
    if "40" in response.content:
        print("✓ Answer is correct!")
    else:
        print("⚠️  Answer may be incorrect, expected 40 in response")

    print("✓ Basic orchestration test passed!")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
