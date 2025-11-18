#!/usr/bin/env python3
"""Simple test of Kai quality improvements."""

import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

# Suppress warnings
os.environ["PYTHONWARNINGS"] = "ignore"
import warnings
warnings.simplefilter("ignore")

from dotenv import load_dotenv
load_dotenv()

import asyncio
import uuid
from src.cli.main import CLI
from src.models.conversation import ConversationSession

RESET = "\033[0m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"


async def test_conversation():
    """Test Kai's conversational quality."""
    
    print(f"\n{BLUE}{'='*60}")
    print("KAI QUALITY TEST - Conversational Context")
    print(f"{'='*60}{RESET}\n")
    
    # Initialize CLI (synchronous __init__)
    cli = CLI(debug=False, show_reflection=False)
    
    # CRITICAL: Inject conversation service into orchestrator for context retention
    cli.orchestrator.conversation_service = cli.conversation_service
    
    # Create session
    session = ConversationSession(
        session_id=str(uuid.uuid4()),
        user_id="test_user"
    )
    
    # Test 1: Simple greeting
    print(f"{YELLOW}Test 1: Simple greeting{RESET}")
    print(f"User: hey")
    response1 = await cli.orchestrator.process_query("hey", session, source="cli")
    print(f"{GREEN}Kai: {response1.content}{RESET}\n")
    
    # Save to history
    cli.conversation_service.save_message({
        "session_id": session.session_id,
        "role": "user",
        "content": "hey",
        "timestamp": response1.timestamp
    })
    cli.conversation_service.save_message({
        "session_id": session.session_id,
        "role": "assistant",
        "content": response1.content,
        "timestamp": response1.timestamp
    })
    
    # Test 2: Provide context
    print(f"{YELLOW}Test 2: Establish context{RESET}")
    print(f"User: I have a 2007 Chevy Aveo")
    response2 = await cli.orchestrator.process_query(
        "I have a 2007 Chevy Aveo",
        session,
        source="cli"
    )
    print(f"{GREEN}Kai: {response2.content}{RESET}\n")
    
    # Save to history
    cli.conversation_service.save_message({
        "session_id": session.session_id,
        "role": "user",
        "content": "I have a 2007 Chevy Aveo",
        "timestamp": response2.timestamp
    })
    cli.conversation_service.save_message({
        "session_id": session.session_id,
        "role": "assistant",
        "content": response2.content,
        "timestamp": response2.timestamp
    })
    
    # Test 3: Vague follow-up (should remember Aveo)
    print(f"{YELLOW}Test 3: Context retention (vague pronoun){RESET}")
    print(f"User: tell me more about it")
    response3 = await cli.orchestrator.process_query(
        "tell me more about it",
        session,
        source="cli"
    )
    print(f"{GREEN}Kai: {response3.content}{RESET}\n")
    
    # Analysis
    has_context = any(word in response3.content.lower() for word in ["aveo", "chevy", "car", "vehicle"])
    print(f"Analysis: Context retention = {GREEN if has_context else 'FAIL'}")
    print(f"  - Should mention 'Aveo', 'Chevy', 'car', or 'vehicle': {'✓' if has_context else '✗'}{RESET}\n")
    
    # Save to history
    cli.conversation_service.save_message({
        "session_id": session.session_id,
        "role": "user",
        "content": "tell me more about it",
        "timestamp": response3.timestamp
    })
    cli.conversation_service.save_message({
        "session_id": session.session_id,
        "role": "assistant",
        "content": response3.content,
        "timestamp": response3.timestamp
    })
    
    # Test 4: Add more context
    print(f"{YELLOW}Test 4: Add more context{RESET}")
    print(f"User: My favorite color is blue")
    response4 = await cli.orchestrator.process_query(
        "My favorite color is blue",
        session,
        source="cli"
    )
    print(f"{GREEN}Kai: {response4.content}{RESET}\n")
    
    cli.conversation_service.save_message({
        "session_id": session.session_id,
        "role": "user",
        "content": "My favorite color is blue",
        "timestamp": response4.timestamp
    })
    cli.conversation_service.save_message({
        "session_id": session.session_id,
        "role": "assistant",
        "content": response4.content,
        "timestamp": response4.timestamp
    })
    
    # Test 5: One more context item
    print(f"{YELLOW}Test 5: Add third context item{RESET}")
    print(f"User: I like programming in Python")
    response5 = await cli.orchestrator.process_query(
        "I like programming in Python",
        session,
        source="cli"
    )
    print(f"{GREEN}Kai: {response5.content}{RESET}\n")
    
    cli.conversation_service.save_message({
        "session_id": session.session_id,
        "role": "user",
        "content": "I like programming in Python",
        "timestamp": response5.timestamp
    })
    cli.conversation_service.save_message({
        "session_id": session.session_id,
        "role": "assistant",
        "content": response5.content,
        "timestamp": response5.timestamp
    })
    
    # Test 6: Recall all context (tests 6-message window = 3 exchanges)
    print(f"{YELLOW}Test 6: Multi-context recall (6-message window){RESET}")
    print(f"User: what do you remember about me?")
    response6 = await cli.orchestrator.process_query(
        "what do you remember about me?",
        session,
        source="cli"
    )
    print(f"{GREEN}Kai: {response6.content}{RESET}\n")
    
    # Analysis
    remembers_aveo = "aveo" in response6.content.lower() or "chevy" in response6.content.lower()
    remembers_blue = "blue" in response6.content.lower()
    remembers_python = "python" in response6.content.lower() or "program" in response6.content.lower()
    
    print(f"Analysis: Multi-context memory (6-message window)")
    print(f"  - Remembers Aveo/Chevy: {'✓' if remembers_aveo else '✗'}")
    print(f"  - Remembers blue: {'✓' if remembers_blue else '✗'}")
    print(f"  - Remembers Python/programming: {'✓' if remembers_python else '✗'}")
    
    total = sum([remembers_aveo, remembers_blue, remembers_python])
    print(f"  - Score: {total}/3 ({total/3*100:.0f}%){RESET}\n")
    
    # Test 7: Factual question (fast path)
    print(f"{YELLOW}Test 7: Simple factual (fast path){RESET}")
    print(f"User: what is the capital of France?")
    response7 = await cli.orchestrator.process_query(
        "what is the capital of France?",
        session,
        source="cli"
    )
    print(f"{GREEN}Kai: {response7.content}{RESET}\n")
    
    correct = "paris" in response7.content.lower()
    concise = len(response7.content) < 150
    print(f"Analysis: Factual accuracy + conciseness")
    print(f"  - Says 'Paris': {'✓' if correct else '✗'}")
    print(f"  - Concise (<150 chars): {'✓' if concise else '✗'} (actual: {len(response7.content)} chars){RESET}\n")
    
    print(f"{BLUE}{'='*60}")
    print("TEST COMPLETE")
    print(f"{'='*60}{RESET}\n")


if __name__ == "__main__":
    asyncio.run(test_conversation())
