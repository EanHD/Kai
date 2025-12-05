import asyncio
import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path.cwd()))

from src.core.orchestrator import Orchestrator
from src.core.providers.ollama_provider import OllamaProvider
from src.models.conversation import ConversationSession
from src.lib.config import ConfigLoader

async def run_test():
    # Load config to get model info
    config = ConfigLoader()
    
    # Setup connector (assuming Ollama is running on default port)
    # We'll use the default model from config or hardcode a common one if needed
    model_config = {
        "model_id": "qwen-3b-instruct", # Try to use a likely model
        "model_name": "qwen2.5:3b-instruct-q5_K_M",
        "provider": "ollama",
        "capabilities": ["chat"],
        "context_window": 4096,
        "cost_per_1k_input": 0,
        "cost_per_1k_output": 0
    }
    
    connector = OllamaProvider(model_config, "http://localhost:11434")
    
    # Initialize orchestrator
    orchestrator = Orchestrator(local_connector=connector)
    
    # Mock conversation
    conv = ConversationSession(user_id="test_user", cost_limit=1.0, request_source="cli")
    
    query = "i’m bored, give me something cursed to google"
    print(f"User: {query}")
    print("Kai: ", end="", flush=True)
    
    full_response = ""
    try:
        async for chunk in orchestrator.process_query_stream(query, conv):
            print(chunk, end="", flush=True)
            full_response += chunk
        print()
    except Exception as e:
        print(f"\nError: {e}")

if __name__ == "__main__":
    asyncio.run(run_test())
