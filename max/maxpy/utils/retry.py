from __future__ import annotations

import asyncio
import random
import time
from typing import Callable, TypeVar, Any, Awaitable
from dataclasses import dataclass
from collections.abc import Coroutine

from ..exceptions import (
    MaxError,
    ConnectionError,
    ServerError,
    RateLimitError,
    APIError,
)

T = TypeVar("T")


@dataclass
class RetryPolicy:
    """Retry policy configuration."""

    max_attempts: int = 5
    base_delay: float = 1.0
    max_delay: float = 60.0
    exponent: float = 2.0
    jitter: float = 0.1
    retry_on: tuple[type[Exception], ...] = (
        ConnectionError,
        TimeoutError,
        ServerError,
        RateLimitError,
    )
    should_retry: Callable[[Exception], bool] | None = None

    def should_retry_error(self, error: Exception) -> bool:
        """Check if error should trigger retry."""
        if self.should_retry:
            return self.should_retry(error)

        # Don't retry client errors (4xx except 429)
        if isinstance(error, APIError):
            if error.status_code and 400 <= error.status_code < 500:
                if error.status_code != 429:
                    return False
            if error.status_code and error.status_code >= 500:
                return True

        return isinstance(error, self.retry_on)

    def get_delay(self, attempt: int) -> float:
        """Calculate delay for attempt."""
        delay = min(self.base_delay * (self.exponent ** attempt), self.max_delay)
        jitter_range = delay * self.jitter
        return delay + random.uniform(-jitter_range, jitter_range)


class CircuitBreaker:
    """Circuit breaker for preventing cascade failures."""

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        half_open_max_calls: int = 3,
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls

        self._state = "closed"  # closed, open, half_open
        self._failure_count = 0
        self._last_failure_time: float | None = None
        self._half_open_calls = 0
        self._lock = asyncio.Lock()

    @property
    def state(self) -> str:
        return self._state

    async def call(self, func: Callable[..., Awaitable[T]], *args, **kwargs) -> T:
        """Execute function with circuit breaker."""
        async with self._lock:
            if self._state == "open":
                if time.time() - self._last_failure_time >= self.recovery_timeout:
                    self._state = "half_open"
                    self._half_open_calls = 0
                else:
                    raise ConnectionError("Circuit breaker is open")

            if self._state == "half_open" and self._half_open_calls >= self.half_open_max_calls:
                raise ConnectionError("Circuit breaker half-open limit reached")

        try:
            result = await func(*args, **kwargs)
            await self._on_success()
            return result
        except Exception as e:
            await self._on_failure()
            raise

    async def _on_success(self) -> None:
        async with self._lock:
            self._failure_count = 0
            if self._state == "half_open":
                self._state = "closed"
            self._half_open_calls = 0

    async def _on_failure(self) -> None:
        async with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()

            if self._state == "half_open":
                self._state = "open"
            elif self._failure_count >= self.failure_threshold:
                self._state = "open"


async def retry(
    func: Callable[..., Awaitable[T]],
    *args,
    policy: RetryPolicy | None = None,
    circuit_breaker: CircuitBreaker | None = None,
    **kwargs,
) -> T:
    """Execute function with retry policy."""
    policy = policy or RetryPolicy()
    last_error: Exception | None = None

    for attempt in range(policy.max_attempts):
        try:
            if circuit_breaker:
                return await circuit_breaker.call(func, *args, **kwargs)
            return await func(*args, **kwargs)
        except Exception as e:
            last_error = e
            if not policy.should_retry_error(e):
                raise

            if attempt < policy.max_attempts - 1:
                delay = policy.get_delay(attempt)
                await asyncio.sleep(delay)

    raise last_error or MaxError("Retry exhausted")