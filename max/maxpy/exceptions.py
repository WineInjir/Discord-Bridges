from __future__ import annotations

from typing import Any, Optional
from datetime import datetime


class MaxError(Exception):
    """Base exception for all MaxPy errors."""

    def __init__(
        self,
        message: str,
        *,
        request_id: Optional[str] = None,
        endpoint: Optional[str] = None,
        transport: Optional[str] = None,
        original_error: Optional[Exception] = None,
    ):
        super().__init__(message)
        self.message = message
        self.request_id = request_id
        self.endpoint = endpoint
        self.transport = transport
        self.original_error = original_error
        self.timestamp = datetime.utcnow()

    def __str__(self) -> str:
        parts = [self.message]
        if self.request_id:
            parts.append(f"request_id={self.request_id}")
        if self.endpoint:
            parts.append(f"endpoint={self.endpoint}")
        if self.transport:
            parts.append(f"transport={self.transport}")
        return " | ".join(parts)

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}({self.message!r}, "
            f"request_id={self.request_id!r}, endpoint={self.endpoint!r}, "
            f"transport={self.transport!r})"
        )


class ConfigError(MaxError):
    """Configuration error."""


class AuthError(MaxError):
    """Authentication/authorization error."""


class InvalidCredentialsError(AuthError):
    """Invalid credentials provided."""


class TwoFactorRequiredError(AuthError):
    """Two-factor authentication required."""

    def __init__(
        self,
        message: str = "Two-factor authentication required",
        *,
        hint: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(message, **kwargs)
        self.hint = hint


class SessionExpiredError(AuthError):
    """Session has expired, re-authentication required."""


class QRCodeExpiredError(AuthError):
    """QR code has expired."""


class QRCodeNotScannedError(AuthError):
    """QR code not scanned yet."""


class RegistrationRequiredError(AuthError):
    """Account registration required."""


class ConnectionError(MaxError):
    """Connection-related error."""


class TransportError(ConnectionError):
    """Transport layer error."""


class ReconnectFailedError(ConnectionError):
    """Failed to reconnect after max attempts."""

    def __init__(
        self,
        message: str = "Failed to reconnect",
        *,
        attempts: int,
        last_error: Optional[Exception] = None,
        **kwargs,
    ):
        super().__init__(message, **kwargs)
        self.attempts = attempts
        self.last_error = last_error


class PingTimeoutError(ConnectionError):
    """Ping/keepalive timeout."""


class APIError(MaxError):
    """API error response from server."""

    def __init__(
        self,
        message: str,
        *,
        code: Optional[int] = None,
        error_code: Optional[str] = None,
        status_code: Optional[int] = None,
        response_data: Optional[dict[str, Any]] = None,
        **kwargs,
    ):
        super().__init__(message, **kwargs)
        self.code = code
        self.error_code = error_code
        self.status_code = status_code
        self.response_data = response_data


class RateLimitError(APIError):
    """Rate limit exceeded."""

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        *,
        retry_after: Optional[float] = None,
        **kwargs,
    ):
        super().__init__(message, **kwargs)
        self.retry_after = retry_after


class NotFoundError(APIError):
    """Resource not found (404)."""


class ForbiddenError(APIError):
    """Access forbidden (403)."""


class ValidationError(APIError):
    """Request validation failed (400)."""


class ServerError(APIError):
    """Server error (500+ status codes)."""

    def __init__(
        self,
        message: str = "Server error",
        *,
        status_code: int,
        **kwargs,
    ):
        super().__init__(message, status_code=status_code, **kwargs)


class FileError(MaxError):
    """File operation error."""


class UploadError(FileError):
    """File upload error."""


class DownloadError(FileError):
    """File download error."""


class FileValidationError(FileError):
    """File validation error (type, size, format)."""


class DispatchError(MaxError):
    """Event dispatch error."""


class HandlerError(DispatchError):
    """Error in event handler."""


class FilterError(DispatchError):
    """Error in event filter."""


def wrap_error(
    error: Exception,
    *,
    request_id: Optional[str] = None,
    endpoint: Optional[str] = None,
    transport: Optional[str] = None,
) -> MaxError:
    """Wrap an arbitrary exception into MaxError hierarchy."""
    if isinstance(error, MaxError):
        if request_id:
            error.request_id = request_id
        if endpoint:
            error.endpoint = endpoint
        if transport:
            error.transport = transport
        return error

    if isinstance(error, TimeoutError):
        return ConnectionError(
            f"Timeout: {error}",
            request_id=request_id,
            endpoint=endpoint,
            transport=transport,
            original_error=error,
        )
    if isinstance(error, ConnectionError):
        return TransportError(
            f"Connection error: {error}",
            request_id=request_id,
            endpoint=endpoint,
            transport=transport,
            original_error=error,
        )
    if isinstance(error, OSError):
        return TransportError(
            f"OS error: {error}",
            request_id=request_id,
            endpoint=endpoint,
            transport=transport,
            original_error=error,
        )

    return MaxError(
        f"Unexpected error: {error}",
        request_id=request_id,
        endpoint=endpoint,
        transport=transport,
        original_error=error,
    )