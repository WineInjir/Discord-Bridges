from __future__ import annotations

from enum import Enum, auto
from typing import Final


class TransportType(str, Enum):
    """Supported transport types."""

    REST = "rest"  # Green-API REST API
    TCP = "tcp"  # Internal MAX API via TCP (mobile)
    WEBSOCKET = "websocket"  # Internal MAX API via WebSocket (web)


class AuthType(str, Enum):
    """Authentication method types."""

    INSTANCE_TOKEN = "instance_token"  # Green-API: idInstance + apiTokenInstance
    SESSION_TOKEN = "session_token"  # Direct session token (TCP/WS)
    SMS = "sms"  # Phone + SMS code (+ optional 2FA)
    QR = "qr"  # QR code scanning (+ optional 2FA)


class ConnectionState(str, Enum):
    """Connection state."""

    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    AUTHENTICATING = "authenticating"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    CLOSING = "closing"
    CLOSED = "closed"


class EventType(str, Enum):
    """Event types for dispatcher."""

    # Message events
    MESSAGE_NEW = "message_new"
    MESSAGE_EDIT = "message_edit"
    MESSAGE_DELETE = "message_delete"
    MESSAGE_READ = "message_read"

    # Chat events
    CHAT_UPDATE = "chat_update"
    CHAT_CREATE = "chat_create"
    CHAT_DELETE = "chat_delete"

    # User events
    USER_UPDATE = "user_update"
    PRESENCE = "presence"
    TYPING = "typing"

    # Reaction events
    REACTION_ADD = "reaction_add"
    REACTION_REMOVE = "reaction_remove"

    # Media events
    VIDEO_READY = "video_ready"
    FILE_READY = "file_ready"
    VOICE_READY = "voice_ready"

    # System events
    RAW = "raw"
    START = "start"
    DISCONNECT = "disconnect"
    ERROR = "error"
    SYNC_COMPLETE = "sync_complete"


class ErrorScope(str, Enum):
    """Error handler scope."""

    GLOBAL = "global"  # Sees all errors from all routers
    LOCAL = "local"  # Sees only errors from own router


class MessageType(str, Enum):
    """Message content types."""

    TEXT = "text"
    PHOTO = "photo"
    VIDEO = "video"
    VOICE = "voice"
    VIDEO_NOTE = "video_note"
    FILE = "file"
    CONTACT = "contact"
    STICKER = "sticker"
    POLL = "poll"
    LOCATION = "location"
    FORWARD = "forward"
    REPLY = "reply"
    CALL = "call"
    CONTROL = "control"
    SHARE = "share"
    INLINE_KEYBOARD = "inline_keyboard"
    UNKNOWN = "unknown"


class ChatType(str, Enum):
    """Chat types."""

    PRIVATE = "private"
    GROUP = "group"
    CHANNEL = "channel"
    BOT = "bot"


class UserStatus(str, Enum):
    """User presence status."""

    ONLINE = "online"
    OFFLINE = "offline"
    RECENTLY = "recently"
    LAST_WEEK = "last_week"
    LAST_MONTH = "last_month"


class DeviceType(str, Enum):
    """Device types for fingerprinting."""

    ANDROID = "android"
    IOS = "ios"
    DESKTOP = "desktop"
    WEB = "web"


class UploadType(str, Enum):
    """File upload types."""

    PHOTO = "photo"
    VIDEO = "video"
    VOICE = "voice"
    VIDEO_NOTE = "video_note"
    FILE = "file"
    PROFILE_PHOTO = "profile_photo"
    GROUP_PHOTO = "group_photo"


# Constants
DEFAULT_TCP_HOST: Final[str] = "api2.oneme.ru"
DEFAULT_TCP_PORT: Final[int] = 443
DEFAULT_WS_URL: Final[str] = "wss://api.oneme.ru/websocket"
DEFAULT_REST_HOST: Final[str] = "https://api.green-api.com"
DEFAULT_REST_API_VERSION: Final[str] = "v3"

DEFAULT_RECONNECT_DELAY: Final[float] = 1.0
DEFAULT_RECONNECT_MAX_DELAY: Final[float] = 60.0
DEFAULT_RECONNECT_ATTEMPTS: Final[int] = 10
DEFAULT_REQUEST_TIMEOUT: Final[float] = 30.0
DEFAULT_PING_INTERVAL: Final[float] = 30.0
DEFAULT_UPLOAD_TIMEOUT: Final[float] = 900.0
DEFAULT_UPLOAD_CHUNK_SIZE: Final[int] = 1024 * 1024  # 1MB

# Green-API specific
GREEN_API_MEDIA_HOST: Final[str] = "https://media.green-api.com"

# File validation
MAX_PHOTO_SIZE: Final[int] = 20 * 1024 * 1024  # 20MB
MAX_VIDEO_SIZE: Final[int] = 200 * 1024 * 1024  # 200MB
MAX_VOICE_SIZE: Final[int] = 50 * 1024 * 1024  # 50MB
MAX_FILE_SIZE: Final[int] = 2 * 1024 * 1024 * 1024  # 2GB

ALLOWED_PHOTO_EXTENSIONS: Final[set[str]] = {"jpg", "jpeg", "png", "webp", "heic"}
ALLOWED_VIDEO_EXTENSIONS: Final[set[str]] = {"mp4", "mov", "mkv", "webm"}
ALLOWED_VOICE_EXTENSIONS: Final[set[str]] = {"ogg", "opus", "mp3", "m4a", "wav"}
ALLOWED_VIDEO_NOTE_EXTENSIONS: Final[set[str]] = {"mp4", "mov"}

MIME_TYPE_MAP: Final[dict[str, str]] = {
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
    "webp": "image/webp",
    "heic": "image/heic",
    "mp4": "video/mp4",
    "mov": "video/quicktime",
    "mkv": "video/x-matroska",
    "webm": "video/webm",
    "ogg": "audio/ogg",
    "opus": "audio/opus",
    "mp3": "audio/mpeg",
    "m4a": "audio/mp4",
    "wav": "audio/wav",
    "pdf": "application/pdf",
    "doc": "application/msword",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xls": "application/vnd.ms-excel",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "zip": "application/zip",
    "rar": "application/x-rar-compressed",
    "txt": "text/plain",
}