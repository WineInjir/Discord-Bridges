from __future__ import annotations

from typing import Any
from ..auth.base import AuthFlow, AuthResult, SmsCodeProvider, QrHandler, PasswordProvider
from ..enums import AuthType
from ..types.user import User
from ..exceptions import AuthError, SessionExpiredError


class RESTAuthFlow(AuthFlow):
    """Authentication flow for Green-API REST (instance token)."""

    @property
    def auth_type(self) -> AuthType:
        return AuthType.INSTANCE_TOKEN

    async def authenticate(self, transport: Any) -> AuthResult:
        """REST auth is just setting credentials - no actual flow."""
        # For REST, the transport just needs the credentials set
        # The actual "auth" is done by Green-API on their side
        return AuthResult(
            success=True,
            token=f"{self.config.id_instance}:{self.config.api_token_instance}",
            user=None,  # User info fetched separately
        )

    async def refresh(self, transport: Any, token: str) -> AuthResult:
        """No refresh needed for instance token."""
        return AuthResult(
            success=True,
            token=token,
            user=None,
        )

    async def logout(self, transport: Any, token: str) -> bool:
        """Logout from Green-API instance."""
        try:
            # Call logout endpoint
            await transport.request("GET", f"waInstance{{idInstance}}/logout/{{token}}")
            return True
        except Exception:
            return False