from __future__ import annotations

from typing import Any
from pydantic import Field, PrivateAttr
from .base import CamelModel
from .common import ChatId, UserId, PhoneNumber, JSONDict


class User(CamelModel):
    """User model."""

    id: UserId
    phone: PhoneNumber | None = None
    first_name: str | None = None
    last_name: str | None = None
    username: str | None = None
    is_bot: bool = False
    is_verified: bool = False
    is_premium: bool = False
    status: str | None = None  # UserStatus enum value
    last_seen: int | None = None  # Unix timestamp
    avatar_url: str | None = None
    bio: str | None = None

    # Private attribute for client reference
    _client: Any = PrivateAttr(default=None)

    def set_client(self, client: Any) -> "User":
        """Set client reference for convenience methods."""
        self._client = client
        return self

    def get_full_name(self) -> str:
        parts = []
        if self.first_name:
            parts.append(self.first_name)
        if self.last_name:
            parts.append(self.last_name)
        return " ".join(parts) or self.username or str(self.id)

    def get_chat_id(self, other_user_id: UserId) -> ChatId:
        """Compute private chat ID with another user."""
        # MAX uses sorted user IDs for private chat IDs
        ids = sorted([str(self.id), str(other_user_id)])
        return ChatId(f"{ids[0]}_{ids[1]}")

    # Convenience methods
    async def add_contact(self) -> bool:
        """Add this user as a contact."""
        if not self._client:
            raise RuntimeError("Client not set on user")
        return await self._client.users.add_contact(str(self.id))

    async def remove_contact(self) -> bool:
        """Remove this user from contacts."""
        if not self._client:
            raise RuntimeError("Client not set on user")
        return await self._client.users.remove_contact(str(self.id))

    async def get_chat_id_with(self, other_user_id: UserId) -> ChatId:
        """Get private chat ID with another user."""
        return self.get_chat_id(other_user_id)


class Profile(CamelModel):
    """Current user profile."""

    user: User
    settings: JSONDict | None = None
    folders: list["Folder"] | None = None
    privacy: "PrivacySettings | None" = None


class Contact(CamelModel):
    """Contact from phone book."""

    phone: PhoneNumber
    first_name: str
    last_name: str | None = None
    user_id: UserId | None = None
    is_registered: bool = False


class ContactInfo(CamelModel):
    """Contact info for import."""

    phone: PhoneNumber
    first_name: str
    last_name: str | None = None


class Session(CamelModel):
    """Active session."""

    id: SessionId
    device_name: str | None = None
    device_type: str | None = None
    platform: str | None = None
    app_version: str | None = None
    system_version: str | None = None
    ip: str | None = None
    country: str | None = None
    city: str | None = None
    created_at: int  # Unix timestamp
    last_active: int  # Unix timestamp
    is_current: bool = False


class Folder(CamelModel):
    """Chat folder."""

    id: int
    name: str
    chat_ids: list[ChatId] = []
    pinned_chat_ids: list[ChatId] = []
    order: int = 0
    is_default: bool = False


class FolderUpdate(CamelModel):
    """Folder update request."""

    name: str | None = None
    chat_ids: list[ChatId] | None = None
    pinned_chat_ids: list[ChatId] | None = None
    order: int | None = None


class PrivacySettings(CamelModel):
    """Privacy settings."""

    last_seen: str = "everyone"  # everyone, contacts, nobody
    profile_photo: str = "everyone"
    phone_number: str = "everyone"
    forward_messages: str = "everyone"
    groups: str = "everyone"
    calls: str = "everyone"


class SyncState(CamelModel):
    """Sync state markers."""

    chats: str | None = None
    contacts: str | None = None
    drafts: str | None = None
    presence: str | None = None


class SyncOverrides(CamelModel):
    """Sync overrides for login."""

    chats: bool = True
    contacts: bool = True
    drafts: bool = True
    presence: bool = True


class LoginResponse(CamelModel):
    """Login response."""

    token: str
    user: User
    sync_state: SyncState | None = None
    config_hash: str | None = None


class Login2Response(CamelModel):
    """Login2 response (after handshake)."""

    token: str
    user: User
    sync_state: SyncState | None = None
    config_hash: str | None = None
    flags: int = 0


class Login2Flags:
    """Login2 flags."""

    HAS_CHATS = 1
    HAS_CONTACTS = 2
    HAS_DRAFTS = 4
    HAS_PRESENCE = 8


class HandshakeResponse(CamelModel):
    """Handshake response."""

    salt: str
    version: str
    features: list[str] = []


class RegisterTokenResponse(CamelModel):
    """Registration token response."""

    token: str
    phone: PhoneNumber


class ImportContactsResponse(CamelModel):
    """Import contacts response."""

    imported: int = 0
    failed: list[ContactInfo] = []
    phone_to_user_id: dict[PhoneNumber, UserId] = {}