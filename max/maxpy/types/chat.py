from __future__ import annotations

from typing import Any
from pydantic import Field, PrivateAttr
from .base import CamelModel
from .common import ChatId, UserId, MessageId, JSONDict, InviteLink
from .user import User
from ..enums import ChatType


class Chat(CamelModel):
    """Chat/Group/Channel model."""

    id: ChatId
    type: ChatType = ChatType.PRIVATE
    title: str | None = None
    username: str | None = None
    description: str | None = None
    avatar_url: str | None = None
    members_count: int = 0
    admins_count: int = 0
    is_creator: bool = False
    is_admin: bool = False
    is_member: bool = False
    is_muted: bool = False
    is_archived: bool = False
    is_pinned: bool = False
    unread_count: int = 0
    unread_mentions: int = 0
    last_message: "Message | None" = None
    draft_text: str | None = None
    created_at: int | None = None
    updated_at: int | None = None
    settings: "ChatSettings | None" = None
    invite_link: InviteLink | None = None

    # Private attribute for client reference
    _client: Any = PrivateAttr(default=None)

    def set_client(self, client: Any) -> "Chat":
        """Set client reference for convenience methods."""
        self._client = client
        return self

    @property
    def is_group(self) -> bool:
        return self.type == ChatType.GROUP

    @property
    def is_channel(self) -> bool:
        return self.type == ChatType.CHANNEL

    @property
    def is_private(self) -> bool:
        return self.type == ChatType.PRIVATE

    # Convenience methods
    async def answer(self, text: str, **kwargs) -> "Message":
        """Send a message to this chat."""
        if not self._client:
            raise RuntimeError("Client not set on chat")
        return await self._client.messages.send(self.id, text=text, **kwargs)

    async def send(self, text: str | None = None, **kwargs) -> "Message":
        """Send a message to this chat."""
        if not self._client:
            raise RuntimeError("Client not set on chat")
        return await self._client.messages.send(self.id, text=text, **kwargs)

    async def send_photo(self, photo: Any, caption: str | None = None, **kwargs) -> "Message":
        """Send a photo to this chat."""
        if not self._client:
            raise RuntimeError("Client not set on chat")
        return await self._client.messages.send_photo(self.id, photo, caption=caption, **kwargs)

    async def send_video(self, video: Any, caption: str | None = None, **kwargs) -> "Message":
        """Send a video to this chat."""
        if not self._client:
            raise RuntimeError("Client not set on chat")
        return await self._client.messages.send_video(self.id, video, caption=caption, **kwargs)

    async def send_voice(self, voice: Any, **kwargs) -> "Message":
        """Send a voice message to this chat."""
        if not self._client:
            raise RuntimeError("Client not set on chat")
        return await self._client.messages.send_voice(self.id, voice, **kwargs)

    async def send_video_note(self, video_note: Any, **kwargs) -> "Message":
        """Send a video note to this chat."""
        if not self._client:
            raise RuntimeError("Client not set on chat")
        return await self._client.messages.send_video_note(self.id, video_note, **kwargs)

    async def send_file(self, file: Any, caption: str | None = None, **kwargs) -> "Message":
        """Send a file to this chat."""
        if not self._client:
            raise RuntimeError("Client not set on chat")
        return await self._client.messages.send_file(self.id, file, caption=caption, **kwargs)

    async def history(self, limit: int = 50, **kwargs) -> list["Message"]:
        """Get message history for this chat."""
        if not self._client:
            raise RuntimeError("Client not set on chat")
        return await self._client.messages.get_history(self.id, limit=limit, **kwargs)

    async def get_message(self, message_id: MessageId) -> "Message":
        """Get a message by ID from this chat."""
        if not self._client:
            raise RuntimeError("Client not set on chat")
        return await self._client.messages.get_message(self.id, message_id)

    async def get_messages(self, message_ids: list[MessageId]) -> list["Message"]:
        """Get multiple messages by IDs from this chat."""
        if not self._client:
            raise RuntimeError("Client not set on chat")
        return await self._client.messages.get_messages(self.id, message_ids)

    async def leave(self) -> bool:
        """Leave this chat."""
        if not self._client:
            raise RuntimeError("Client not set on chat")
        if self.is_group:
            return await self._client.chats.leave_group(self.id)
        elif self.is_channel:
            return await self._client.chats.leave_channel(self.id)
        return False

    async def delete(self, last_event_time: int | None = None, for_all: bool = False) -> bool:
        """Delete this chat."""
        if not self._client:
            raise RuntimeError("Client not set on chat")
        return await self._client.chats.delete_chat(self.id, last_event_time, for_all)

    async def invite(self, user_ids: list[str], show_history: bool = False) -> bool:
        """Invite users to this chat."""
        if not self._client:
            raise RuntimeError("Client not set on chat")
        if self.is_group:
            return await self._client.chats.invite_users_to_group(self.id, user_ids, show_history)
        elif self.is_channel:
            return await self._client.chats.invite_users_to_channel(self.id, user_ids, show_history)
        return False

    async def remove_users(self, user_ids: list[str], clean_msg_period: int | None = None) -> bool:
        """Remove users from this chat."""
        if not self._client:
            raise RuntimeError("Client not set on chat")
        return await self._client.chats.remove_users_from_group(self.id, user_ids, clean_msg_period)

    async def pin_message(self, message_id: MessageId, notify: bool = True) -> bool:
        """Pin a message in this chat."""
        if not self._client:
            raise RuntimeError("Client not set on chat")
        return await self._client.messages.pin(self.id, message_id, notify)

    async def update_settings(self, **settings) -> bool:
        """Update chat settings."""
        if not self._client:
            raise RuntimeError("Client not set on chat")
        return await self._client.chats.change_group_settings(self.id, **settings)

    async def rework_invite_link(self) -> InviteLinkInfo:
        """Rework invite link for this chat."""
        if not self._client:
            raise RuntimeError("Client not set on chat")
        return await self._client.chats.rework_invite_link(self.id)

    async def get_members(self, marker: str | None = None, count: int = 100) -> list[Member]:
        """Get members of this chat."""
        if not self._client:
            raise RuntimeError("Client not set on chat")
        return await self._client.chats.get_members(self.id, marker, count)

    async def add_admin(self, user_id: str, permissions: dict | None = None) -> bool:
        """Add admin to this chat."""
        if not self._client:
            raise RuntimeError("Client not set on chat")
        return await self._client.chats.add_admin(self.id, user_id, permissions)

    async def remove_admin(self, user_id: str) -> bool:
        """Remove admin from this chat."""
        if not self._client:
            raise RuntimeError("Client not set on chat")
        return await self._client.chats.remove_admin(self.id, user_id)

    async def get_join_requests(self, marker: str | None = None) -> list[JoinRequest]:
        """Get join requests for this chat."""
        if not self._client:
            raise RuntimeError("Client not set on chat")
        return await self._client.chats.get_join_requests(self.id, marker)

    async def confirm_join_requests(self, request_ids: list[str]) -> bool:
        """Confirm join requests."""
        if not self._client:
            raise RuntimeError("Client not set on chat")
        return await self._client.chats.confirm_join_requests(self.id, request_ids)

    async def decline_join_requests(self, request_ids: list[str]) -> bool:
        """Decline join requests."""
        if not self._client:
            raise RuntimeError("Client not set on chat")
        return await self._client.chats.decline_join_requests(self.id, request_ids)


class ChatSettings(CamelModel):
    """Chat settings."""

    # Group settings
    can_add_members: bool = True
    can_change_info: bool = True
    can_pin_messages: bool = True
    can_send_media: bool = True
    can_send_stickers: bool = True
    can_send_polls: bool = True
    can_send_other: bool = True
    pre_history: bool = False  # Show history to new members

    # Channel settings
    can_post: bool = True
    can_comment: bool = True
    sign_messages: bool = False

    # Notifications
    mute_until: int | None = None  # Unix timestamp
    sound: str | None = None
    show_preview: bool = True


class Member(CamelModel):
    """Chat member."""

    user: User
    chat_id: ChatId
    role: str = "member"  # owner, admin, member
    joined_at: int | None = None
    invited_by: UserId | None = None
    is_banned: bool = False
    is_restricted: bool = False
    can_manage_chat: bool = False
    can_manage_video: bool = False
    can_delete_messages: bool = False
    can_restrict_members: bool = False
    can_promote_members: bool = False
    can_change_info: bool = False
    can_invite_users: bool = False
    can_post_messages: bool = True
    can_edit_messages: bool = True
    can_pin_messages: bool = True
    can_manage_topics: bool = False


class InviteLinkInfo(CamelModel):
    """Invite link info."""

    link: InviteLink
    chat_id: ChatId
    creator: User
    creates_join_request: bool = False
    is_primary: bool = False
    is_revoked: bool = False
    expire_date: int | None = None
    member_limit: int | None = None
    pending_join_requests: int = 0


class JoinRequest(CamelModel):
    """Join request for group/channel."""

    user: User
    chat_id: ChatId
    date: int
    bio: str | None = None
    invite_link: InviteLinkInfo | None = None


class ChatMemberUpdate(CamelModel):
    """Chat member update event."""

    chat_id: ChatId
    user: User
    old_role: str | None = None
    new_role: str | None = None
    inviter: User | None = None


class ChatUpdate(CamelModel):
    """Chat update event."""

    chat_id: ChatId
    title: str | None = None
    description: str | None = None
    avatar_url: str | None = None
    settings: ChatSettings | None = None
    username: str | None = None


class CreateGroupRequest(CamelModel):
    """Create group request."""

    name: str
    participant_ids: list[UserId]
    notify: bool = True


class CreateChannelRequest(CamelModel):
    """Create channel request."""

    name: str
    description: str | None = None


class ChangeGroupSettingsRequest(CamelModel):
    """Change group settings request."""

    chat_id: ChatId
    name: str | None = None
    description: str | None = None
    can_add_members: bool | None = None
    can_change_info: bool | None = None
    can_pin_messages: bool | None = None
    can_send_media: bool | None = None
    can_send_stickers: bool | None = None
    can_send_polls: bool | None = None
    can_send_other: bool | None = None
    pre_history: bool | None = None


class ChangeGroupProfileRequest(CamelModel):
    """Change group profile request."""

    chat_id: ChatId
    name: str | None = None
    description: str | None = None
    photo: "File | None" = None  # Forward reference


class ResolveLinkResponse(CamelModel):
    """Resolve invite link response."""

    chat: Chat
    join_request: bool = False


class GetMembersRequest(CamelModel):
    """Get chat members request."""

    chat_id: ChatId
    marker: str | None = None
    count: int = Field(default=100, ge=1, le=200)


class GetMembersResponse(CamelModel):
    """Get chat members response."""

    members: list[Member]
    next_marker: str | None = None


class JoinRequestListResponse(CamelModel):
    """Join request list response."""

    requests: list[JoinRequest]
    next_marker: str | None = None