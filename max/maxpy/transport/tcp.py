from __future__ import annotations

import asyncio
import ssl
import struct
import time
from typing import Any, Optional
from pathlib import Path

import msgpack
from python_socks import ProxyType
from python_socks.async_.asyncio import Proxy as AsyncProxy

from .base import Transport, TransportFactory
from ..config import TransportConfig
from ..enums import TransportType
from ..exceptions import TransportError, ConnectionError, wrap_error
from ..utils.fingerprint import FingerprintGenerator


# TCP Protocol constants - PyMax Opcode values
class TCPOpcode:
    # Frame types (cmd field)
    REQUEST = 0
    RESPONSE = 1
    EVENT = 2
    ERROR = 3

    # Operation codes (opcode field)
    SESSION_INIT = 6
    LOGIN = 1
    LOGIN2 = 8
    LOGOUT = 20
    PING = 1
    MSG_SEND = 64
    MSG_EDIT = 67
    MSG_DELETE = 66
    MSG_GET = 71
    CHAT_HISTORY = 49
    CHAT_INFO = 48
    CHATS_LIST = 53
    CHAT_JOIN = 57
    CHAT_LEAVE = 58
    CHAT_DELETE = 52
    CHAT_UPDATE = 55
    CHAT_MEMBERS = 59
    CHAT_MEMBERS_UPDATE = 77
    CONTACT_INFO = 32
    CONTACT_INFO_BY_PHONE = 46
    CONTACT_UPDATE = 34
    SYNC = 21
    PROFILE = 16
    PHOTO_UPLOAD = 80
    FOLDERS_GET = 272
    FOLDERS_UPDATE = 274
    FOLDERS_DELETE = 276
    CONFIG = 22
    SESSIONS_INFO = 96
    SESSIONS_CLOSE = 97
    AUTH_REQUEST = 17
    AUTH = 18
    AUTH_LOGIN_CHECK_PASSWORD = 115
    GET_QR = 288
    GET_QR_STATUS = 289
    LOGIN_BY_QR = 291
    AUTH_CREATE_TRACK = 112
    AUTH_VERIFY_EMAIL = 109
    AUTH_CHECK_EMAIL = 110
    AUTH_VALIDATE_HINT = 108
    AUTH_VALIDATE_PASSWORD = 107
    AUTH_SET_2FA = 111
    AUTH_QR_APPROVE = 290
    AUTH_CONFIRM = 23
    BOT_GET_INFO = 145
    BOT_SEND = 118
    TELEMETRY = 160
    VIDEO_PLAY = 83
    FILE_DOWNLOAD = 88
    PHOTO_UPLOAD_URL = 80
    VIDEO_UPLOAD_URL = 82
    FILE_UPLOAD_URL = 87


class TCPFlags:
    COMPRESSED = 0x80
    ENCRYPTED = 0x40


# Packet structure (PyMax format):
# Header: 1 byte version, 1 byte cmd, 2 bytes sequence, 2 bytes opcode, 4 bytes packed_len
#   packed_len = (flags << 24) | (length & 0x00FFFFFF)
# Payload: msgpack encoded
HEADER_FORMAT = ">BBHHI"
HEADER_SIZE = 10  # 1+1+2+2+4 = 10 bytes


class TCPPacketHeader:
    """TCP packet header (PyMax format)."""

    def __init__(
        self,
        version: int = 10,
        cmd: int = 0,
        sequence: int = 0,
        opcode: int = 0,
        flags: int = 0,
        length: int = 0,
    ):
        self.version = version
        self.cmd = cmd
        self.sequence = sequence
        self.opcode = opcode
        self.flags = flags
        self.length = length

    @property
    def command(self) -> int:
        """Alias for cmd (backward compatibility)."""
        return self.cmd

    @command.setter
    def command(self, value: int) -> None:
        self.cmd = value

    def pack(self) -> bytes:
        packed_len = ((self.flags & 0xFF) << 24) | (self.length & 0x00FFFFFF)
        return struct.pack(
            ">BBHHI",
            self.version,
            self.cmd,
            self.sequence,
            self.opcode,
            packed_len,
        )

    @classmethod
    def unpack(cls, data: bytes) -> "TCPPacketHeader":
        if len(data) < 10:
            raise ValueError("Header too short")
        version, cmd, sequence, opcode, packed_len = struct.unpack(">BBHHI", data[:10])
        flags = (packed_len >> 24) & 0xFF
        length = packed_len & 0x00FFFFFF
        return cls(version, cmd, sequence, opcode, flags, length)


class TCPPayloadCodec:
    """TCP payload encoding/decoding."""

    @staticmethod
    def encode(data: dict[str, Any]) -> bytes:
        return msgpack.packb(data, use_bin_type=True)

    @staticmethod
    def decode(data: bytes) -> dict[str, Any]:
        return msgpack.unpackb(data, raw=False, strict_map_key=False)


class ZstdCompression:
    """Zstd compression for TCP."""

    @staticmethod
    def compress(data: bytes) -> bytes:
        import zstandard as zstd
        cctx = zstd.ZstdCompressor(level=3)
        return cctx.compress(data)

    @staticmethod
    def decompress(data: bytes) -> bytes:
        import zstandard as zstd
        dctx = zstd.ZstdDecompressor()
        return dctx.decompress(data)


class LZ4Compression:
    """LZ4 compression for TCP."""

    @staticmethod
    def compress(data: bytes) -> bytes:
        import lz4.block
        return lz4.block.compress(data, mode="high_compression", store_size=False)

    @staticmethod
    def decompress(data: bytes) -> bytes:
        import lz4.block
        return lz4.block.decompress(data)


class TCPTransport(Transport):
    """TCP transport for internal MAX API."""

    def __init__(self, config: TransportConfig):
        super().__init__(config)
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._sequence = 0
        self._fingerprint: bytes | None = None
        self._ssl_context: ssl.SSLContext | None = None
        self._proxy: AsyncProxy | None = None

    async def connect(self) -> None:
        """Establish TCP connection with SSL."""
        if self._writer and not self._writer.is_closing():
            return

        # Setup SSL context
        self._ssl_context = ssl.create_default_context()
        self._ssl_context.check_hostname = False
        self._ssl_context.verify_mode = ssl.CERT_NONE

        # Load custom CA if provided
        if self.config.custom_ca:
            self._ssl_context.load_verify_locations(self.config.custom_ca)
            self._ssl_context.verify_mode = ssl.CERT_REQUIRED
            self._ssl_context.check_hostname = True
        else:
            # Use embedded CA cert
            ca_path = Path(__file__).parent.parent / "certs" / "rootca_ssl_rsa2022.crt"
            if ca_path.exists():
                self._ssl_context.load_verify_locations(str(ca_path))
                self._ssl_context.verify_mode = ssl.CERT_REQUIRED
                self._ssl_context.check_hostname = True

        # Setup proxy
        if self.config.proxy:
            proxy_type = ProxyType.SOCKS5  # Default
            if self.config.proxy.startswith("http://"):
                proxy_type = ProxyType.HTTP
            elif self.config.proxy.startswith("socks5://"):
                proxy_type = ProxyType.SOCKS5
            elif self.config.proxy.startswith("socks4://"):
                proxy_type = ProxyType.SOCKS4
            
            # Parse proxy URL
            from python_socks._helpers import parse_proxy_url
            proxy_info = parse_proxy_url(self.config.proxy)
            self._proxy = AsyncProxy(
                proxy_type=proxy_type,
                host=proxy_info.host,
                port=proxy_info.port,
                username=proxy_info.username,
                password=proxy_info.password,
            )

        # Connect
        try:
            if self._proxy:
                sock = await self._proxy.connect(
                    self.config.host,
                    self.config.port,
                )
                self._reader, self._writer = await asyncio.open_connection(
                    host=None,
                    port=None,
                    sock=sock,
                    ssl=self._ssl_context,
                    server_hostname=self.config.host,
                )
            else:
                self._reader, self._writer = await asyncio.open_connection(
                    host=self.config.host,
                    port=self.config.port,
                    ssl=self._ssl_context,
                    server_hostname=self.config.host,
                )

            self._connected = True
            self._metadata.connected_at = time.time()
            self._sequence = 0

        except Exception as e:
            raise ConnectionError(
                f"Failed to connect: {e}",
                endpoint=f"{self.config.host}:{self.config.port}",
                transport="tcp",
                original_error=e,
            )

    def _next_sequence(self) -> int:
        self._sequence = (self._sequence + 1) % 65536
        return self._sequence

    async def send(self, data: bytes | str) -> None:
        """Send raw data (not typically used directly)."""
        if not self._connected or not self._writer:
            raise ConnectionError("Transport not connected")

        if isinstance(data, str):
            data = data.encode()

        self._writer.write(data)
        await self._writer.drain()
        self._mark_sent(len(data))

    async def send_packet(
        self,
        opcode: int,
        payload: dict[str, Any],
        cmd: int = 0,  # REQUEST
        flags: int = 0,
        sequence: int | None = None,
    ) -> int:
        """Send a TCP packet with msgpack payload."""
        if not self._connected or not self._writer:
            raise ConnectionError("Transport not connected")

        seq = sequence if sequence is not None else self._next_sequence()
        payload_bytes = TCPPayloadCodec.encode(payload)

        # Apply compression if needed
        if flags & 0x80:  # Zstd compression flag
            payload_bytes = ZstdCompression.compress(payload_bytes)

        header = TCPPacketHeader(
            version=10,  # PyMax protocol version
            cmd=cmd,
            sequence=seq,
            opcode=opcode,
            flags=flags,
            length=len(payload_bytes),
        )

        packet = header.pack() + payload_bytes
        self._writer.write(packet)
        await self._writer.drain()
        self._mark_sent(len(packet))
        return seq

    async def receive(self) -> tuple[TCPPacketHeader, dict[str, Any]] | None:
        """Receive and decode a TCP packet."""
        if not self._connected or not self._reader:
            raise ConnectionError("Transport not connected")

        try:
            # Read header (10 bytes in PyMax format)
            header_data = await self._reader.readexactly(10)
            header = TCPPacketHeader.unpack(header_data)

            # Read payload
            if header.length > 0:
                payload_data = await self._reader.readexactly(header.length)
            else:
                payload_data = b""

            self._mark_received(10 + len(payload_data))

            # Decompress if needed
            if header.flags == 0xFF:  # Zstd compression
                import zstandard as zstd
                dctx = zstd.ZstdDecompressor()
                payload_data = dctx.decompress(payload_data)
            elif header.flags > 0:  # LZ4 compression with factor = flags
                import lz4.block
                payload_data = lz4.block.decompress(payload_data, uncompressed_size=5 * 1024 * 1024)

            # Decode payload
            if payload_data:
                payload = TCPPayloadCodec.decode(payload_data)
            else:
                payload = {}

            return header, payload

        except asyncio.IncompleteReadError:
            return None
        except Exception as e:
            self._mark_error()
            raise TransportError(f"Failed to receive packet: {e}", transport="tcp", original_error=e)

    async def close(self) -> None:
        """Close TCP connection."""
        self._closing = True
        if self._writer and not self._writer.is_closing():
            self._writer.close()
            try:
                await self._writer.wait_closed()
            except Exception:
                pass
        self._connected = False
        self._reader = None
        self._writer = None

    def set_fingerprint(self, fingerprint: bytes) -> None:
        """Set device fingerprint."""
        self._fingerprint = fingerprint

    @property
    def fingerprint(self) -> bytes | None:
        return self._fingerprint


# Register transport
TransportFactory.register(TransportType.TCP, TCPTransport)