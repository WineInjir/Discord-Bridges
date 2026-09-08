from __future__ import annotations

from typing import Any, Literal
from pydantic import Field, field_validator, PrivateAttr
from .base import CamelModel
from .common import ChatId, UserId, MessageId, JSONDict
from .user import User
from .chat import Chat
from .file import Photo, Video, Voice, VideoNote, Document
from ..enums import EventType, MessageType


class Attachment(CamelModel):
    """Base attachment."""

    type: str


class PhotoAttachment(Attachment):
    """Photo attachment."""

    type: Literal["photo"] = "photo"
    photo: Photo


class VideoAttachment(Attachment):
    """Video attachment."""

    type: Literal["video"] = "video"
    video: Video


class VoiceAttachment(Attachment):
    """Voice attachment."""

    type: Literal["voice"] = "voice"
    voice: Voice


class VideoNoteAttachment(Attachment):
    """Video note (round video) attachment."""

    type: Literal["video_note"] = "video_note"
    video_note: VideoNote


class FileAttachment(Attachment):
    """File attachment."""

    type: Literal["file"] = "file"
    file: Document


class ContactAttachment(Attachment):
    """Contact attachment."""

    type: Literal["contact"] = "contact"
    phone_number: str
    first_name: str
    last_name: str | None = None
    user_id: UserId | None = None


class StickerAttachment(Attachment):
    """Sticker attachment."""

    type: Literal["sticker"] = "sticker"
    sticker: "Sticker"


class PollAttachment(Attachment):
    """Poll attachment."""

    type: Literal["poll"] = "poll"
    poll: "Poll"


class LocationAttachment(Attachment):
    """Location attachment."""

    type: Literal["location"] = "location"
    latitude: float
    longitude: float
    live_period: int | None = None


class ShareAttachment(Attachment):
    """Share attachment."""

    type: Literal["share"] = "share"
    chat_id: ChatId
    message_id: MessageId


class CallAttachment(Attachment):
    """Call attachment."""

    type: Literal["call"] = "call"
    call_id: str
    duration: int | None = None
    is_video: bool = False
    is_missed: bool = False


class ControlAttachment(Attachment):
    """Control message (system)."""

    type: Literal["control"] = "control"
    action: str
    data: JSONDict | None = None


class InlineKeyboardAttachment(Attachment):
    """Inline keyboard attachment."""

    type: Literal["inline_keyboard"] = "inline_keyboard"
    buttons: list[list["InlineKeyboardButton"]]


class UnknownAttachment(Attachment):
    """Unknown attachment type."""

    type: Literal["unknown"] = "unknown"
    data: JSONDict


# Discriminated union
AttachmentUnion = (
    PhotoAttachment
    | VideoAttachment
    | VoiceAttachment
    | VideoNoteAttachment
    | FileAttachment
    | ContactAttachment
    | StickerAttachment
    | PollAttachment
    | LocationAttachment
    | ShareAttachment
    | CallAttachment
    | ControlAttachment
    | InlineKeyboardAttachment
    | UnknownAttachment
)


class InlineKeyboardButton(CamelModel):
    """Inline keyboard button."""

    text: str
    url: str | None = None
    callback_data: str | None = None
    switch_inline_query: str | None = None
    switch_inline_query_current_chat: str | None = None
    callback_game: bool | None = None
    pay: bool | None = None


class PollOption(CamelModel):
    """Poll option."""

    text: str
    voter_count: int = 0
    is_chosen: bool = False


class Poll(CamelModel):
    """Poll."""

    id: str
    question: str
    options: list[PollOption]
    total_voter_count: int = 0
    is_closed: bool = False
    is_anonymous: bool = True
    type: str = "regular"  # regular, quiz
    allows_multiple_answers: bool = False
    correct_option_id: int | None = None
    explanation: str | None = None
    open_period: int | None = None
    close_date: int | None = None


class PollState(CamelModel):
    """Poll state (user's vote)."""

    poll_id: str
    chosen_options: list[int] = []


class Sticker(CamelModel):
    """Sticker."""

    id: str
    set_name: str
    width: int
    height: int
    is_animated: bool = False
    is_video: bool = False
    emoji: str | None = None
    thumbnail: Photo | None = None
    file: Document | None = None


class Reaction(CamelModel):
    """Reaction."""

    emoji: str
    count: int = 0
    is_chosen: bool = False
    users: list[User] | None = None


class ReactionInfo(CamelModel):
    """Reaction info for a message."""

    message_id: MessageId
    chat_id: ChatId
    reactions: list[Reaction] = []


class ReactionCounter(CamelModel):
    """Reaction counter summary."""

    emoji: str
    count: int


class ReadState(CamelModel):
    """Message read state."""

    message_id: MessageId
    chat_id: ChatId
    user_id: UserId
    read_at: int


class Message(CamelModel):
    """Message model."""

    id: MessageId
    chat_id: ChatId
    sender_id: UserId
    type: MessageType = MessageType.TEXT
    text: str | None = None
    attachments: list[AttachmentUnion] = []
    reply_to: MessageId | None = None
    forward_from: UserId | None = None
    forward_from_chat: ChatId | None = None
    forward_date: int | None = None
    edit_date: int | None = None
    is_outgoing: bool = False
    is_pinned: bool = False
    is_edited: bool = False
    is_deleted: bool = False
    views: int = 0
    forwards: int = 0
    reactions: list[ReactionCounter] = []
    read_state: ReadState | None = None
    created_at: int  # Unix timestamp
    send_at: int | None = None  # Scheduled send time

    # Private attribute for client reference (set by dispatcher)
    _client: Any = PrivateAttr(default=None)

    def set_client(self, client: Any) -> "Message":
        """Set client reference for convenience methods."""
        self._client = client
        return self

    @property
    def has_media(self) -> bool:
        return bool(self.attachments)

    @property
    def photo(self) -> Photo | None:
        for att in self.attachments:
            if isinstance(att, PhotoAttachment):
                return att.photo
        return None

    @property
    def video(self) -> Video | None:
        for att in self.attachments:
            if isinstance(att, VideoAttachment):
                return att.video
        return None

    @property
    def voice(self) -> Voice | None:
        for att in self.attachments:
            if isinstance(att, VoiceAttachment):
                return att.voice
        return None

    @property
    def video_note(self) -> VideoNote | None:
        for att in self.attachments:
            if isinstance(att, VideoNoteAttachment):
                return att.video_note
        return None

    @property
    def document(self) -> Document | None:
        for att in self.attachments:
            if isinstance(att, FileAttachment):
                return att.file
        return None

    @property
    def poll(self) -> Poll | None:
        for att in self.attachments:
            if isinstance(att, PollAttachment):
                return att.poll
        return None

    @property
    def contact(self) -> ContactAttachment | None:
        for att in self.attachments:
            if isinstance(att, ContactAttachment):
                return att
        return None

    @property
    def location(self) -> LocationAttachment | None:
        for att in self.attachments:
            if isinstance(att, LocationAttachment):
                return att
        return None

    # Convenience methods
    async def reply(self, text: str, **kwargs) -> "Message":
        """Reply to this message."""
        if not self._client:
            raise RuntimeError("Client not set on message")
        return await self._client.messages.send(
            self.chat_id,
            text=text,
            reply_to=self.id,
            **kwargs,
        )

    async def answer(self, text: str, **kwargs) -> "Message":
        """Answer to this message (alias for reply)."""
        return await self.reply(text, **kwargs)

    async def forward(self, to_chat_id: ChatId, **kwargs) -> list["Message"]:
        """Forward this message to another chat."""
        if not self._client:
            raise RuntimeError("Client not set on message")
        return await self._client.messages.forward(
            to_chat_id,
            self.chat_id,
            [self.id],
            **kwargs,
        )

    async def edit(self, text: str | None = None, **kwargs) -> "Message":
        """Edit this message."""
        if not self._client:
            raise RuntimeError("Client not set on message")
        return await self._client.messages.edit(
            self.chat_id,
            self.id,
            text=text,
            **kwargs,
        )

    async def delete(self, for_all: bool = False) -> bool:
        """Delete this message."""
        if not self._client:
            raise RuntimeError("Client not set on message")
        return await self._client.messages.delete(
            self.chat_id,
            self.id,
            for_all=for_all,
        )

    async def pin(self, notify: bool = True) -> bool:
        """Pin this message."""
        if not self._client:
            raise RuntimeError("Client not set on message")
        return await self._client.messages.pin(
            self.chat_id,
            self.id,
            notify=notify,
        )

    async def unpin(self) -> bool:
        """Unpin this message."""
        if not self._client:
            raise RuntimeError("Client not set on message")
        return await self._client.messages.unpin(
            self.chat_id,
            self.id,
        )

    async def read(self) -> bool:
        """Mark this message as read."""
        if not self._client:
            raise RuntimeError("Client not set on message")
        return await self._client.messages.read(
            self.chat_id,
            self.id,
        )

    async def react(self, emoji: str) -> bool:
        """Add reaction to this message."""
        if not self._client:
            raise RuntimeError("Client not set on message")
        return await self._client.messages.add_reaction(
            self.chat_id,
            self.id,
            emoji,
        )

    async def unreact(self, emoji: str) -> bool:
        """Remove reaction from this message."""
        if not self._client:
            raise RuntimeError("Client not set on message")
        return await self._client.messages.remove_reaction(
            self.chat_id,
            self.id,
            emoji,
        )

    async def get_reactions(self) -> list:
        """Get reactions on this message."""
        if not self._client:
            raise RuntimeError("Client not set on message")
        return await self._client.messages.get_reactions(
            self.chat_id,
            self.id,
        )

    async def vote_poll(self, option_ids: list[int]) -> bool:
        """Vote in poll attached to this message."""
        if not self._client:
            raise RuntimeError("Client not set on message")
        return await self._client.messages.vote_poll(
            self.chat_id,
            self.id,
            option_ids,
        )


class SendMessageRequest(CamelModel):
    """Send message request."""

    chat_id: ChatId
    text: str | None = None
    attachments: list[AttachmentUnion] = []
    reply_to: MessageId | None = None
    forward_from: MessageId | None = None
    send_at: int | None = None  # Unix timestamp for scheduled send
    link_preview: bool = True
    silent: bool = False
    parse_mode: str | None = None  # markdown, html


class EditMessageRequest(CamelModel):
    """Edit message request."""

    chat_id: ChatId
    message_id: MessageId
    text: str | None = None
    attachments: list[AttachmentUnion] | None = None
    parse_mode: str | None = None


class DeleteMessageRequest(CamelModel):
    """Delete message request."""

    chat_id: ChatId
    message_id: MessageId
    for_all: bool = False  # Delete for everyone


class ForwardMessageRequest(CamelModel):
    """Forward message request."""

    chat_id: ChatId
    from_chat_id: ChatId
    message_ids: list[MessageId]
    silent: bool = False


class GetHistoryRequest(CamelModel):
    """Get message history request."""

    chat_id: ChatId
    limit: int = Field(default=50, ge=1, le=200)
    before: MessageId | None = None
    after: MessageId | None = None
    around: MessageId | None = None


class GetMessagesRequest(CamelModel):
    """Get messages by IDs request."""

    chat_id: ChatId
    message_ids: list[MessageId]


class PinMessageRequest(CamelModel):
    """Pin message request."""

    chat_id: ChatId
    message_id: MessageId
    notify: bool = True


class ReactionRequest(CamelModel):
    """Add/remove reaction request."""

    chat_id: ChatId
    message_id: MessageId
    emoji: str


class ReadMessageRequest(CamelModel):
    """Mark message as read request."""

    chat_id: ChatId
    message_id: MessageId


class MessageEvent(CamelModel):
    """Message event (incoming)."""

    type: Literal[EventType.MESSAGE_NEW] = EventType.MESSAGE_NEW
    message: Message
    is_new: bool = True


class MessageEditEvent(CamelModel):
    """Message edit event."""

    message: Message
    old_text: str | None = None


class MessageDeleteEvent(CamelModel):
    """Message delete event."""

    chat_id: ChatId
    message_ids: list[MessageId]
    for_all: bool = False


class MessageReadEvent(CamelModel):
    """Message read event."""

    chat_id: ChatId
    user_id: UserId
    message_id: MessageId
    read_at: int


class TypingEvent(CamelModel):
    """Typing indicator event."""

    chat_id: ChatId
    user_id: UserId
    is_typing: bool = True


class PresenceEvent(CamelModel):
    """Presence update event."""

    user_id: UserId
    status: str  # UserStatus
    last_seen: int | None = None


class ReactionUpdateEvent(CamelModel):
    """Reaction update event."""

    chat_id: ChatId
    message_id: MessageId
    user_id: UserId
    emoji: str
    is_added: bool = True