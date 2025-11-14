"""Rate limiter for external API calls."""

import asyncio
import time
import logging
from typing import Dict, Optional
from collections import deque

logger = logging.getLogger(__name__)


class RateLimiter:
    """Token bucket rate limiter for API calls."""

    def __init__(self, calls_per_minute: int = 60, burst_size: Optional[int] = None):
        """Initialize rate limiter.
        
        Args:
            calls_per_minute: Maximum calls per minute
            burst_size: Maximum burst size (default: calls_per_minute)
        """
        self.calls_per_minute = calls_per_minute
        self.burst_size = burst_size or calls_per_minute
        self.tokens = self.burst_size
        self.last_refill = time.time()
        self.lock = asyncio.Lock()
        
        # Track recent calls for metrics
        self.call_history: deque = deque(maxlen=1000)

    async def acquire(self, tokens: int = 1) -> bool:
        """Acquire tokens for API call.
        
        Args:
            tokens: Number of tokens to acquire (default: 1)
            
        Returns:
            True if tokens acquired, False if rate limited
        """
        async with self.lock:
            self._refill_tokens()
            
            if self.tokens >= tokens:
                self.tokens -= tokens
                self.call_history.append(time.time())
                return True
            
            # Rate limited
            logger.warning(
                f"Rate limit reached: {self.tokens}/{self.burst_size} tokens available"
            )
            return False

    async def wait_for_token(self, tokens: int = 1, timeout: Optional[float] = None):
        """Wait until tokens are available.
        
        Args:
            tokens: Number of tokens needed
            timeout: Maximum wait time in seconds
            
        Raises:
            asyncio.TimeoutError: If timeout is reached
        """
        start_time = time.time()
        
        while True:
            if await self.acquire(tokens):
                return
            
            # Check timeout
            if timeout and (time.time() - start_time) > timeout:
                raise asyncio.TimeoutError(
                    f"Rate limit timeout after {timeout}s"
                )
            
            # Wait before retry
            await asyncio.sleep(0.1)

    def _refill_tokens(self):
        """Refill tokens based on time elapsed."""
        now = time.time()
        elapsed = now - self.last_refill
        
        # Refill rate: calls_per_minute / 60 tokens per second
        refill_rate = self.calls_per_minute / 60.0
        new_tokens = elapsed * refill_rate
        
        if new_tokens >= 1:
            self.tokens = min(self.burst_size, self.tokens + new_tokens)
            self.last_refill = now

    def get_stats(self) -> Dict[str, any]:
        """Get rate limiter statistics.
        
        Returns:
            Dict with current tokens, limits, and recent usage
        """
        now = time.time()
        
        # Count calls in last minute
        recent_calls = sum(
            1 for call_time in self.call_history
            if now - call_time < 60
        )
        
        return {
            "available_tokens": int(self.tokens),
            "burst_size": self.burst_size,
            "calls_per_minute": self.calls_per_minute,
            "recent_calls": recent_calls,
            "utilization_pct": (recent_calls / self.calls_per_minute) * 100,
        }


class MultiServiceRateLimiter:
    """Manages rate limiters for multiple services."""

    def __init__(self):
        """Initialize multi-service rate limiter."""
        self.limiters: Dict[str, RateLimiter] = {}

    def add_service(
        self,
        service_name: str,
        calls_per_minute: int,
        burst_size: Optional[int] = None,
    ):
        """Add rate limiter for a service.
        
        Args:
            service_name: Name of service
            calls_per_minute: Max calls per minute
            burst_size: Optional burst size
        """
        self.limiters[service_name] = RateLimiter(calls_per_minute, burst_size)
        logger.info(
            f"Added rate limiter for {service_name}: "
            f"{calls_per_minute} calls/min"
        )

    async def acquire(self, service_name: str, tokens: int = 1) -> bool:
        """Acquire tokens for a service.
        
        Args:
            service_name: Name of service
            tokens: Number of tokens
            
        Returns:
            True if acquired, False if rate limited
        """
        if service_name not in self.limiters:
            logger.warning(f"No rate limiter for {service_name}, allowing call")
            return True
        
        return await self.limiters[service_name].acquire(tokens)

    async def wait_for_token(
        self,
        service_name: str,
        tokens: int = 1,
        timeout: Optional[float] = None,
    ):
        """Wait for tokens for a service.
        
        Args:
            service_name: Name of service
            tokens: Number of tokens needed
            timeout: Max wait time
            
        Raises:
            asyncio.TimeoutError: If timeout reached
        """
        if service_name not in self.limiters:
            return
        
        await self.limiters[service_name].wait_for_token(tokens, timeout)

    def get_all_stats(self) -> Dict[str, Dict[str, any]]:
        """Get stats for all services.
        
        Returns:
            Dict mapping service name to stats
        """
        return {
            name: limiter.get_stats()
            for name, limiter in self.limiters.items()
        }
