from __future__ import annotations

from typing import Any
from ..types.message import (
    SendMessageRequest,
    EditMessageRequest,
    DeleteMessageRequest,
    ForwardMessageRequest,
    GetHistoryRequest,
    GetMessagesRequest,
    PinMessageRequest,
    ReactionRequest,
    ReadMessageRequest,
    Message,
)
from ..types.chat import (
    Chat,
    CreateGroupRequest,
    CreateChannelRequest,
    ChangeGroupSettingsRequest,
    ChangeGroupProfileRequest,
    GetMembersRequest,
    InviteLinkInfo,
    JoinRequest,
    Member,
)
from ..types.user import User, Profile, ContactInfo, Session
from ..types.file import (
    Photo,
    Video,
    Voice,
    VideoNote,
    Document,
    UploadResponse,
    DownloadResponse,
)
from ..enums import EventType
from ..exceptions import APIError


class MessageService:
    """Message operations service."""

    def __init__(self, client: "MaxClient"):
        self.client = client

    async def send(
        self,
        chat_id: str,
        text: str | None = None,
        attachments: list = None,
        reply_to: str | None = None,
        forward_from: str | None = None,
        send_at: int | None = None,
        link_preview: bool = True,
        silent: bool = False,
        parse_mode: str | None = None,
    ) -> Message:
        """Send a message."""
        request = SendMessageRequest(
            chat_id=chat_id,
            text=text,
            attachments=attachments or [],
            reply_to=reply_to,
            forward_from=forward_from,
            send_at=send_at,
            link_preview=link_preview,
            silent=silent,
            parse_mode=parse_mode,
        )
        return await self.client._send_request("send_message", request)

    async def send_text(self, chat_id: str, text: str, **kwargs) -> Message:
        """Send text message."""
        return await self.send(chat_id, text=text, **kwargs)

    async def send_photo(self, chat_id: str, photo: Photo, caption: str | None = None, **kwargs) -> Message:
        """Send photo."""
        return await self.send(chat_id, text=caption, attachments=[photo], **kwargs)

    async def send_video(self, chat_id: str, video: Video, caption: str | None = None, **kwargs) -> Message:
        """Send video."""
        return await self.send(chat_id, text=caption, attachments=[video], **kwargs)

    async def send_voice(self, chat_id: str, voice: Voice, **kwargs) -> Message:
        """Send voice message."""
        return await self.send(chat_id, attachments=[voice], **kwargs)

    async def send_video_note(self, chat_id: str, video_note: VideoNote, **kwargs) -> Message:
        """Send video note."""
        return await self.send(chat_id, attachments=[video_note], **kwargs)

    async def send_file(self, chat_id: str, file: Document, caption: str | None = None, **kwargs) -> Message:
        """Send file."""
        return await self.send(chat_id, text=caption, attachments=[file], **kwargs)

    async def send_poll(self, chat_id: str, poll, **kwargs) -> Message:
        """Send poll."""
        return await self.send(chat_id, attachments=[poll], **kwargs)

    async def edit(self, chat_id: str, message_id: str, text: str | None = None, **kwargs) -> Message:
        """Edit message."""
        request = EditMessageRequest(chat_id=chat_id, message_id=message_id, text=text, **kwargs)
        return await self.client._send_request("edit_message", request)

    async def delete(self, chat_id: str, message_id: str, for_all: bool = False) -> bool:
        """Delete message."""
        request = DeleteMessageRequest(chat_id=chat_id, message_id=message_id, for_all=for_all)
        return await self.client._send_request("delete_message", request)

    async def forward(
        self,
        chat_id: str,
        from_chat_id: str,
        message_ids: list[str],
        silent: bool = False,
    ) -> list[Message]:
        """Forward messages."""
        request = ForwardMessageRequest(
            chat_id=chat_id,
            from_chat_id=from_chat_id,
            message_ids=message_ids,
            silent=silent,
        )
        return await self.client._send_request("forward_message", request)

    async def get_history(
        self,
        chat_id: str,
        limit: int = 50,
        before: str | None = None,
        after: str | None = None,
        around: str | None = None,
    ) -> list[Message]:
        """Get message history."""
        request = GetHistoryRequest(
            chat_id=chat_id,
            limit=limit,
            before=before,
            after=after,
            around=around,
        )
        return await self.client._send_request("get_history", request)

    async def get_message(self, chat_id: str, message_id: str) -> Message:
        """Get single message by ID."""
        request = GetMessagesRequest(chat_id=chat_id, message_ids=[message_id])
        messages = await self.client._send_request("get_messages", request)
        return messages[0] if messages else None

    async def get_messages(self, chat_id: str, message_ids: list[str]) -> list[Message]:
        """Get multiple messages by IDs."""
        request = GetMessagesRequest(chat_id=chat_id, message_ids=message_ids)
        return await self.client._send_request("get_messages", request)

    async def pin(self, chat_id: str, message_id: str, notify: bool = True) -> bool:
        """Pin message."""
        request = PinMessageRequest(chat_id=chat_id, message_id=message_id, notify=notify)
        return await self.client._send_request("pin_message", request)

    async def unpin(self, chat_id: str, message_id: str) -> bool:
        """Unpin message."""
        return await self.client._send_request("unpin_message", {"chat_id": chat_id, "message_id": message_id})

    async def add_reaction(self, chat_id: str, message_id: str, emoji: str) -> bool:
        """Add reaction."""
        request = ReactionRequest(chat_id=chat_id, message_id=message_id, emoji=emoji)
        return await self.client._send_request("add_reaction", request)

    async def remove_reaction(self, chat_id: str, message_id: str, emoji: str) -> bool:
        """Remove reaction."""
        return await self.client._send_request("remove_reaction", {"chat_id": chat_id, "message_id": message_id, "emoji": emoji})

    async def get_reactions(self, chat_id: str, message_id: str) -> list:
        """Get reactions."""
        return await self.client._send_request("get_reactions", {"chat_id": chat_id, "message_id": message_id})

    async def read(self, chat_id: str, message_id: str) -> bool:
        """Mark message as read."""
        request = ReadMessageRequest(chat_id=chat_id, message_id=message_id)
        return await self.client._send_request("read_message", request)

    async def vote_poll(self, chat_id: str, message_id: str, option_ids: list[int]) -> bool:
        """Vote in poll."""
        return await self.client._send_request("vote_poll", {"chat_id": chat_id, "message_id": message_id, "option_ids": option_ids})

    async def get_poll_state(self, chat_id: str, message_id: str):
        """Get poll state."""
        return await self.client._send_request("get_poll_state", {"chat_id": chat_id, "message_id": message_id})


class ChatService:
    """Chat operations service."""

    def __init__(self, client: "MaxClient"):
        self.client = client

    async def get_chat(self, chat_id: str) -> Chat:
        """Get chat info."""
        return await self.client._send_request("get_chat", {"chat_id": chat_id})

    async def get_chats(self, chat_ids: list[str] | None = None) -> list[Chat]:
        """Get multiple chats."""
        return await self.client._send_request("get_chats", {"chat_ids": chat_ids})

    async def fetch_chats(self, marker: str | None = None) -> list[Chat]:
        """Fetch chat list."""
        return await self.client._send_request("fetch_chats", {"marker": marker})

    async def create_group(self, name: str, participant_ids: list[str], notify: bool = True) -> Chat:
        """Create group chat."""
        request = CreateGroupRequest(name=name, participant_ids=participant_ids, notify=notify)
        return await self.client._send_request("create_group", request)

    async def create_channel(self, name: str, description: str | None = None) -> Chat:
        """Create channel."""
        request = CreateChannelRequest(name=name, description=description)
        return await self.client._send_request("create_channel", request)

    async def invite_users_to_group(self, chat_id: str, user_ids: list[str], show_history: bool = False) -> bool:
        """Invite users to group."""
        return await self.client._send_request("invite_to_group", {"chat_id": chat_id, "user_ids": user_ids, "show_history": show_history})

    async def invite_users_to_channel(self, chat_id: str, user_ids: list[str], show_history: bool = False) -> bool:
        """Invite users to channel."""
        return await self.client._send_request("invite_to_channel", {"chat_id": chat_id, "user_ids": user_ids, "show_history": show_history})

    async def remove_users_from_group(self, chat_id: str, user_ids: list[str], clean_msg_period: int | None = None) -> bool:
        """Remove users from group."""
        return await self.client._send_request("remove_from_group", {"chat_id": chat_id, "user_ids": user_ids, "clean_msg_period": clean_msg_period})

    async def change_group_settings(self, chat_id: str, **settings) -> bool:
        """Change group settings."""
        request = ChangeGroupSettingsRequest(chat_id=chat_id, **settings)
        return await self.client._send_request("change_group_settings", request)

    async def change_group_profile(self, chat_id: str, name: str | None = None, description: str | None = None, photo: Any | None = None) -> bool:
        """Change group profile."""
        request = ChangeGroupProfileRequest(chat_id=chat_id, name=name, description=description, photo=photo)
        return await self.client._send_request("change_group_profile", request)

    async def join_group(self, link: str) -> Chat:
        """Join group by invite link."""
        return await self.client._send_request("join_group", {"link": link})

    async def join_channel(self, link: str) -> Chat:
        """Join channel by invite link."""
        return await self.client._send_request("join_channel", {"link": link})

    async def resolve_link(self, link: str) -> InviteLinkInfo:
        """Resolve invite link."""
        return await self.client._send_request("resolve_link", {"link": link})

    async def rework_invite_link(self, chat_id: str) -> InviteLinkInfo:
        """Rework invite link."""
        return await self.client._send_request("rework_invite_link", {"chat_id": chat_id})

    async def get_members(self, chat_id: str, marker: str | None = None, count: int = 100) -> list[Member]:
        """Get chat members."""
        request = GetMembersRequest(chat_id=chat_id, marker=marker, count=count)
        return await self.client._send_request("get_members", request)

    async def leave_group(self, chat_id: str) -> bool:
        """Leave group."""
        return await self.client._send_request("leave_group", {"chat_id": chat_id})

    async def leave_channel(self, chat_id: str) -> bool:
        """Leave channel."""
        return await self.client._send_request("leave_channel", {"chat_id": chat_id})

    async def delete_chat(self, chat_id: str, last_event_time: int | None = None, for_all: bool = False) -> bool:
        """Delete chat."""
        return await self.client._send_request("delete_chat", {"chat_id": chat_id, "last_event_time": last_event_time, "for_all": for_all})

    async def add_admin(self, chat_id: str, user_id: str, permissions: dict | None = None) -> bool:
        """Add admin."""
        return await self.client._send_request("add_admin", {"chat_id": chat_id, "user_id": user_id, "permissions": permissions})

    async def remove_admin(self, chat_id: str, user_id: str) -> bool:
        """Remove admin."""
        return await self.client._send_request("remove_admin", {"chat_id": chat_id, "user_id": user_id})

    async def get_join_requests(self, chat_id: str, marker: str | None = None) -> list[JoinRequest]:
        """Get join requests."""
        return await self.client._send_request("get_join_requests", {"chat_id": chat_id, "marker": marker})

    async def confirm_join_requests(self, chat_id: str, request_ids: list[str]) -> bool:
        """Confirm join requests."""
        return await self.client._send_request("confirm_join_requests", {"chat_id": chat_id, "request_ids": request_ids})

    async def decline_join_requests(self, chat_id: str, request_ids: list[str]) -> bool:
        """Decline join requests."""
        return await self.client._send_request("decline_join_requests", {"chat_id": chat_id, "request_ids": request_ids})


class UserService:
    """User operations service."""

    def __init__(self, client: "MaxClient"):
        self.client = client

    async def get_user(self, user_id: str) -> User:
        """Get user by ID."""
        return await self.client._send_request("get_user", {"user_id": user_id})

    async def get_users(self, user_ids: list[str]) -> list[User]:
        """Get multiple users."""
        return await self.client._send_request("get_users", {"user_ids": user_ids})

    async def get_cached_user(self, user_id: str) -> User | None:
        """Get cached user."""
        return self.client._cache.get_user(user_id)

    async def fetch_users(self, user_ids: list[str]) -> list[User]:
        """Fetch users from server."""
        return await self.client._send_request("fetch_users", {"user_ids": user_ids})

    async def search_by_phone(self, phone: str) -> User | None:
        """Search user by phone."""
        return await self.client._send_request("search_by_phone", {"phone": phone})

    async def get_sessions(self) -> list[Session]:
        """Get active sessions."""
        return await self.client._send_request("get_sessions", {})

    async def close_session(self, session_id: str) -> bool:
        """Close session."""
        return await self.client._send_request("close_session", {"session_id": session_id})

    async def close_all_sessions(self) -> bool:
        """Close all other sessions."""
        return await self.client._send_request("close_all_sessions", {})

    async def add_contact(self, contact_id: str) -> bool:
        """Add contact."""
        return await self.client._send_request("add_contact", {"contact_id": contact_id})

    async def remove_contact(self, contact_id: str) -> bool:
        """Remove contact."""
        return await self.client._send_request("remove_contact", {"contact_id": contact_id})

    async def import_contacts(self, contacts: list[ContactInfo]) -> dict:
        """Import contacts."""
        return await self.client._send_request("import_contacts", {"contacts": [c.model_dump() for c in contacts]})

    async def get_chat_id(self, user_id1: str, user_id2: str) -> str:
        """Compute private chat ID."""
        ids = sorted([str(user_id1), str(user_id2)])
        return f"{ids[0]}_{ids[1]}"


class FileService:
    """File operations service."""

    def __init__(self, client: "MaxClient"):
        self.client = client

    async def upload_photo(self, photo: Photo, profile: bool = False) -> UploadResponse:
        """Upload photo."""
        return await self.client._upload_file(photo, "photo", profile=profile)

    async def upload_video(self, video: Video) -> UploadResponse:
        """Upload video."""
        return await self.client._upload_file(video, "video")

    async def upload_voice(self, voice: Voice) -> UploadResponse:
        """Upload voice."""
        return await self.client._upload_file(voice, "voice")

    async def upload_video_note(self, video_note: VideoNote) -> UploadResponse:
        """Upload video note."""
        return await self.client._upload_file(video_note, "video_note")

    async def upload_file(self, file: Document) -> UploadResponse:
        """Upload generic file."""
        return await self.client._upload_file(file, "file")

    async def download_file(self, chat_id: str, message_id: str, file_id: str) -> DownloadResponse:
        """Get file download URL."""
        return await self.client._send_request("download_file", {"chat_id": chat_id, "message_id": message_id, "file_id": file_id})

    async def download_video(self, chat_id: str, message_id: str, video_id: str) -> DownloadResponse:
        """Get video download URL."""
        return await self.client._send_request("download_video", {"chat_id": chat_id, "message_id": message_id, "video_id": video_id})


class SelfService:
    """Self/profile operations service."""

    def __init__(self, client: "MaxClient"):
        self.client = client

    async def get_profile(self) -> Profile:
        """Get own profile."""
        return await self.client._send_request("get_profile", {})

    async def update_profile(self, first_name: str | None = None, last_name: str | None = None, bio: str | None = None, username: str | None = None) -> Profile:
        """Update profile."""
        return await self.client._send_request("update_profile", {"first_name": first_name, "last_name": last_name, "bio": bio, "username": username})

    async def change_profile_photo(self, photo: Photo) -> bool:
        """Change profile photo."""
        return await self.client._upload_file(photo, "profile_photo")

    async def get_folders(self) -> list:
        """Get chat folders."""
        return await self.client._send_request("get_folders", {})

    async def update_folder(self, folder_id: int, name: str | None = None, chat_ids: list[str] | None = None, pinned_chat_ids: list[str] | None = None, order: int | None = None) -> bool:
        """Update folder."""
        return await self.client._send_request("update_folder", {"folder_id": folder_id, "name": name, "chat_ids": chat_ids, "pinned_chat_ids": pinned_chat_ids, "order": order})

    async def delete_folder(self, folder_id: int) -> bool:
        """Delete folder."""
        return await self.client._send_request("delete_folder", {"folder_id": folder_id})

    async def get_privacy(self) -> dict:
        """Get privacy settings."""
        return await self.client._send_request("get_privacy", {})

    async def set_privacy(self, settings: dict) -> bool:
        """Set privacy settings."""
        return await self.client._send_request("set_privacy", settings)


class BotService:
    """Bot operations service."""

    def __init__(self, client: "MaxClient"):
        self.client = client

    async def get_info(self) -> dict:
        """Get bot info."""
        return await self.client._send_request("bot_get_info", {})

    async def send(self, chat_id: str, text: str, **kwargs) -> dict:
        """Send message as bot."""
        return await self.client._send_request("bot_send", {"chat_id": chat_id, "text": text, **kwargs})


class AuthService:
    """Authentication service."""

    def __init__(self, client: "MaxClient"):
        self.client = client

    async def logout(self) -> bool:
        """Logout current session."""
        return await self.client._send_request("logout", {})

    async def set_2fa(self, password: str, email: str | None = None, hint: str | None = None) -> bool:
        """Set 2FA password."""
        return await self.client._send_request("set_2fa", {"password": password, "email": email, "hint": hint})

    async def remove_2fa(self, password: str) -> bool:
        """Remove 2FA password."""
        return await self.client._send_request("remove_2fa", {"password": password})

    async def change_password(self, old_password: str, new_password: str) -> bool:
        """Change 2FA password."""
        return await self.client._send_request("change_password", {"old_password": old_password, "new_password": new_password})


class ApiFacade:
    """Aggregates all API services."""

    def __init__(self, client: "MaxClient"):
        self.client = client
        self.messages = MessageService(client)
        self.chats = ChatService(client)
        self.users = UserService(client)
        self.files = FileService(client)
        self.self = SelfService(client)
        self.bots = BotService(client)
        self.auth = AuthService(client)