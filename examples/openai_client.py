#!/usr/bin/env python3
"""
Example: Using Kai API with OpenAI Python SDK

This demonstrates drop-in compatibility with the OpenAI Python library.
Simply point the client to your Kai API endpoint.

Run: uv run python examples/openai_client.py
"""

from openai import OpenAI

# Point to Kai API endpoint
client = OpenAI(
    base_url="http://localhost:9000/v1",
    api_key="not-needed",  # Auth not required in dev mode
)


def example_chat_completion():
    """Non-streaming chat completion."""
    print("Example 1: Non-streaming chat completion")
    print("-" * 60)

    response = client.chat.completions.create(
        model="qwen-local",  # Uses local Ollama (Qwen2.5 3B)
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "What is the capital of France?"},
        ],
        temperature=0.7,
        max_tokens=100,
    )

    print(f"Response: {response.choices[0].message.content}")
    print(f"Tokens: {response.usage.total_tokens}")
    print()


def example_streaming():
    """Streaming chat completion."""
    print("Example 2: Streaming chat completion")
    print("-" * 60)

    stream = client.chat.completions.create(
        model=\"qwen-local\",
        messages=[
            {\"role\": \"user\", \"content\": \"Count from 1 to 5.\"},
        ],
        stream=True,
    )

    print("Streaming response: ", end="", flush=True)
    for chunk in stream:
        if chunk.choices[0].delta.content:
            print(chunk.choices[0].delta.content, end="", flush=True)
    print("\n")


def example_list_models():
    """List available models."""
    print("Example 3: List available models")
    print("-" * 60)

    models = client.models.list()

    print("Available models:")
    for model in models.data:
        print(f"  - {model.id}")
    print()


def example_with_tools():
    """Chat completion with function calling."""
    print("Example 4: Function calling")
    print("-" * 60)

    tools = [
        {
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "Get current weather for a location",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "location": {
                            "type": "string",
                            "description": "City name",
                        },
                    },
                    "required": ["location"],
                },
            },
        }
    ]

    response = client.chat.completions.create(
        model=\"qwen-local\",
        messages=[
            {"role": "user", "content": "What's the weather in Paris?"},
        ],
        tools=tools,
    )

    print(f"Response: {response.choices[0].message}")
    print()


if __name__ == "__main__":
    print("Kai OpenAI-Compatible API - Example Client")
    print("=" * 60)
    print()

    example_chat_completion()
    example_streaming()
    example_list_models()
    # example_with_tools()  # Uncomment when tool calling is fully integrated
