"""Unit tests for utility modules."""

from __future__ import annotations

import pytest
import asyncio

from maxpy.utils.retry import RetryPolicy, CircuitBreaker, retry
from maxpy.utils.rate_limit import TokenBucket, SlidingWindowRateLimiter, MultiRateLimiter
from maxpy.utils.fingerprint import FingerprintGenerator, VersionCatalog, ApkBuildFingerprint
from maxpy.exceptions import ConnectionError, ServerError, RateLimitError, ValidationError


class TestRetryPolicy:
    """Tests for RetryPolicy."""

    def test_default_policy(self):
        policy = RetryPolicy()
        assert policy.max_attempts == 5
        assert policy.base_delay == 1.0
        assert policy.exponent == 2.0

    def test_should_retry_connection_error(self):
        policy = RetryPolicy()
        assert policy.should_retry_error(ConnectionError("Failed")) is True

    def test_should_retry_server_error(self):
        policy = RetryPolicy()
        assert policy.should_retry_error(ServerError(status_code=500)) is True

    def test_should_retry_rate_limit(self):
        policy = RetryPolicy()
        assert policy.should_retry_error(RateLimitError(retry_after=1.0)) is True

    def test_should_not_retry_client_error(self):
        policy = RetryPolicy()
        assert policy.should_retry_error(ValidationError("Bad request", status_code=400)) is False

    def test_get_delay(self):
        policy = RetryPolicy(base_delay=1.0, exponent=2.0, jitter=0.0)
        assert policy.get_delay(0) == 1.0
        assert policy.get_delay(1) == 2.0
        assert policy.get_delay(2) == 4.0
        assert policy.get_delay(10) == 60.0  # Capped at max_delay


class TestCircuitBreaker:
    """Tests for CircuitBreaker."""

    @pytest.mark.asyncio
    async def test_closed_state_allows_calls(self):
        breaker = CircuitBreaker(failure_threshold=3)
        assert breaker.state == "closed"

        async def success():
            return "ok"

        result = await breaker.call(success)
        assert result == "ok"
        assert breaker.state == "closed"

    @pytest.mark.asyncio
    async def test_opens_after_threshold(self):
        breaker = CircuitBreaker(failure_threshold=2, recovery_timeout=1.0)

        async def fail():
            raise ConnectionError("Failed")

        # First failure
        with pytest.raises(ConnectionError):
            await breaker.call(fail)
        assert breaker.state == "closed"

        # Second failure - should open
        with pytest.raises(ConnectionError):
            await breaker.call(fail)
        assert breaker.state == "open"

    @pytest.mark.asyncio
    async def test_half_open_after_timeout(self):
        breaker = CircuitBreaker(failure_threshold=1, recovery_timeout=0.1)

        async def fail():
            raise ConnectionError("Failed")

        with pytest.raises(ConnectionError):
            await breaker.call(fail)
        assert breaker.state == "open"

        await asyncio.sleep(0.15)

        # Should be half-open now
        async def success():
            return "ok"

        result = await breaker.call(success)
        assert result == "ok"
        assert breaker.state == "closed"


class TestRetry:
    """Tests for retry function."""

    @pytest.mark.asyncio
    async def test_retry_success_first_try(self):
        call_count = 0

        async def func():
            nonlocal call_count
            call_count += 1
            return "success"

        result = await retry(func, policy=RetryPolicy(max_attempts=3))
        assert result == "success"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_retry_succeeds_after_failures(self):
        call_count = 0

        async def func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("Temporary failure")
            return "success"

        result = await retry(func, policy=RetryPolicy(max_attempts=5, base_delay=0.01))
        assert result == "success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_retry_exhausted(self):
        call_count = 0

        async def func():
            nonlocal call_count
            call_count += 1
            raise ConnectionError("Persistent failure")

        with pytest.raises(ConnectionError):
            await retry(func, policy=RetryPolicy(max_attempts=3, base_delay=0.01))
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_no_retry_on_non_retryable(self):
        call_count = 0

        async def func():
            nonlocal call_count
            call_count += 1
            raise ValidationError("Bad request", status_code=400)

        with pytest.raises(ValidationError):
            await retry(func, policy=RetryPolicy(max_attempts=3))
        assert call_count == 1


class TestTokenBucket:
    """Tests for TokenBucket rate limiter."""

    @pytest.mark.asyncio
    async def test_acquire_tokens(self):
        bucket = TokenBucket(rate=10.0, burst=5)  # 10 tokens/sec, max 5
        await bucket.acquire(3)
        # Should have 2 tokens left
        assert bucket.try_acquire(2) is True
        assert bucket.try_acquire(1) is False

    @pytest.mark.asyncio
    async def test_refill_over_time(self):
        bucket = TokenBucket(rate=100.0, burst=10)  # 100 tokens/sec
        await bucket.acquire(10)  # Empty the bucket
        assert bucket.try_acquire(1) is False

        await asyncio.sleep(0.05)  # 50ms = 5 tokens
        assert bucket.try_acquire(5) is True
        assert bucket.try_acquire(1) is False


class TestSlidingWindowRateLimiter:
    """Tests for SlidingWindowRateLimiter."""

    @pytest.mark.asyncio
    async def test_allows_within_limit(self):
        limiter = SlidingWindowRateLimiter(max_requests=5, window_seconds=1.0)
        for _ in range(5):
            await limiter.acquire()

    @pytest.mark.asyncio
    async def test_blocks_over_limit(self):
        limiter = SlidingWindowRateLimiter(max_requests=2, window_seconds=1.0)
        await limiter.acquire()
        await limiter.acquire()

        # Third request should wait
        import time
        start = time.monotonic()
        await limiter.acquire()
        elapsed = time.monotonic() - start
        assert elapsed >= 0.9  # Should have waited ~1 second


class TestMultiRateLimiter:
    """Tests for MultiRateLimiter."""

    @pytest.mark.asyncio
    async def test_different_limits_per_key(self):
        limiter = MultiRateLimiter()
        limiter.set_limit("api1", max_requests=2, window_seconds=1.0)
        limiter.set_limit("api2", max_requests=10, window_seconds=1.0)

        await limiter.acquire("api1")
        await limiter.acquire("api1")
        # Third should block

        # api2 should have plenty of room
        for _ in range(5):
            assert limiter.try_acquire("api2") is True


class TestFingerprintGenerator:
    """Tests for FingerprintGenerator."""

    def test_default_fingerprint(self):
        gen = FingerprintGenerator()
        fp = gen.generate()
        assert isinstance(fp, bytes)
        assert len(fp) == 32  # SHA256 = 32 bytes

    def test_consistent_device_id(self):
        gen = FingerprintGenerator()
        device_id = "test_device_123"
        fp1 = gen.generate(device_id)
        fp2 = gen.generate(device_id)
        assert fp1 == fp2

    def test_different_device_ids(self):
        gen = FingerprintGenerator()
        fp1 = gen.generate("device_1")
        fp2 = gen.generate("device_2")
        assert fp1 != fp2

    def test_user_agent_generation(self):
        gen = FingerprintGenerator()
        ua = gen.get_user_agent(app_version="2.4.1", build_number=100)
        assert ua["app_version"] == "2.4.1"
        assert ua["build_number"] == 100
        assert ua["device_type"] == "android"
        assert "device_id" in ua


class TestVersionCatalog:
    """Tests for VersionCatalog."""

    def test_get_known_fingerprint(self):
        catalog = VersionCatalog()
        fp = catalog.get_fingerprint("34", "google")
        assert isinstance(fp, ApkBuildFingerprint)
        assert fp.sdk_version == 34
        assert fp.brand == "google"

    def test_fallback_to_default(self):
        catalog = VersionCatalog()
        fp = catalog.get_fingerprint("99", "unknown")
        # Should fallback to default
        assert fp.sdk_version == 34
        assert fp.brand == "google"

    def test_list_versions(self):
        catalog = VersionCatalog()
        versions = catalog.list_versions()
        assert "android-34-google" in versions
        assert "android-33-samsung" in versions