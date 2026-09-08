"""Unit tests for exceptions."""

from __future__ import annotations

import builtins
import pytest

from maxpy.exceptions import (
    MaxError,
    ConfigError,
    AuthError,
    InvalidCredentialsError,
    TwoFactorRequiredError,
    SessionExpiredError,
    ConnectionError,
    TransportError,
    ReconnectFailedError,
    APIError,
    RateLimitError,
    NotFoundError,
    ForbiddenError,
    ValidationError,
    ServerError,
    FileError,
    UploadError,
    DownloadError,
    wrap_error,
)


class TestMaxError:
    """Tests for base MaxError."""

    def test_basic_error(self):
        err = MaxError("Test error")
        assert str(err) == "Test error"
        assert err.message == "Test error"
        assert err.request_id is None

    def test_error_with_context(self):
        err = MaxError(
            "Test error",
            request_id="req_123",
            endpoint="/api/test",
            transport="tcp",
        )
        assert "req_123" in str(err)
        assert "/api/test" in str(err)
        assert "tcp" in str(err)
        assert err.request_id == "req_123"
        assert err.endpoint == "/api/test"
        assert err.transport == "tcp"

    def test_error_with_original(self):
        original = ValueError("Original error")
        err = MaxError("Wrapped error", original_error=original)
        assert err.original_error is original


class TestAuthErrors:
    """Tests for authentication errors."""

    def test_invalid_credentials(self):
        err = InvalidCredentialsError("Invalid phone")
        assert isinstance(err, AuthError)
        assert isinstance(err, MaxError)

    def test_two_factor_required(self):
        err = TwoFactorRequiredError(hint="Enter password")
        assert err.hint == "Enter password"
        assert "Two-factor authentication required" in str(err)

    def test_session_expired(self):
        err = SessionExpiredError("Token expired")
        assert isinstance(err, AuthError)


class TestConnectionErrors:
    """Tests for connection errors."""

    def test_transport_error(self):
        err = TransportError("Connection failed", endpoint="tcp://host:443", transport="tcp")
        assert isinstance(err, ConnectionError)

    def test_reconnect_failed(self):
        err = ReconnectFailedError(attempts=5, last_error=ConnectionError("Failed"))
        assert err.attempts == 5
        assert err.last_error is not None


class TestAPIErrors:
    """Tests for API errors."""

    def test_rate_limit_error(self):
        err = RateLimitError(retry_after=5.0, status_code=429)
        assert err.retry_after == 5.0
        assert err.status_code == 429

    def test_not_found_error(self):
        err = NotFoundError("Not found", status_code=404)
        assert err.status_code == 404

    def test_forbidden_error(self):
        err = ForbiddenError("Forbidden", status_code=403)
        assert err.status_code == 403

    def test_validation_error(self):
        err = ValidationError("Invalid input", status_code=400)
        assert err.status_code == 400

    def test_server_error(self):
        err = ServerError(status_code=500)
        assert err.status_code == 500


class TestWrapError:
    """Tests for wrap_error function."""

    def test_wraps_timeout_error(self):
        original = TimeoutError("Timeout")
        wrapped = wrap_error(original, endpoint="/api/test", transport="tcp")
        assert isinstance(wrapped, ConnectionError)
        assert "Timeout" in str(wrapped)
        assert wrapped.endpoint == "/api/test"
        assert wrapped.transport == "tcp"

    def test_wraps_builtin_connection_error(self):
        # Python's built-in ConnectionError - need to use fully qualified name
        original = builtins.ConnectionError("Connection failed")
        wrapped = wrap_error(original)
        assert isinstance(wrapped, TransportError)

    def test_wraps_os_error(self):
        original = OSError("Network unreachable")
        wrapped = wrap_error(original)
        assert isinstance(wrapped, TransportError)

    def test_wraps_generic_error(self):
        original = RuntimeError("Something went wrong")
        wrapped = wrap_error(original)
        assert isinstance(wrapped, MaxError)
        assert "Something went wrong" in str(wrapped)

    def test_passes_through_max_error(self):
        original = MaxError("Already a MaxError", request_id="req_1")
        wrapped = wrap_error(original, request_id="req_2")
        assert wrapped is original
        assert wrapped.request_id == "req_2"  # Should update