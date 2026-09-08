from __future__ import annotations

from typing import Any
from ..auth.base import AuthFlow, AuthResult
from ..enums import AuthType
from ..types.user import User, Login2Response
from ..exceptions import SessionExpiredError, AuthError
from ..transport.tcp import TCPTransport, TCPOpcode


class SessionTokenAuthFlow(AuthFlow):
    """Direct session token authentication (for restored sessions)."""

    @property
    def auth_type(self) -> AuthType:
        return AuthType.SESSION_TOKEN

    def __init__(self, config: Any):
        super().__init__(config)
        self._token = config.token

    async def authenticate(self, transport: TCPTransport) -> AuthResult:
        """Authenticate with existing session token."""
        if not self._token:
            raise AuthError("No session token provided")

        # Use LOGIN2 to restore session
        return await self.refresh(transport, self._token)

    async def refresh(self, transport: TCPTransport, token: str) -> AuthResult:
        """Refresh session with token."""
        seq = await transport.send_packet(
            opcode=TCPOpcode.LOGIN2,
            payload={"token": token},
        )

        header, payload = await transport.receive()

        if header.opcode == TCPOpcode.ERROR:
            error = payload.get("error", "Refresh failed")
            if error in ("FAIL_LOGIN_TOKEN", "FAIL_LOGOUT_ALL"):
                raise SessionExpiredError(error)
            raise AuthError(error)

        login_resp = Login2Response(**payload)
        return AuthResult(
            success=True,
            token=login_resp.token,
            user=login_resp.user,
        )

    async def logout(self, transport: TCPTransport, token: str) -> bool:
        """Logout current session."""
        try:
            seq = await transport.send_packet(
                opcode=TCPOpcode.LOGOUT,
                payload={"token": token},
            )
            header, payload = await transport.receive()
            return header.opcode != TCPOpcode.ERROR
        except Exception:
            return False