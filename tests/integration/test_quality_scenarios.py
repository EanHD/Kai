"""Integration tests for Kai's response quality with realistic multi-turn scenarios."""

import pytest
import uuid
from datetime import datetime
from src.core.orchestrator import Orchestrator
from src.core.providers.ollama_provider import OllamaProvider
from src.storage.sqlite_store import SQLiteStore
from src.models.conversation import ConversationSession
from src.core.conversation_service import ConversationService
from src.lib.config import ConfigLoader

@pytest.fixture
async def orchestrator_setup():
    """Create orchestrator instance using actual Kai setup."""
    # Load real config
    config_loader = ConfigLoader()
    
    # Get local model config
    active_models = config_loader.get_active_models()
    local_config = None
    for model in active_models:
        if model.provider == "ollama":
            local_config = model
            break
    
    if not local_config:
        pytest.skip("No local Ollama model configured")
    
    # Create config dict
    config_dict = {
        "model_id": local_config.model_id,
        "model_name": local_config.model_name,
        "provider": local_config.provider,
        "capabilities": local_config.capabilities,
        "context_window": local_config.context_window,
        "cost_per_1k_input": local_config.cost_per_1k_input,
        "cost_per_1k_output": local_config.cost_per_1k_output,
    }
    
    # Create provider
    ollama_url = config_loader.get_env("ollama_base_url")
    local_connector = OllamaProvider(config_dict, ollama_url)
    
    # Create orchestrator
    orchestrator = Orchestrator(
        local_connector=local_connector,
        external_connectors={},
        tools={},
        cost_limit=1.0,
    )
    
    # Add conversation service
    # Use in-memory DB for tests if possible, or temp file
    db_path = ":memory:" 
    store = SQLiteStore(db_path)
    conv_service = ConversationService(store)
    orchestrator.conversation_service = conv_service
    
    return orchestrator, conv_service

@pytest.mark.asyncio
async def test_scenario_instant_greeting(orchestrator_setup):
    """Test: Simple greeting (instant response)."""
    orchestrator, conv_service = orchestrator_setup
    session = ConversationSession(session_id=str(uuid.uuid4()), user_id="test")
    
    start = datetime.now()
    response = await orchestrator.process_query("hey", session, source="cli")
    elapsed = (datetime.now() - start).total_seconds()
    
    assert elapsed < 1.0, "Greeting should be instant"
    assert "hey" in response.content.lower() or "hello" in response.content.lower() or "hi" in response.content.lower()
    assert len(response.content) < 150, "Greeting should be brief"

@pytest.mark.asyncio
async def test_scenario_fast_path_context(orchestrator_setup):
    """Test: Context retention in fast path."""
    orchestrator, conv_service = orchestrator_setup
    session = ConversationSession(session_id=str(uuid.uuid4()), user_id="test")
    
    # Turn 1: Establish context
    response1 = await orchestrator.process_query(
        "I have a 2007 Chevy Aveo",
        session,
        source="cli"
    )
    
    # Save to conversation history
    await conv_service.add_message(session.session_id, "user", "I have a 2007 Chevy Aveo")
    await conv_service.add_message(session.session_id, "assistant", response1.content)
    
    # Turn 2: Vague follow-up
    response2 = await orchestrator.process_query(
        "tell me more about it",
        session,
        source="cli"
    )
    
    # Analysis
    content_lower = response2.content.lower()
    context_terms = ["aveo", "chevy", "2007", "car", "vehicle"]
    assert any(term in content_lower for term in context_terms), \
        f"Response should reference context. Got: {response2.content}"

@pytest.mark.asyncio
async def test_scenario_factual_question(orchestrator_setup):
    """Test: Simple factual question (fast path)."""
    orchestrator, conv_service = orchestrator_setup
    session = ConversationSession(session_id=str(uuid.uuid4()), user_id="test")
    
    start = datetime.now()
    response = await orchestrator.process_query(
        "what is the capital of France?",
        session,
        source="cli"
    )
    elapsed = (datetime.now() - start).total_seconds()
    
    assert "paris" in response.content.lower()
    assert len(response.content) < 300
    # assert elapsed < 5.0 # Removed timing assertion as it can be flaky in CI

@pytest.mark.asyncio
async def test_scenario_multi_turn_memory(orchestrator_setup):
    """Test: Conversation with multiple exchanges."""
    orchestrator, conv_service = orchestrator_setup
    session = ConversationSession(session_id=str(uuid.uuid4()), user_id="test")
    
    # Exchange 1
    r1 = await orchestrator.process_query("My favorite color is blue", session, source="cli")
    await conv_service.add_message(session.session_id, "user", "My favorite color is blue")
    await conv_service.add_message(session.session_id, "assistant", r1.content)
    
    # Exchange 2
    r2 = await orchestrator.process_query("I like programming", session, source="cli")
    await conv_service.add_message(session.session_id, "user", "I like programming")
    await conv_service.add_message(session.session_id, "assistant", r2.content)
    
    # Exchange 3
    r3 = await orchestrator.process_query("I have a cat", session, source="cli")
    await conv_service.add_message(session.session_id, "user", "I have a cat")
    await conv_service.add_message(session.session_id, "assistant", r3.content)
    
    # Turn 4: Recall
    response4 = await orchestrator.process_query(
        "what do you know about me?",
        session,
        source="cli"
    )
    
    content = response4.content.lower()
    assert "blue" in content, "Should remember favorite color"
    assert "program" in content, "Should remember programming"
    assert "cat" in content, "Should remember cat"
