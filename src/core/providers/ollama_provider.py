"""Ollama provider implementation for local model hosting."""

import logging
from typing import Any

import httpx

from src.core.llm_connector import LLMConnector, LLMResponse, Message

logger = logging.getLogger(__name__)


class OllamaProvider(LLMConnector):
    """Ollama provider for local model inference (granite4:tiny-h)."""

    def __init__(self, model_config: dict[str, Any], base_url: str = "http://localhost:11434"):
        """Initialize Ollama provider.

        Args:
            model_config: Model configuration dict
            base_url: Ollama server URL
        """
        super().__init__(model_config)
        self.base_url = base_url.rstrip("/")
        self.client = httpx.AsyncClient(timeout=30.0)

    async def generate(
        self,
        messages: list[Message],
        temperature: float = 0.7,
        max_tokens: int | None = None,
        **kwargs,
    ) -> LLMResponse:
        """Generate response using Ollama.

        Args:
            messages: Conversation messages
            temperature: Sampling temperature
            max_tokens: Maximum tokens (not supported by Ollama directly)
            **kwargs: Additional Ollama parameters

        Returns:
            LLMResponse with generated content
        """
        try:
            # Convert messages to Ollama format
            ollama_messages = []
            for msg in messages:
                # Handle both Message objects and dicts
                if isinstance(msg, dict):
                    ollama_messages.append(
                        {"role": msg.get("role", "user"), "content": msg.get("content", "")}
                    )
                else:
                    ollama_messages.append({"role": msg.role, "content": msg.content})

            # Build request payload
            payload = {
                "model": self.model_name,
                "messages": ollama_messages,
                "stream": False,
                "options": {
                    "temperature": temperature,
                },
            }

            # Add max tokens if specified (Ollama uses num_predict)
            if max_tokens:
                payload["options"]["num_predict"] = max_tokens

            # Call Ollama API
            response = await self.client.post(
                f"{self.base_url}/api/chat",
                json=payload,
            )
            response.raise_for_status()

            data = response.json()

            # Extract response content
            content = data.get("message", {}).get("content", "")

            # Extract token counts (Ollama provides these)
            prompt_tokens = data.get("prompt_eval_count", 0)
            completion_tokens = data.get("eval_count", 0)
            total_tokens = prompt_tokens + completion_tokens

            # Calculate cost (local model = $0)
            cost = self.calculate_cost(prompt_tokens, completion_tokens)

            # Get finish reason
            finish_reason = "stop" if data.get("done", False) else "length"

            return LLMResponse(
                content=content,
                token_count=total_tokens,
                cost=cost,
                model_used=self.model_name,
                finish_reason=finish_reason,
                metadata={
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "eval_duration_ms": data.get("eval_duration", 0) // 1_000_000,
                },
            )

        except httpx.HTTPStatusError as e:
            logger.error(f"Ollama HTTP error: {e.response.status_code} - {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"Ollama generation error: {e}")
            raise

    async def generate_stream(
        self,
        messages: list[Message],
        temperature: float = 0.7,
        max_tokens: int | None = None,
        **kwargs,
    ):
        """Generate streaming response using Ollama.

        Args:
            messages: Conversation messages
            temperature: Sampling temperature
            max_tokens: Maximum tokens
            **kwargs: Additional parameters

        Yields:
            Chunks of generated content
        """
        try:
            ollama_messages = [{"role": msg.role, "content": msg.content} for msg in messages]

            payload = {
                "model": self.model_name,
                "messages": ollama_messages,
                "stream": True,
                "options": {
                    "temperature": temperature,
                },
            }

            if max_tokens:
                payload["options"]["num_predict"] = max_tokens

            async with self.client.stream(
                "POST",
                f"{self.base_url}/api/chat",
                json=payload,
                timeout=60.0,
            ) as response:
                response.raise_for_status()

                async for line in response.aiter_lines():
                    if line.strip():
                        import json

                        chunk = json.loads(line)

                        if "message" in chunk:
                            content = chunk["message"].get("content", "")
                            if content:
                                yield content

                        if chunk.get("done", False):
                            break

        except httpx.HTTPStatusError as e:
            logger.error(f"Ollama streaming HTTP error: {e.response.status_code}")
            raise RuntimeError(f"Ollama unavailable: {e.response.status_code}")
        except Exception as e:
            logger.error(f"Ollama streaming error: {e}")
            raise RuntimeError(f"Ollama error: {str(e)}")

    async def check_health(self) -> bool:
        """Check if Ollama server and model are available.

        Returns:
            True if healthy, False otherwise
        """
        try:
            # Check server health
            response = await self.client.get(f"{self.base_url}/api/tags")
            response.raise_for_status()

            # Check if our model is available
            data = response.json()
            models = [m.get("name") for m in data.get("models", [])]

            if self.model_name not in models:
                logger.warning(f"Model {self.model_name} not found in Ollama")
                return False

            return True

        except Exception as e:
            logger.error(f"Ollama health check failed: {e}")
            return False

    async def close(self):
        """Close HTTP client."""
        await self.client.aclose()
