"""Unit tests for enums and constants."""

from __future__ import annotations

import pytest

from maxpy.enums import (
    TransportType,
    AuthType,
    ConnectionState,
    EventType,
    ErrorScope,
    MessageType,
    ChatType,
    UserStatus,
    DeviceType,
    UploadType,
    DEFAULT_TCP_HOST,
    DEFAULT_TCP_PORT,
    DEFAULT_WS_URL,
    DEFAULT_REST_HOST,
    ALLOWED_PHOTO_EXTENSIONS,
    ALLOWED_VIDEO_EXTENSIONS,
    MIME_TYPE_MAP,
    MAX_PHOTO_SIZE,
    MAX_VIDEO_SIZE,
)


class TestTransportType:
    """Tests for TransportType enum."""

    def test_values(self):
        assert TransportType.REST == "rest"
        assert TransportType.TCP == "tcp"
        assert TransportType.WEBSOCKET == "websocket"

    def test_from_string(self):
        assert TransportType("rest") == TransportType.REST
        assert TransportType("tcp") == TransportType.TCP
        assert TransportType("websocket") == TransportType.WEBSOCKET


class TestAuthType:
    """Tests for AuthType enum."""

    def test_values(self):
        assert AuthType.INSTANCE_TOKEN == "instance_token"
        assert AuthType.SESSION_TOKEN == "session_token"
        assert AuthType.SMS == "sms"
        assert AuthType.QR == "qr"


class TestConnectionState:
    """Tests for ConnectionState enum."""

    def test_values(self):
        assert ConnectionState.DISCONNECTED == "disconnected"
        assert ConnectionState.CONNECTING == "connecting"
        assert ConnectionState.AUTHENTICATING == "authenticating"
        assert ConnectionState.CONNECTED == "connected"
        assert ConnectionState.RECONNECTING == "reconnecting"


class TestEventType:
    """Tests for EventType enum."""

    def test_message_events(self):
        assert EventType.MESSAGE_NEW == "message_new"
        assert EventType.MESSAGE_EDIT == "message_edit"
        assert EventType.MESSAGE_DELETE == "message_delete"
        assert EventType.MESSAGE_READ == "message_read"

    def test_chat_events(self):
        assert EventType.CHAT_UPDATE == "chat_update"
        assert EventType.CHAT_CREATE == "chat_create"
        assert EventType.CHAT_DELETE == "chat_delete"

    def test_user_events(self):
        assert EventType.USER_UPDATE == "user_update"
        assert EventType.PRESENCE == "presence"
        assert EventType.TYPING == "typing"

    def test_system_events(self):
        assert EventType.RAW == "raw"
        assert EventType.START == "start"
        assert EventType.DISCONNECT == "disconnect"
        assert EventType.ERROR == "error"


class TestConstants:
    """Tests for constants."""

    def test_tcp_defaults(self):
        assert DEFAULT_TCP_HOST == "api2.oneme.ru"
        assert DEFAULT_TCP_PORT == 443

    def test_ws_defaults(self):
        assert DEFAULT_WS_URL == "wss://api.oneme.ru/websocket"

    def test_rest_defaults(self):
        assert DEFAULT_REST_HOST == "https://api.green-api.com"

    def test_file_limits(self):
        assert MAX_PHOTO_SIZE == 20 * 1024 * 1024  # 20MB
        assert MAX_VIDEO_SIZE == 200 * 1024 * 1024  # 200MB

    def test_allowed_extensions(self):
        assert "jpg" in ALLOWED_PHOTO_EXTENSIONS
        assert "png" in ALLOWED_PHOTO_EXTENSIONS
        assert "mp4" in ALLOWED_VIDEO_EXTENSIONS
        assert "ogg" in MIME_TYPE_MAP
        assert MIME_TYPE_MAP["jpg"] == "image/jpeg"
        assert MIME_TYPE_MAP["mp4"] == "video/mp4"