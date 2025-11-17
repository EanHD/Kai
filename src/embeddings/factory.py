"""Factory for creating embeddings providers based on configuration."""

import logging
import os
from typing import Optional

from src.embeddings.provider import EmbeddingsProvider, MockEmbeddingsProvider, RemoteEmbeddingsProvider

logger = logging.getLogger(__name__)


def get_embeddings_provider() -> Optional[EmbeddingsProvider]:
    """Get embeddings provider based on environment configuration.

    Checks for OPENROUTER_API_KEY and creates RemoteEmbeddingsProvider if available.
    Falls back to MockEmbeddingsProvider for development/testing.
    Returns None if embeddings should be disabled.

    Environment variables:
        OPENROUTER_API_KEY: API key for OpenRouter
        EMBEDDINGS_MODEL: Model to use (default: openai/text-embedding-3-small)
        EMBEDDINGS_ENABLED: Set to "false" to disable embeddings entirely

    Returns:
        EmbeddingsProvider instance or None if disabled
    """
    # Check if explicitly disabled
    if os.getenv("EMBEDDINGS_ENABLED", "true").lower() == "false":
        logger.info("Embeddings disabled via EMBEDDINGS_ENABLED=false")
        return None

    # Try to use remote provider (OpenRouter)
    api_key = os.getenv("OPENROUTER_API_KEY")
    if api_key:
        model = os.getenv("EMBEDDINGS_MODEL", "openai/text-embedding-3-small")
        try:
            provider = RemoteEmbeddingsProvider(api_key=api_key, model=model)
            logger.info(f"Using RemoteEmbeddingsProvider with model: {model}")
            return provider
        except Exception as e:
            logger.warning(f"Failed to initialize RemoteEmbeddingsProvider: {e}")
            # Fall through to mock provider

    # Fall back to mock provider for development
    logger.warning(
        "No OPENROUTER_API_KEY found - using MockEmbeddingsProvider. "
        "Set OPENROUTER_API_KEY to use real embeddings via OpenRouter."
    )
    return MockEmbeddingsProvider(dimensions=1536)  # Match text-embedding-3-small dimensions


# Singleton instance
_provider_instance: Optional[EmbeddingsProvider] = None


def get_shared_embeddings_provider() -> Optional[EmbeddingsProvider]:
    """Get shared singleton embeddings provider instance.

    Returns:
        Shared EmbeddingsProvider instance or None
    """
    global _provider_instance
    if _provider_instance is None:
        _provider_instance = get_embeddings_provider()
    return _provider_instance
