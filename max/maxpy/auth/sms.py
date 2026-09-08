from __future__ import annotations

import asyncio
from typing import Any
from ..auth.base import AuthFlow, AuthResult, SmsCodeProvider, PasswordProvider
from ..enums import AuthType
from ..types.user import User, LoginResponse, Login2Response
from ..exceptions import AuthError, TwoFactorRequiredError, SessionExpiredError, RegistrationRequiredError
from ..transport.tcp import TCPTransport, TCPOpcode


class SmsAuthFlow(AuthFlow):
    """SMS authentication flow for TCP transport."""

    @property
    def auth_type(self) -> AuthType:
        return AuthType.SMS

    def __init__(self, config: Any):
        super().__init__(config)
        self._sms_provider: SmsCodeProvider | None = None
        self._password_provider: PasswordProvider | None = None

    def set_sms_provider(self, provider: SmsCodeProvider) -> None:
        self._sms_provider = provider

    def set_password_provider(self, provider: PasswordProvider) -> None:
        self._password_provider = provider

    async def authenticate(self, transport: TCPTransport) -> AuthResult:
        """Perform full SMS authentication flow."""
        if not self._sms_provider:
            raise AuthError("SMS code provider not set")

        phone = self.config.phone
        if not phone:
            raise AuthError("Phone number required for SMS auth")

        # Step 1: Request SMS code
        track_id = await self._request_sms_code(transport, phone)

        # Step 2: Get code from provider
        code = await self._sms_provider.get_code(phone)

        # Step 3: Send code
        result = await self._send_sms_code(transport, track_id, code)

        if result.requires_2fa:
            return await self._handle_2fa(transport, result.track_id)

        if result.requires_registration:
            return await self._handle_registration(transport, result.register_token)

        return result

    async def _request_sms_code(self, transport: TCPTransport, phone: str) -> str:
        """Request SMS code."""
        seq = await transport.send_packet(
            opcode=TCPOpcode.AUTH_REQUEST,
            payload={"phone": phone, "type": "START_AUTH"},
        )

        header, payload = await transport.receive()
        if header is None:
            raise AuthError("No response from server for SMS code request")
        if header.opcode == TCPOpcode.ERROR:
            raise AuthError(payload.get("error", "Failed to request SMS code"))

        return payload.get("trackId") or payload.get("track_id")

    async def _send_sms_code(self, transport: TCPTransport, track_id: str, code: str) -> AuthResult:
        """Send SMS code."""
        seq = await transport.send_packet(
            opcode=TCPOpcode.AUTH,
            payload={"trackId": track_id, "code": code},
        )

        header, payload = await transport.receive()

        if header.opcode == TCPOpcode.ERROR:
            error = payload.get("error", "Authentication failed")
            if error == "FAIL_LOGIN_PASSWORD":
                return AuthResult(
                    success=False,
                    requires_2fa=True,
                    track_id=track_id,
                    hint=payload.get("hint"),
                    error=error,
                )
            if error == "FAIL_REGISTER_REQUIRED":
                register_token = payload.get("registerToken") or payload.get("register_token")
                return AuthResult(
                    success=False,
                    requires_registration=True,
                    register_token=register_token,
                    error=error,
                )
            raise AuthError(error)

        # Success - login response
        login_resp = LoginResponse(**payload)
        transport.set_fingerprint(login_resp.token.encode() if isinstance(login_resp.token, str) else login_resp.token)

        return AuthResult(
            success=True,
            token=login_resp.token,
            user=login_resp.user,
        )

    async def _handle_2fa(self, transport: TCPTransport, track_id: str) -> AuthResult:
        """Handle 2FA password."""
        if not self._password_provider:
            raise TwoFactorRequiredError("2FA required but no password provider set")

        hint = None  # Would come from previous error
        password = await self._password_provider.get_password(hint)

        seq = await transport.send_packet(
            command=TCPCommand.AUTH_LOGIN_CHECK_PASSWORD,
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

    async def _handle_registration(self, transport: TCPTransport, register_token: str) -> AuthResult:
        """Handle account registration."""
        reg_config = self.config.registration_config or {}
        first_name = reg_config.get("first_name", "User")
        last_name = reg_config.get("last_name", "")

        seq = await transport.send_packet(
            command=TCPCommand.AUTH_CONFIRM,
            payload={
                "registerToken": register_token,
                "firstName": first_name,
                "lastName": last_name,
            },
        )

        header, payload = await transport.receive()

        if header.opcode == TCPOpcode.ERROR:
            raise AuthError(payload.get("error", "Registration failed"))

        login_resp = LoginResponse(**payload)
        return AuthResult(
            success=True,
            token=login_resp.token,
            user=login_resp.user,
        )

    async def refresh(self, transport: TCPTransport, token: str) -> AuthResult:
        """Refresh session (login2)."""
        seq = await transport.send_packet(
            command=TCPCommand.LOGIN2,
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
                command=TCPCommand.LOGOUT,
                payload={"token": token},
            )
            header, payload = await transport.receive()
            return header.opcode != TCPOpcode.ERROR
        except Exception:
            return False

    async def check_password(self, transport: TCPTransport, track_id: str, password: str) -> AuthResult:
        """Check 2FA password."""
        seq = await transport.send_packet(
            command=TCPCommand.AUTH_LOGIN_CHECK_PASSWORD,
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

    async def request_sms_code(self, transport: TCPTransport, phone: str) -> str:
        """Request SMS code."""
        return await self._request_sms_code(transport, phone)

    async def send_sms_code(self, transport: TCPTransport, track_id: str, code: str) -> AuthResult:
        """Send SMS code."""
        return await self._send_sms_code(transport, track_id, code)