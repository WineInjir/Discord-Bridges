from __future__ import annotations

from typing import Any
from pydantic import Field
from .base import CamelModel
from .common import ChatId, UserId, MessageId, JSONDict
from .message import (
    Message,
    MessageEvent,
    MessageEditEvent,
    MessageDeleteEvent,
    MessageReadEvent,
    TypingEvent,
    PresenceEvent,
    ReactionUpdateEvent,
)
from .chat import Chat, ChatUpdate, ChatMemberUpdate, JoinRequest
from .user import User
from .file import UploadResponse
from ..enums import EventType


class BaseEvent(CamelModel):
    """Base event model."""

    type: EventType
    timestamp: int  # Unix timestamp in milliseconds
    request_id: str | None = None


class RawEvent(BaseEvent):
    """Raw event from transport."""

    type: Literal[EventType.RAW] = EventType.RAW
    opcode: int
    payload: JSONDict


class StartEvent(BaseEvent):
    """Client started event."""

    type: Literal[EventType.START] = EventType.START
    client_id: str
    user: User


class DisconnectEvent(BaseEvent):
    """Disconnect event."""

    type: Literal[EventType.DISCONNECT] = EventType.DISCONNECT
    reason: str | None = None
    will_reconnect: bool = True


class ErrorEvent(BaseEvent):
    """Error event."""

    type: Literal[EventType.ERROR] = EventType.ERROR
    error: str
    error_type: str
    handler: str | None = None
    router: str | None = None


class SyncCompleteEvent(BaseEvent):
    """Sync completed event."""

    type: Literal[EventType.SYNC_COMPLETE] = EventType.SYNC_COMPLETE
    chats_synced: bool = False
    contacts_synced: bool = False
    drafts_synced: bool = False
    presence_synced: bool = False


# Upload ready events
class VideoReadyEvent(BaseEvent):
    """Video processing complete."""

    type: Literal[EventType.VIDEO_READY] = EventType.VIDEO_READY
    upload: UploadResponse


class FileReadyEvent(BaseEvent):
    """File processing complete."""

    type: Literal[EventType.FILE_READY] = EventType.FILE_READY
    upload: UploadResponse


class VoiceReadyEvent(BaseEvent):
    """Voice processing complete."""

    type: Literal[EventType.VOICE_READY] = EventType.VOICE_READY
    upload: UploadResponse


# Union of all events
Event = (
    MessageEvent
    | MessageEditEvent
    | MessageDeleteEvent
    | MessageReadEvent
    | TypingEvent
    | PresenceEvent
    | ReactionUpdateEvent
    | ChatUpdate
    | ChatMemberUpdate
    | JoinRequest
    | VideoReadyEvent
    | FileReadyEvent
    | VoiceReadyEvent
    | RawEvent
    | StartEvent
    | DisconnectEvent
    | ErrorEvent
    | SyncCompleteEvent
)


def map_event_type(event_type: EventType) -> type[BaseEvent]:
    """Map EventType to event class."""
    mapping = {
        EventType.MESSAGE_NEW: MessageEvent,
        EventType.MESSAGE_EDIT: MessageEditEvent,
        EventType.MESSAGE_DELETE: MessageDeleteEvent,
        EventType.MESSAGE_READ: MessageReadEvent,
        EventType.TYPING: TypingEvent,
        EventType.PRESENCE: PresenceEvent,
        EventType.REACTION_ADD: ReactionUpdateEvent,
        EventType.REACTION_REMOVE: ReactionUpdateEvent,
        EventType.CHAT_UPDATE: ChatUpdate,
        EventType.CHAT_CREATE: ChatUpdate,
        EventType.CHAT_DELETE: ChatUpdate,
        EventType.USER_UPDATE: ChatMemberUpdate,  # or separate
        EventType.VIDEO_READY: VideoReadyEvent,
        EventType.FILE_READY: FileReadyEvent,
        EventType.VOICE_READY: VoiceReadyEvent,
        EventType.RAW: RawEvent,
        EventType.START: StartEvent,
        EventType.DISCONNECT: DisconnectEvent,
        EventType.ERROR: ErrorEvent,
        EventType.SYNC_COMPLETE: SyncCompleteEvent,
    }
    return mapping.get(event_type, BaseEvent)