from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Protocol
from dataclasses import dataclass
from ..types.user import User, LoginResponse, Login2Response, HandshakeResponse, RegisterTokenResponse
from ..types.common import JSONDict
from ..enums import AuthType
from ..exceptions import AuthError, TwoFactorRequiredError, SessionExpiredError, QRCodeExpiredError, QRCodeNotScannedError, RegistrationRequiredError


class SmsCodeProvider(Protocol):
    """Protocol for SMS code providers."""

    async def get_code(self, phone: str) -> str:
        """Get SMS code for phone number."""
        ...


class QrHandler(Protocol):
    """Protocol for QR code handlers."""

    async def show_qr(self, qr_url: str) -> None:
        """Display QR code to user."""
        ...


class PasswordProvider(Protocol):
    """Protocol for 2FA password providers."""

    async def get_password(self, hint: str | None = None) -> str:
        """Get 2FA password."""
        ...


class EmailCodeProvider(Protocol):
    """Protocol for email code providers."""

    async def get_code(self, email: str) -> str:
        """Get email verification code."""
        ...


@dataclass
class AuthResult:
    """Result of authentication."""

    success: bool
    token: str | None = None
    user: User | None = None
    requires_2fa: bool = False
    requires_registration: bool = False
    register_token: str | None = None
    qr_url: str | None = None
    track_id: str | None = None
    hint: str | None = None
    error: str | None = None


class AuthFlow(ABC):
    """Abstract authentication flow."""

    def __init__(self, config: Any):
        self.config = config

    @property
    @abstractmethod
    def auth_type(self) -> AuthType:
        pass

    @abstractmethod
    async def authenticate(self, transport: Any) -> AuthResult:
        """Perform authentication."""
        pass

    @abstractmethod
    async def refresh(self, transport: Any, token: str) -> AuthResult:
        """Refresh authentication."""
        pass

    @abstractmethod
    async def logout(self, transport: Any, token: str) -> bool:
        """Logout."""
        pass


class AuthService:
    """High-level authentication service."""

    def __init__(self, transport: Any, auth_flow: AuthFlow):
        self.transport = transport
        self.auth_flow = auth_flow

    async def login(self) -> AuthResult:
        return await self.auth_flow.authenticate(self.transport)

    async def relogin(self, token: str) -> AuthResult:
        return await self.auth_flow.refresh(self.transport, token)

    async def logout(self, token: str) -> bool:
        return await self.auth_flow.logout(self.transport, token)

    async def check_password(self, track_id: str, password: str) -> AuthResult:
        """Check 2FA password."""
        # This is transport-specific, implemented in subclasses
        raise NotImplementedError

    async def request_sms_code(self, phone: str) -> str:
        """Request SMS code."""
        raise NotImplementedError

    async def send_sms_code(self, phone: str, code: str) -> AuthResult:
        """Send SMS code."""
        raise NotImplementedError

    async def request_qr(self) -> str:
        """Request QR code."""
        raise NotImplementedError

    async def check_qr(self, track_id: str) -> AuthResult:
        """Check QR status."""
        raise NotImplementedError

    async def confirm_qr(self, track_id: str) -> AuthResult:
        """Confirm QR login."""
        raise NotImplementedError

    async def set_2fa(self, password: str, email: str | None = None, hint: str | None = None) -> bool:
        """Set 2FA password."""
        raise NotImplementedError

    async def remove_2fa(self, password: str) -> bool:
        """Remove 2FA password."""
        raise NotImplementedError

    async def change_password(self, old_password: str, new_password: str) -> bool:
        """Change 2FA password."""
        raise NotImplementedError