"""Fallback handler for intelligent hybrid error recovery."""

import logging
from abc import ABC, abstractmethod
from collections.abc import Callable
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class FallbackStrategy(Enum):
    """Fallback strategies for error recovery."""

    RETRY = "retry"
    CACHE = "cache"
    SIMPLER_APPROACH = "simpler_approach"
    NOTIFY_USER = "notify_user"


class FallbackResult:
    """Result of a fallback attempt."""

    def __init__(
        self,
        success: bool,
        data: Any = None,
        strategy_used: FallbackStrategy | None = None,
        error_message: str | None = None,
    ):
        self.success = success
        self.data = data
        self.strategy_used = strategy_used
        self.error_message = error_message


class FallbackHandler(ABC):
    """Base class for intelligent hybrid fallback handling."""

    def __init__(self, max_retries: int = 3):
        """Initialize fallback handler.

        Args:
            max_retries: Maximum retry attempts
        """
        self.max_retries = max_retries

    @abstractmethod
    async def execute_with_fallback(self, primary_fn: Callable, *args, **kwargs) -> FallbackResult:
        """Execute function with fallback strategies.

        Args:
            primary_fn: Primary function to execute
            *args: Positional arguments for function
            **kwargs: Keyword arguments for function

        Returns:
            FallbackResult with outcome
        """
        pass

    async def try_retry(self, fn: Callable, max_attempts: int, *args, **kwargs) -> FallbackResult:
        """Retry strategy with exponential backoff.

        Args:
            fn: Function to retry
            max_attempts: Maximum retry attempts
            *args: Function arguments
            **kwargs: Function keyword arguments

        Returns:
            FallbackResult
        """
        import asyncio

        last_error = None
        for attempt in range(max_attempts):
            try:
                result = await fn(*args, **kwargs)
                logger.info(f"Retry succeeded on attempt {attempt + 1}")
                return FallbackResult(
                    success=True,
                    data=result,
                    strategy_used=FallbackStrategy.RETRY,
                )
            except Exception as e:
                last_error = str(e)
                logger.warning(f"Retry attempt {attempt + 1} failed: {e}")

                if attempt < max_attempts - 1:
                    # Exponential backoff: 1s, 2s, 4s, ...
                    wait_time = 2**attempt
                    await asyncio.sleep(wait_time)

        return FallbackResult(
            success=False,
            strategy_used=FallbackStrategy.RETRY,
            error_message=f"All {max_attempts} retry attempts failed: {last_error}",
        )

    def try_cache(self, cache_key: str, cache: dict[str, Any]) -> FallbackResult | None:
        """Try to retrieve from cache.

        Args:
            cache_key: Key to look up
            cache: Cache dictionary

        Returns:
            FallbackResult if cache hit, None otherwise
        """
        if cache_key in cache:
            logger.info(f"Cache hit for key: {cache_key}")
            return FallbackResult(
                success=True,
                data=cache[cache_key],
                strategy_used=FallbackStrategy.CACHE,
            )
        return None

    async def try_simpler_approach(
        self, simpler_fn: Callable | None, *args, **kwargs
    ) -> FallbackResult | None:
        """Try a simpler alternative approach.

        Args:
            simpler_fn: Simpler fallback function
            *args: Function arguments
            **kwargs: Function keyword arguments

        Returns:
            FallbackResult if successful, None if no simpler approach
        """
        if not simpler_fn:
            return None

        try:
            result = await simpler_fn(*args, **kwargs)
            logger.info("Simpler approach succeeded")
            return FallbackResult(
                success=True,
                data=result,
                strategy_used=FallbackStrategy.SIMPLER_APPROACH,
            )
        except Exception as e:
            logger.warning(f"Simpler approach failed: {e}")
            return None

    def notify_user(self, error_message: str) -> FallbackResult:
        """Notify user of failure after all fallbacks exhausted.

        Args:
            error_message: Error message to include

        Returns:
            FallbackResult indicating user notification
        """
        logger.error(f"All fallback strategies failed: {error_message}")
        return FallbackResult(
            success=False,
            strategy_used=FallbackStrategy.NOTIFY_USER,
            error_message=error_message,
        )
