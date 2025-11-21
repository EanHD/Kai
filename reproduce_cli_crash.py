import asyncio
import logging
import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.core.orchestrator import Orchestrator
from src.core.providers.ollama_provider import OllamaProvider
from src.lib.config import ConfigLoader
from src.models.conversation import ConversationSession

# Setup logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

async def main():
    print("Initializing CLI-like environment...")
    
    config = ConfigLoader()
    
    # Initialize local connector (Granite)
    ollama_url = config.get_env("ollama_base_url") or "http://localhost:11434"
    local_connector = OllamaProvider({
        "model_name": "qwen2.5:3b-instruct-q5_K_M",
        "context_window": 2000000,
        "cost_per_1k_input": 0.0,
        "cost_per_1k_output": 0.0
    }, ollama_url)
    
    # Initialize orchestrator WITHOUT planner_connector (like CLI)
    orchestrator = Orchestrator(
        local_connector=local_connector,
        external_connectors={}, # Assume no external for now to test local path
        tools={}, # No tools for now
        cost_limit=1.0,
        soft_cap_threshold=0.8
    )
    
    # Create dummy conversation
    conversation = ConversationSession(
        session_id="test_session",
        user_id="test_user",
        cost_limit=1.0
    )
    
    print("Running query: 'do you know about mars?'")
    
    # Run process_query_stream
    try:
        async for chunk in orchestrator.process_query_stream(
            query_text="do you know about mars?",
            conversation=conversation,
            source="cli"
        ):
            print(chunk, end="", flush=True)
        print("\nSuccess!")
    except Exception as e:
        print(f"\nCrashed: {e}")

if __name__ == "__main__":
    asyncio.run(main())
