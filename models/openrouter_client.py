import os
import json
from typing import AsyncGenerator, Dict, List, Optional

import httpx

# OpenRouter Chat Completions endpoint
OR_API_URL = "https://openrouter.ai/api/v1/chat/completions"

# Read configuration from environment
OR_API_KEY = os.getenv("OPEN_ROUTER_KEY", "")
OR_APP_URL = os.getenv("OPENROUTER_APP_URL", "kai.local")  # used for HTTP-Referer attribution
OR_APP_TITLE = os.getenv("OPENROUTER_APP_TITLE", "Kai")      # used for X-Title attribution


def _headers() -> Dict[str, str]:
    if not OR_API_KEY:
        raise RuntimeError("OPEN_ROUTER_KEY is missing; set it in your environment")
    return {
        "Authorization": f"Bearer {OR_API_KEY}",
        "HTTP-Referer": OR_APP_URL,
        "X-Title": OR_APP_TITLE,
        "Content-Type": "application/json",
    }


def _payload(
    model: str,
    messages: List[Dict],
    temperature: Optional[float] = 0.7,
    max_tokens: Optional[int] = None,
    stream: bool = False,
) -> Dict:
    body: Dict = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "stream": stream,
    }
    if max_tokens is not None:
        body["max_tokens"] = max_tokens
    return body


async def chat(
    model: str,
    messages: List[Dict],
    temperature: Optional[float] = 0.7,
    max_tokens: Optional[int] = None,
) -> str:
    """Single-shot call to OpenRouter. Returns the final assistant message text.

    Models use OpenRouter slugs like:
      - "openai/gpt-oss-120b"
      - "openai/gpt-5"
    """
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            OR_API_URL,
            headers=_headers(),
            json=_payload(model, messages, temperature, max_tokens, stream=False),
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]


async def stream_chat(
    model: str,
    messages: List[Dict],
    temperature: Optional[float] = 0.7,
    max_tokens: Optional[int] = None,
) -> AsyncGenerator[str, None]:
    """Stream tokens via SSE, yielding text deltas as they arrive."""
    async with httpx.AsyncClient(timeout=None) as client:
        async with client.stream(
            "POST",
            OR_API_URL,
            headers=_headers(),
            json=_payload(model, messages, temperature, max_tokens, stream=True),
        ) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line:
                    continue
                if line.startswith("data: "):
                    data_str = line[len("data: "):]
                    if data_str.strip() == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data_str)
                        delta = (
                            chunk.get("choices", [{}])[0]
                            .get("delta", {})
                            .get("content", "")
                        )
                        if delta:
                            yield delta
                    except json.JSONDecodeError:
                        # Ignore keepalives or malformed lines
                        continue


# Convenience wrappers for your common models
async def ask_oss120b(messages: List[Dict], temperature: float = 0.7, max_tokens: Optional[int] = None) -> str:
    """Call OpenRouter's OSS 120B model (OpenAI open-weight)."""
    return await chat("openai/gpt-oss-120b", messages, temperature=temperature, max_tokens=max_tokens)


async def ask_gpt5(messages: List[Dict], temperature: float = 0.7, max_tokens: Optional[int] = None) -> str:
    """Call OpenRouter's GPT-5 model."""
    return await chat("openai/gpt-5", messages, temperature=temperature, max_tokens=max_tokens)
