from __future__ import annotations

import qrcode
from io import BytesIO
from ..auth.base import SmsCodeProvider, QrHandler, PasswordProvider, EmailCodeProvider


class ConsoleSmsCodeProvider(SmsCodeProvider):
    """Console SMS code provider (for testing)."""

    async def get_code(self, phone: str) -> str:
        print(f"\nEnter SMS code for {phone}: ", end="", flush=True)
        code = input().strip()
        return code


class ConsolePasswordProvider(PasswordProvider):
    """Console password provider (for 2FA)."""

    async def get_password(self, hint: str | None = None) -> str:
        prompt = "Enter 2FA password"
        if hint:
            prompt += f" (hint: {hint})"
        prompt += ": "
        print(prompt, end="", flush=True)
        import getpass
        password = getpass.getpass()
        return password


class ConsoleQrHandler(QrHandler):
    """Console QR code handler."""

    def __init__(self, inline: bool = True):
        self.inline = inline

    async def show_qr(self, qr_url: str) -> None:
        print(f"\nScan this QR code with MAX app:")
        print(f"URL: {qr_url}")

        if self.inline:
            try:
                qr = qrcode.QRCode(
                    version=1,
                    error_correction=qrcode.constants.ERROR_CORRECT_L,
                    box_size=1,
                    border=1,
                )
                qr.add_data(qr_url)
                qr.make(fit=True)

                # Print ASCII QR code
                f = BytesIO()
                qr.make_image(fill_color="black", back_color="white").save(f, "PNG")
                # For ASCII, we use a simple approach
                for row in qr.get_matrix():
                    line = "".join("██" if cell else "  " for cell in row)
                    print(line)
            except Exception:
                print("(QR code display not available, use the URL above)")


class ConsoleEmailCodeProvider(EmailCodeProvider):
    """Console email code provider."""

    async def get_code(self, email: str) -> str:
        print(f"\nEnter email code for {email}: ", end="", flush=True)
        code = input().strip()
        return code


# Factory function
def create_console_providers(
    sms: bool = True,
    qr: bool = True,
    password: bool = True,
    email: bool = True,
) -> dict[str, Any]:
    """Create console providers."""
    providers = {}
    if sms:
        providers["sms"] = ConsoleSmsCodeProvider()
    if qr:
        providers["qr"] = ConsoleQrHandler()
    if password:
        providers["password"] = ConsolePasswordProvider()
    if email:
        providers["email"] = ConsoleEmailCodeProvider()
    return providers