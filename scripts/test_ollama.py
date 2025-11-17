#!/usr/bin/env python3
"""Test Ollama connection and model availability."""

import asyncio
import httpx
import sys


async def test_ollama():
    """Test Ollama server and model."""
    base_url = "http://localhost:11434"
    
    print("🔍 Testing Ollama Connection...")
    print(f"   Base URL: {base_url}")
    print()
    
    client = httpx.AsyncClient(timeout=10.0)
    
    try:
        # Test 1: Check server is running
        print("1️⃣  Checking if Ollama server is running...")
        try:
            response = await client.get(f"{base_url}/api/tags")
            response.raise_for_status()
            data = response.json()
            models = data.get("models", [])
            print(f"   ✅ Server is running")
            print(f"   📦 Available models: {len(models)}")
            for model in models:
                print(f"      • {model['name']}")
            print()
        except Exception as e:
            print(f"   ❌ Server not responding: {e}")
            print()
            print("Fix: Start Ollama with: ollama serve")
            return False
        
        # Test 2: Check if granite4:micro-h exists
        print("2️⃣  Checking for granite4:micro-h model...")
        model_names = [m['name'] for m in models]
        if 'granite4:micro-h' in model_names:
            print("   ✅ granite4:micro-h found")
        else:
            print("   ❌ granite4:micro-h not found")
            print()
            print("Fix: Pull model with: ollama pull granite4:micro-h")
            return False
        print()
        
        # Test 3: Try generating with the model
        print("3️⃣  Testing generation with granite4:micro-h...")
        payload = {
            "model": "granite4:micro-h",
            "messages": [{"role": "user", "content": "Say 'test successful' and nothing else."}],
            "stream": False,
            "options": {"temperature": 0.1}
        }
        
        try:
            response = await client.post(f"{base_url}/api/chat", json=payload)
            response.raise_for_status()
            data = response.json()
            content = data.get("message", {}).get("content", "")
            print(f"   ✅ Generation successful")
            print(f"   📝 Response: {content[:100]}")
            print(f"   📊 Tokens: {data.get('eval_count', 0)} generated")
            print()
        except httpx.HTTPStatusError as e:
            print(f"   ❌ HTTP Error: {e.response.status_code}")
            print(f"   📄 Response: {e.response.text}")
            return False
        except Exception as e:
            print(f"   ❌ Generation failed: {e}")
            return False
        
        print("✅ All tests passed! Ollama is working correctly.")
        return True
        
    finally:
        await client.aclose()


if __name__ == "__main__":
    success = asyncio.run(test_ollama())
    sys.exit(0 if success else 1)
