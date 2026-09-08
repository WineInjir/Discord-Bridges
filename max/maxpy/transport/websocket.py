from __future__ import annotations

import asyncio
import json
import time
from typing import Any, Optional

import websockets
from websockets import ClientConnection

from .base import Transport, TransportFactory
from ..config import TransportConfig
from ..enums import TransportType
from ..exceptions import TransportError, ConnectionError


class WSPayloadCodec:
    """WebSocket payload encoding/decoding (JSON)."""

    @staticmethod
    def encode(data: dict[str, Any]) -> str:
        return json.dumps(data, separators=(",", ":"))

    @staticmethod
    def decode(data: str | bytes) -> dict[str, Any]:
        if isinstance(data, bytes):
            data = data.decode()
        return json.loads(data)


class WSOpcode:
    """WebSocket opcodes."""

    HANDSHAKE = "handshake"
    LOGIN = "login"
    LOGIN2 = "login2"
    LOGOUT = "logout"
    PING = "ping"
    PONG = "pong"
    MSG_SEND = "msg_send"
    MSG_EDIT = "msg_edit"
    MSG_DELETE = "msg_delete"
    MSG_GET = "msg_get"
    CHAT_HISTORY = "chat_history"
    CHAT_INFO = "chat_info"
    CHATS_LIST = "chats_list"
    CHAT_JOIN = "chat_join"
    CHAT_LEAVE = "chat_leave"
    CHAT_DELETE = "chat_delete"
    CHAT_UPDATE = "chat_update"
    CHAT_MEMBERS = "chat_members"
    CHAT_MEMBERS_UPDATE = "chat_members_update"
    CONTACT_INFO = "contact_info"
    CONTACT_INFO_BY_PHONE = "contact_info_by_phone"
    CONTACT_UPDATE = "contact_update"
    SYNC = "sync"
    PROFILE = "profile"
    PHOTO_UPLOAD = "photo_upload"
    FOLDERS_GET = "folders_get"
    FOLDERS_UPDATE = "folders_update"
    FOLDERS_DELETE = "folders_delete"
    CONFIG = "config"
    SESSIONS_INFO = "sessions_info"
    SESSIONS_CLOSE = "sessions_close"
    AUTH_REQUEST = "auth_request"
    AUTH = "auth"
    AUTH_LOGIN_CHECK_PASSWORD = "auth_login_check_password"
    GET_QR = "get_qr"
    GET_QR_STATUS = "get_qr_status"
    LOGIN_BY_QR = "login_by_qr"
    AUTH_CREATE_TRACK = "auth_create_track"
    AUTH_VERIFY_EMAIL = "auth_verify_email"
    AUTH_CHECK_EMAIL = "auth_check_email"
    AUTH_VALIDATE_HINT = "auth_validate_hint"
    AUTH_VALIDATE_PASSWORD = "auth_validate_password"
    AUTH_SET_2FA = "auth_set_2fa"
    AUTH_QR_APPROVE = "auth_qr_approve"
    AUTH_CONFIRM = "auth_confirm"
    BOT_GET_INFO = "bot_get_info"
    BOT_SEND = "bot_send"
    TELEMETRY = "telemetry"
    VIDEO_PLAY = "video_play"
    FILE_DOWNLOAD = "file_download"
    PHOTO_UPLOAD_URL = "photo_upload_url"
    VIDEO_UPLOAD_URL = "video_upload_url"
    FILE_UPLOAD_URL = "file_upload_url"


class WSFrame:
    """WebSocket frame structure."""

    def __init__(
        self,
        type: str,
        payload: dict[str, Any],
        request_id: str | None = None,
    ):
        self.type = type
        self.payload = payload
        self.request_id = request_id

    def to_json(self) -> str:
        data = {"type": self.type, "payload": self.payload}
        if self.request_id:
            data["request_id"] = self.request_id
        return WSPayloadCodec.encode(data)

    @classmethod
    def from_json(cls, data: str) -> "WSFrame":
        obj = WSPayloadCodec.decode(data)
        return cls(
            type=obj.get("type", ""),
            payload=obj.get("payload", {}),
            request_id=obj.get("request_id"),
        )


class WebSocketTransport(Transport):
    """WebSocket transport for internal MAX API (web client)."""

    def __init__(self, config: TransportConfig):
        super().__init__(config)
        self._ws: ClientConnection | None = None
        self._origin = "https://web.max.ru"  # TODO: make configurable
        self._max_frame_size = 10 * 1024 * 1024  # 10MB

    async def connect(self) -> None:
        """Establish WebSocket connection."""
        if self._ws and not self._ws.closed:
            return

        url = self.config.ws_url

        # Setup proxy
        proxy = None
        if self.config.proxy:
            proxy = self.config.proxy

        try:
            self._ws = await websockets.connect(
                url,
                origin=self._origin,
                proxy=proxy,
                max_size=self._max_frame_size,
                ping_interval=20,
                ping_timeout=10,
                close_timeout=5,
                additional_headers={
                    "User-Agent": "MaxPy/0.1.0",
                },
            )
            self._connected = True
            self._metadata.connected_at = time.time()

        except Exception as e:
            raise ConnectionError(
                f"Failed to connect WebSocket: {e}",
                endpoint=url,
                transport="websocket",
                original_error=e,
            )

    async def send(self, data: bytes | str) -> None:
        """Send raw data."""
        if not self._connected or not self._ws:
            raise ConnectionError("Transport not connected")

        if isinstance(data, bytes):
            data = data.decode()

        await self._ws.send(data)
        self._mark_sent(len(data))

    async def send_frame(self, frame: WSFrame) -> None:
        """Send a WebSocket frame."""
        await self.send(frame.to_json())

    async def send_request(
        self,
        opcode: str,
        payload: dict[str, Any],
        request_id: str | None = None,
    ) -> None:
        """Send a request frame."""
        frame = WSFrame(type=opcode, payload=payload, request_id=request_id)
        await self.send_frame(frame)

    async def receive(self) -> WSFrame | None:
        """Receive and decode a WebSocket frame."""
        if not self._connected or not self._ws:
            raise ConnectionError("Transport not connected")

        try:
            data = await self._ws.recv()
            self._mark_received(len(data) if isinstance(data, str) else len(data))
            return WSFrame.from_json(data)
        except websockets.ConnectionClosed:
            return None
        except Exception as e:
            self._mark_error()
            raise TransportError(f"Failed to receive frame: {e}", transport="websocket", original_error=e)

    async def close(self) -> None:
        """Close WebSocket connection."""
        self._closing = True
        if self._ws and not self._ws.closed:
            await self._ws.close()
        self._connected = False
        self._ws = None


# Register transport
TransportFactory.register(TransportType.WEBSOCKET, WebSocketTransport)