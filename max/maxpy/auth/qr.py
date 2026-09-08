from __future__ import annotations

import asyncio
from typing import Any
from ..auth.base import AuthFlow, AuthResult, QrHandler, PasswordProvider
from ..enums import AuthType
from ..types.user import User, LoginResponse
from ..exceptions import AuthError, TwoFactorRequiredError, QRCodeExpiredError, QRCodeNotScannedError
from ..transport.tcp import TCPTransport, TCPOpcode


class QrAuthFlow(AuthFlow):
    """QR code authentication flow for TCP/WebSocket transport."""

    @property
    def auth_type(self) -> AuthType:
        return AuthType.QR

    def __init__(self, config: Any):
        super().__init__(config)
        self._qr_handler: QrHandler | None = None
        self._password_provider: PasswordProvider | None = None

    def set_qr_handler(self, handler: QrHandler) -> None:
        self._qr_handler = handler

    def set_password_provider(self, provider: PasswordProvider) -> None:
        self._password_provider = provider

    async def authenticate(self, transport: TCPTransport) -> AuthResult:
        """Perform full QR authentication flow."""
        if not self._qr_handler:
            raise AuthError("QR handler not set")

        # Step 1: Request QR code
        qr_url, track_id = await self._request_qr(transport)

        # Step 2: Show QR to user
        await self._qr_handler.show_qr(qr_url)

        # Step 3: Poll for QR status
        result = await self._poll_qr(transport, track_id)

        if result.requires_2fa:
            return await self._handle_2fa(transport, result.track_id)

        return result

    async def _request_qr(self, transport: TCPTransport) -> tuple[str, str]:
        """Request QR code."""
        seq = await transport.send_packet(
            opcode=TCPOpcode.GET_QR,
            payload={},
        )

        header, payload = await transport.receive()

        if header.opcode == TCPOpcode.ERROR:
            raise AuthError(payload.get("error", "Failed to get QR code"))

        qr_url = payload.get("qrUrl") or payload.get("qr_url")
        track_id = payload.get("trackId") or payload.get("track_id")

        if not qr_url or not track_id:
            raise AuthError("Invalid QR response")

        return qr_url, track_id

    async def _poll_qr(self, transport: TCPTransport, track_id: str) -> AuthResult:
        """Poll QR status until scanned/confirmed."""
        max_attempts = 60  # ~2 minutes at 2s intervals
        interval = 2

        for attempt in range(max_attempts):
            await asyncio.sleep(interval)

            seq = await transport.send_packet(
                opcode=TCPOpcode.GET_QR_STATUS,
                payload={"trackId": track_id},
            )

            header, payload = await transport.receive()

            if header.opcode == TCPOpcode.ERROR:
                error = payload.get("error", "QR check failed")
                if error == "QR_EXPIRED":
                    raise QRCodeExpiredError("QR code expired")
                raise AuthError(error)

            status = payload.get("status")

            if status == "SCANNED":
                # QR scanned, now confirm
                return await self._confirm_qr(transport, track_id)

            elif status == "EXPIRED":
                raise QRCodeExpiredError("QR code expired")

            # Still waiting for scan
            if attempt % 10 == 0:
                # Could notify handler of waiting status
                pass

        raise QRCodeExpiredError("QR code polling timeout")

    async def _confirm_qr(self, transport: TCPTransport, track_id: str) -> AuthResult:
        """Confirm QR login."""
        seq = await transport.send_packet(
            opcode=TCPOpcode.LOGIN_BY_QR,
            payload={"trackId": track_id},
        )

        header, payload = await transport.receive()

        if header.opcode == TCPOpcode.ERROR:
            error = payload.get("error", "QR confirmation failed")
            if error == "FAIL_LOGIN_PASSWORD":
                return AuthResult(
                    success=False,
                    requires_2fa=True,
                    track_id=track_id,
                    hint=payload.get("hint"),
                    error=error,
                )
            raise AuthError(error)

        login_resp = LoginResponse(**payload)
        return AuthResult(
            success=True,
            token=login_resp.token,
            user=login_resp.user,
        )

    async def _handle_2fa(self, transport: TCPTransport, track_id: str) -> AuthResult:
        """Handle 2FA password after QR."""
        if not self._password_provider:
            raise TwoFactorRequiredError("2FA required but no password provider set")

        password = await self._password_provider.get_password(None)

        seq = await transport.send_packet(
            opcode=TCPOpcode.AUTH_LOGIN_CHECK_PASSWORD,
            payload={"trackId": track_id, "password": password},
        )

        header, payload = await transport.receive()

        if header.opcode == TCPOpcode.ERROR:
            raise AuthError(payload.get("error", "Invalid password"))

        login_resp = LoginResponse(**payload)
        return AuthResult(
            success=True,
            token=login_resp.token,
            user=login_resp.user,
        )

    async def refresh(self, transport: TCPTransport, token: str) -> AuthResult:
        """Refresh session (login2)."""
        seq = await transport.send_packet(
            opcode=TCPOpcode.LOGIN2,
            payload={"token": token},
        )

        header, payload = await transport.receive()

        if header.opcode == TCPOpcode.ERROR:
            error = payload.get("error", "Refresh failed")
            if error in ("FAIL_LOGIN_TOKEN", "FAIL_LOGOUT_ALL"):
                from ..exceptions import SessionExpiredError
                raise SessionExpiredError(error)
            raise AuthError(error)

        from ..types.user import Login2Response
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

    async def check_password(self, transport: TCPTransport, track_id: str, password: str) -> AuthResult:
        """Check 2FA password."""
        seq = await transport.send_packet(
            opcode=TCPOpcode.AUTH_LOGIN_CHECK_PASSWORD,
            payload={"trackId": track_id, "password": password},
        )

        header, payload = await transport.receive()

        if header.opcode == TCPOpcode.ERROR:
            raise AuthError(payload.get("error", "Invalid password"))

        login_resp = LoginResponse(**payload)
        return AuthResult(
            success=True,
            token=login_resp.token,
            user=login_resp.user,
        )

    async def request_qr(self, transport: TCPTransport) -> str:
        """Request QR code and return URL."""
        qr_url, _ = await self._request_qr(transport)
        return qr_url

    async def check_qr(self, transport: TCPTransport, track_id: str) -> AuthResult:
        """Check QR status once."""
        seq = await transport.send_packet(
            opcode=TCPOpcode.GET_QR_STATUS,
            payload={"trackId": track_id},
        )

        header, payload = await transport.receive()

        if header.opcode == TCPOpcode.ERROR:
            raise AuthError(payload.get("error", "QR check failed"))

        status = payload.get("status")

        if status == "SCANNED":
            return await self._confirm_qr(transport, track_id)
        elif status == "EXPIRED":
            raise QRCodeExpiredError("QR code expired")

        return AuthResult(
            success=False,
            qr_url=None,
            error="Waiting for scan",
        )

    async def confirm_qr(self, transport: TCPTransport, track_id: str) -> AuthResult:
        """Confirm QR login."""
        return await self._confirm_qr(transport, track_id)