"""Embeddings provider abstraction for local and remote embedding models."""

import logging
from typing import List

import httpx

logger = logging.getLogger(__name__)


class EmbeddingsProvider:
    """Abstract base class for embeddings providers."""

    def embed(self, texts: List[str]) -> List[List[float]]:
        """Generate embedding vectors for the given texts.

        Args:
            texts: List of strings to embed

        Returns:
            List of embedding vectors (one per input text)

        Raises:
            NotImplementedError: If not implemented by subclass
        """
        raise NotImplementedError("Subclasses must implement embed()")


class RemoteEmbeddingsProvider(EmbeddingsProvider):
    """Remote embeddings provider using OpenRouter API.

    Uses OpenRouter's /embeddings endpoint with OpenAI-compatible format.
    Supports text-embedding-3-small and other embedding models.
    """

    def __init__(
        self,
        api_key: str,
        model: str = "openai/text-embedding-3-small",
        base_url: str = "https://openrouter.ai/api/v1",
        timeout: int = 30,
    ):
        """Initialize remote embeddings provider.

        Args:
            api_key: OpenRouter API key
            model: Model identifier (default: openai/text-embedding-3-small)
            base_url: Base URL for OpenRouter API
            timeout: Request timeout in seconds
        """
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.client = httpx.Client(timeout=timeout)

        logger.info(f"Initialized RemoteEmbeddingsProvider with model: {model}")

    def embed(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings using OpenRouter API.

        Args:
            texts: List of strings to embed

        Returns:
            List of embedding vectors

        Raises:
            Exception: If API request fails
        """
        if not texts:
            return []

        try:
            response = self.client.post(
                f"{self.base_url}/embeddings",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={"model": self.model, "input": texts},
            )

            response.raise_for_status()
            data = response.json()

            # Extract embeddings from response
            # Format: {"data": [{"embedding": [...]}, ...]}
            embeddings = [item["embedding"] for item in data["data"]]

            logger.debug(f"Generated {len(embeddings)} embeddings via {self.model}")
            return embeddings

        except httpx.HTTPError as e:
            logger.error(f"HTTP error calling embeddings API: {e}")
            raise Exception(f"Failed to generate embeddings: {e}")
        except KeyError as e:
            logger.error(f"Unexpected API response format: {e}")
            raise Exception(f"Invalid embeddings API response: {e}")
        except Exception as e:
            logger.error(f"Error generating embeddings: {e}")
            raise

    def __del__(self):
        """Cleanup HTTP client on deletion."""
        try:
            self.client.close()
        except Exception:
            pass


class MockEmbeddingsProvider(EmbeddingsProvider):
    """Mock embeddings provider for testing without external dependencies.

    Generates deterministic random vectors based on text hash.
    Useful for development and testing when embeddings are not critical.
    """

    def __init__(self, dimensions: int = 384):
        """Initialize mock provider.

        Args:
            dimensions: Embedding vector dimensions (default: 384 like MiniLM)
        """
        self.dimensions = dimensions
        logger.warning(
            f"Using MockEmbeddingsProvider ({dimensions}D) - not suitable for production!"
        )

    def embed(self, texts: List[str]) -> List[List[float]]:
        """Generate mock embeddings based on text hash.

        Args:
            texts: List of strings to embed

        Returns:
            List of deterministic pseudo-random vectors
        """
        import random

        embeddings = []
        for text in texts:
            # Use text hash as seed for deterministic results
            random.seed(hash(text) % (2**32))
            embedding = [random.random() for _ in range(self.dimensions)]
            embeddings.append(embedding)

        logger.debug(f"Generated {len(embeddings)} mock embeddings")
        return embeddings
