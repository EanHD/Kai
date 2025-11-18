#!/usr/bin/env python3
"""Test Kai's response quality with realistic multi-turn scenarios."""

import asyncio
import sys
import uuid
from datetime import datetime

# Add src to path
sys.path.insert(0, '/home/eanhd/projects/kai')

from src.core.orchestrator import Orchestrator
from src.core.llm_connector import LLMConnector
from src.models.conversation import ConversationSession
from src.core.conversation_service import ConversationService

# ANSI colors for output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"


def print_test(name: str):
    """Print test name."""
    print(f"\n{'='*60}")
    print(f"{BLUE}TEST: {name}{RESET}")
    print('='*60)


def print_turn(num: int, query: str):
    """Print conversation turn."""
    print(f"\n{YELLOW}Turn {num}:{RESET} {query}")


def print_response(response: str, time_taken: float):
    """Print Kai's response."""
    print(f"{GREEN}Kai ({time_taken:.2f}s):{RESET} {response[:300]}...")
    if len(response) > 300:
        print(f"  [...{len(response)-300} more chars]")


def print_analysis(expected: str, actual: str, passed: bool):
    """Print test analysis."""
    status = f"{GREEN}✓ PASS{RESET}" if passed else f"{RED}✗ FAIL{RESET}"
    print(f"\n{status}")
    print(f"Expected: {expected}")
    if not passed:
        print(f"Issue: {actual}")


async def create_orchestrator():
    """Create orchestrator instance using actual Kai setup."""
    from src.lib.config import ConfigLoader
    from src.core.providers.ollama_provider import OllamaProvider
    from src.storage.sqlite_store import SQLiteStore
    
    # Load real config
    config_loader = ConfigLoader()
    kai_config = config_loader.config
    
    # Get local model config
    active_models = kai_config.get_active_models()
    local_config = None
    for model in active_models:
        if model.provider == "ollama":
            local_config = model
            break
    
    if not local_config:
        raise RuntimeError("No local Ollama model configured")
    
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
    ollama_url = kai_config.get_env("ollama_base_url")
    local_connector = OllamaProvider(config_dict, ollama_url)
    
    # Create orchestrator
    orchestrator = Orchestrator(
        local_connector=local_connector,
        external_connectors={},
        tools={},
        cost_limit=1.0,
    )
    
    # Add conversation service
    db_path = "/tmp/kai_test.db"
    store = SQLiteStore(db_path)
    conv_service = ConversationService(store)
    orchestrator.conversation_service = conv_service
    
    return orchestrator, conv_service


async def test_scenario_1():
    """Test: Simple greeting (instant response)."""
    print_test("Scenario 1: Instant Greeting")
    
    orchestrator, conv_service = await create_orchestrator()
    session = ConversationSession(session_id=str(uuid.uuid4()), user_id="test")
    
    start = datetime.now()
    response = await orchestrator.process_query("hey", session, source="cli")
    elapsed = (datetime.now() - start).total_seconds()
    
    print_turn(1, "hey")
    print_response(response.content, elapsed)
    
    # Analysis
    passed = (
        elapsed < 0.5 and  # Should be instant
        "hey" in response.content.lower() and
        len(response.content) < 100  # Should be brief
    )
    
    print_analysis(
        "Instant response (<0.5s), casual greeting, brief",
        f"Time: {elapsed:.2f}s, Length: {len(response.content)}",
        passed
    )
    
    return passed


async def test_scenario_2():
    """Test: Context retention in fast path."""
    print_test("Scenario 2: Fast Path Context Retention")
    
    orchestrator, conv_service = await create_orchestrator()
    session = ConversationSession(session_id=str(uuid.uuid4()), user_id="test")
    
    # Turn 1: Establish context
    print_turn(1, "I have a 2007 Chevy Aveo")
    start = datetime.now()
    response1 = await orchestrator.process_query(
        "I have a 2007 Chevy Aveo",
        session,
        source="cli"
    )
    elapsed1 = (datetime.now() - start).total_seconds()
    print_response(response1.content, elapsed1)
    
    # Save to conversation history
    await conv_service.add_message(
        session.session_id,
        "user",
        "I have a 2007 Chevy Aveo"
    )
    await conv_service.add_message(
        session.session_id,
        "assistant",
        response1.content
    )
    
    # Turn 2: Vague follow-up (should reference "2007 Chevy Aveo")
    print_turn(2, "tell me more about it")
    start = datetime.now()
    response2 = await orchestrator.process_query(
        "tell me more about it",
        session,
        source="cli"
    )
    elapsed2 = (datetime.now() - start).total_seconds()
    print_response(response2.content, elapsed2)
    
    # Analysis
    context_maintained = any(
        term in response2.content.lower() 
        for term in ["aveo", "chevy", "2007", "car"]
    )
    
    print_analysis(
        "Should reference 'Aveo' or 'Chevy' or 'car' from context",
        f"Context maintained: {context_maintained}",
        context_maintained
    )
    
    return context_maintained


async def test_scenario_3():
    """Test: Simple factual question (fast path with history)."""
    print_test("Scenario 3: Fast Path Factual Question")
    
    orchestrator, conv_service = await create_orchestrator()
    session = ConversationSession(session_id=str(uuid.uuid4()), user_id="test")
    
    print_turn(1, "what is the capital of France?")
    start = datetime.now()
    response = await orchestrator.process_query(
        "what is the capital of France?",
        session,
        source="cli"
    )
    elapsed = (datetime.now() - start).total_seconds()
    print_response(response.content, elapsed)
    
    # Analysis
    correct = "paris" in response.content.lower()
    concise = len(response.content) < 200  # Should be brief
    fast = elapsed < 5.0
    
    passed = correct and concise and fast
    
    print_analysis(
        "Should say 'Paris', be concise (<200 chars), fast (<5s)",
        f"Correct: {correct}, Concise: {concise}, Fast: {fast}",
        passed
    )
    
    return passed


async def test_scenario_4():
    """Test: Conversation with multiple exchanges."""
    print_test("Scenario 4: Multi-Turn Context (6 messages = 3 exchanges)")
    
    orchestrator, conv_service = await create_orchestrator()
    session = ConversationSession(session_id=str(uuid.uuid4()), user_id="test")
    
    # Exchange 1
    print_turn(1, "My favorite color is blue")
    response1 = await orchestrator.process_query(
        "My favorite color is blue",
        session,
        source="cli"
    )
    print_response(response1.content, 0)
    await conv_service.add_message(session.session_id, "user", "My favorite color is blue")
    await conv_service.add_message(session.session_id, "assistant", response1.content)
    
    # Exchange 2
    print_turn(2, "I like programming")
    response2 = await orchestrator.process_query(
        "I like programming",
        session,
        source="cli"
    )
    print_response(response2.content, 0)
    await conv_service.add_message(session.session_id, "user", "I like programming")
    await conv_service.add_message(session.session_id, "assistant", response2.content)
    
    # Exchange 3
    print_turn(3, "I have a cat")
    response3 = await orchestrator.process_query(
        "I have a cat",
        session,
        source="cli"
    )
    print_response(response3.content, 0)
    await conv_service.add_message(session.session_id, "user", "I have a cat")
    await conv_service.add_message(session.session_id, "assistant", response3.content)
    
    # Turn 4: Reference all previous context (tests 6-message window)
    print_turn(4, "what do you know about me?")
    start = datetime.now()
    response4 = await orchestrator.process_query(
        "what do you know about me?",
        session,
        source="cli"
    )
    elapsed = (datetime.now() - start).total_seconds()
    print_response(response4.content, elapsed)
    
    # Analysis - should remember all 3 facts (blue, programming, cat)
    remembers_blue = "blue" in response4.content.lower()
    remembers_programming = "program" in response4.content.lower()
    remembers_cat = "cat" in response4.content.lower()
    
    passed = remembers_blue and remembers_programming and remembers_cat
    
    print_analysis(
        "Should remember all 3 facts: blue, programming, cat",
        f"Blue: {remembers_blue}, Programming: {remembers_programming}, Cat: {remembers_cat}",
        passed
    )
    
    return passed


async def main():
    """Run all test scenarios."""
    print(f"\n{BLUE}{'='*60}")
    print("KAI QUALITY TESTING SUITE")
    print(f"{'='*60}{RESET}\n")
    
    results = []
    
    try:
        # Test 1: Instant greeting
        result1 = await test_scenario_1()
        results.append(("Instant Greeting", result1))
        
        # Test 2: Fast path context
        result2 = await test_scenario_2()
        results.append(("Fast Path Context", result2))
        
        # Test 3: Simple factual
        result3 = await test_scenario_3()
        results.append(("Simple Factual", result3))
        
        # Test 4: Multi-turn memory
        result4 = await test_scenario_4()
        results.append(("Multi-Turn Memory", result4))
        
    except Exception as e:
        print(f"\n{RED}ERROR: {e}{RESET}")
        import traceback
        traceback.print_exc()
        return 1
    
    # Summary
    print(f"\n{BLUE}{'='*60}")
    print("TEST SUMMARY")
    print(f"{'='*60}{RESET}\n")
    
    passed = sum(1 for _, r in results if r)
    total = len(results)
    
    for name, result in results:
        status = f"{GREEN}✓{RESET}" if result else f"{RED}✗{RESET}"
        print(f"{status} {name}")
    
    print(f"\n{BLUE}Score: {passed}/{total} ({passed/total*100:.0f}%){RESET}")
    
    if passed == total:
        print(f"\n{GREEN}🎉 ALL TESTS PASSED!{RESET}")
        return 0
    else:
        print(f"\n{YELLOW}⚠️  Some tests failed - review output above{RESET}")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
