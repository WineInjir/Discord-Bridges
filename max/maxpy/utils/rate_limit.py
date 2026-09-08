from __future__ import annotations

import asyncio
import time
from typing import Optional
from dataclasses import dataclass, field
from collections import deque


@dataclass
class RateLimit:
    """Rate limit configuration."""

    requests: int  # Max requests
    window: float  # Time window in seconds


class TokenBucket:
    """Token bucket rate limiter."""

    def __init__(self, rate: float, burst: int):
        """
        Args:
            rate: Tokens per second
            burst: Maximum bucket size
        """
        self.rate = rate
        self.burst = burst
        self._tokens = float(burst)
        self._last_update = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self, tokens: int = 1) -> None:
        """Acquire tokens, waiting if necessary."""
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_update
            self._tokens = min(self.burst, self._tokens + elapsed * self.rate)
            self._last_update = now

            if self._tokens >= tokens:
                self._tokens -= tokens
                return

            # Need to wait
            deficit = tokens - self._tokens
            wait_time = deficit / self.rate
            self._tokens = 0
            self._last_update = now + wait_time

        await asyncio.sleep(wait_time)

    def try_acquire(self, tokens: int = 1) -> bool:
        """Try to acquire tokens without waiting."""
        now = time.monotonic()
        elapsed = now - self._last_update
        self._tokens = min(self.burst, self._tokens + elapsed * self.rate)
        self._last_update = now

        if self._tokens >= tokens:
            self._tokens -= tokens
            return True
        return False


class SlidingWindowRateLimiter:
    """Sliding window rate limiter."""

    def __init__(self, max_requests: int, window_seconds: float):
        self.max_requests = max_requests
        self.window = window_seconds
        self._requests: deque[float] = deque()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Acquire permission, waiting if necessary."""
        async with self._lock:
            now = time.monotonic()
            # Remove old requests
            cutoff = now - self.window
            while self._requests and self._requests[0] < cutoff:
                self._requests.popleft()

            if len(self._requests) < self.max_requests:
                self._requests.append(now)
                return

            # Need to wait for oldest request to expire
            wait_time = self._requests[0] + self.window - now

        await asyncio.sleep(wait_time)
        # Retry after waiting
        await self.acquire()

    def try_acquire(self) -> bool:
        """Try to acquire without waiting."""
        now = time.monotonic()
        cutoff = now - self.window
        while self._requests and self._requests[0] < cutoff:
            self._requests.popleft()

        if len(self._requests) < self.max_requests:
            self._requests.append(now)
            return True
        return False


class MultiRateLimiter:
    """Multiple rate limiters for different endpoints."""

    def __init__(self):
        self._limiters: dict[str, SlidingWindowRateLimiter] = {}
        self._default: SlidingWindowRateLimiter | None = None
        self._lock = asyncio.Lock()

    def set_limit(self, key: str, max_requests: int, window_seconds: float) -> None:
        """Set rate limit for key."""
        self._limiters[key] = SlidingWindowRateLimiter(max_requests, window_seconds)

    def set_default(self, max_requests: int, window_seconds: float) -> None:
        """Set default rate limit."""
        self._default = SlidingWindowRateLimiter(max_requests, window_seconds)

    async def acquire(self, key: str = "default") -> None:
        """Acquire permission for key."""
        limiter = self._limiters.get(key) or self._default
        if limiter:
            await limiter.acquire()

    def try_acquire(self, key: str = "default") -> bool:
        """Try to acquire without waiting."""
        limiter = self._limiters.get(key) or self._default
        if limiter:
            return limiter.try_acquire()
        return True


# Global rate limiter instance
_global_limiter: MultiRateLimiter | None = None


def get_global_limiter() -> MultiRateLimiter:
    """Get global rate limiter."""
    global _global_limiter
    if _global_limiter is None:
        _global_limiter = MultiRateLimiter()
    return _global_limiter