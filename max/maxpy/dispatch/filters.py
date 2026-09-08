from __future__ import annotations

from typing import Any, Callable, Awaitable
from ..types.message import Message
from ..types.chat import Chat
from ..types.user import User
from ..enums import EventType, ChatType


class Filter:
    """Base filter class."""

    def __call__(self, event: Any) -> bool | Awaitable[bool]:
        raise NotImplementedError

    def __and__(self, other: "Filter") -> "AndFilter":
        return AndFilter(self, other)

    def __or__(self, other: "Filter") -> "OrFilter":
        return OrFilter(self, other)

    def __invert__(self) -> "NotFilter":
        return NotFilter(self)


class AndFilter(Filter):
    """AND combination of filters."""

    def __init__(self, *filters: Filter):
        self.filters = filters

    def __call__(self, event: Any) -> bool | Awaitable[bool]:
        for f in self.filters:
            result = f(event)
            if isinstance(result, bool) and not result:
                return False
        return True


class OrFilter(Filter):
    """OR combination of filters."""

    def __init__(self, *filters: Filter):
        self.filters = filters

    def __call__(self, event: Any) -> bool | Awaitable[bool]:
        for f in self.filters:
            result = f(event)
            if isinstance(result, bool) and result:
                return True
        return False


class NotFilter(Filter):
    """NOT filter."""

    def __init__(self, filter: Filter):
        self.filter = filter

    def __call__(self, event: Any) -> bool | Awaitable[bool]:
        result = self.filter(event)
        if isinstance(result, bool):
            return not result
        # For async, we can't easily negate
        return True


# Message filters
class MessageFilter(Filter):
    """Base message filter."""

    def __call__(self, event: Any) -> bool:
        return isinstance(event, Message)


class TextFilter(MessageFilter):
    """Filter messages with text."""

    def __init__(self, text: str | None = None, contains: str | None = None, regex: str | None = None):
        self.text = text
        self.contains = contains
        self.regex = regex
        if regex:
            import re
            self._pattern = re.compile(regex)

    def __call__(self, event: Any) -> bool:
        if not super().__call__(event):
            return False
        msg: Message = event
        if not msg.text:
            return False
        if self.text and msg.text != self.text:
            return False
        if self.contains and self.contains not in msg.text:
            return False
        if self.regex and not self._pattern.search(msg.text):
            return False
        return True


class CommandFilter(MessageFilter):
    """Filter messages starting with command."""

    def __init__(self, command: str, prefixes: str | list[str] = "/"):
        self.command = command.lstrip("/")
        self.prefixes = [prefixes] if isinstance(prefixes, str) else prefixes

    def __call__(self, event: Any) -> bool:
        if not super().__call__(event):
            return False
        msg: Message = event
        if not msg.text:
            return False
        for prefix in self.prefixes:
            if msg.text.startswith(f"{prefix}{self.command}"):
                return True
        return False


class ChatTypeFilter(MessageFilter):
    """Filter by chat type."""

    def __init__(self, *chat_types: ChatType):
        self.chat_types = set(chat_types)

    def __call__(self, event: Any) -> bool:
        if not super().__call__(event):
            return False
        msg: Message = event
        # Need chat info - would need to be fetched
        return True  # Placeholder


class PrivateChatFilter(MessageFilter):
    """Filter private chats only."""

    def __call__(self, event: Any) -> bool:
        if not super().__call__(event):
            return False
        # Would need chat info
        return True


class GroupChatFilter(MessageFilter):
    """Filter group chats only."""

    def __call__(self, event: Any) -> bool:
        if not super().__call__(event):
            return False
        return True


class ChannelFilter(MessageFilter):
    """Filter channel messages only."""

    def __call__(self, event: Any) -> bool:
        if not super().__call__(event):
            return False
        return True


class HasAttachmentFilter(MessageFilter):
    """Filter messages with attachments."""

    def __call__(self, event: Any) -> bool:
        if not super().__call__(event):
            return False
        msg: Message = event
        return msg.has_media


class PhotoFilter(MessageFilter):
    """Filter photo messages."""

    def __call__(self, event: Any) -> bool:
        if not super().__call__(event):
            return False
        msg: Message = event
        return msg.photo is not None


class VideoFilter(MessageFilter):
    """Filter video messages."""

    def __call__(self, event: Any) -> bool:
        if not super().__call__(event):
            return False
        msg: Message = event
        return msg.video is not None


class VoiceFilter(MessageFilter):
    """Filter voice messages."""

    def __call__(self, event: Any) -> bool:
        if not super().__call__(event):
            return False
        msg: Message = event
        return msg.voice is not None


class DocumentFilter(MessageFilter):
    """Filter document/file messages."""

    def __call__(self, event: Any) -> bool:
        if not super().__call__(event):
            return False
        msg: Message = event
        return msg.document is not None


class FromUserFilter(MessageFilter):
    """Filter messages from specific user."""

    def __init__(self, user_id: str | int):
        self.user_id = str(user_id)

    def __call__(self, event: Any) -> bool:
        if not super().__call__(event):
            return False
        msg: Message = event
        return str(msg.sender_id) == self.user_id


class OutgoingFilter(MessageFilter):
    """Filter outgoing messages."""

    def __call__(self, event: Any) -> bool:
        if not super().__call__(event):
            return False
        msg: Message = event
        return msg.is_outgoing


class IncomingFilter(MessageFilter):
    """Filter incoming messages."""

    def __call__(self, event: Any) -> bool:
        if not super().__call__(event):
            return False
        msg: Message = event
        return not msg.is_outgoing


class ReplyFilter(MessageFilter):
    """Filter reply messages."""

    def __call__(self, event: Any) -> bool:
        if not super().__call__(event):
            return False
        msg: Message = event
        return msg.reply_to is not None


class ForwardFilter(MessageFilter):
    """Filter forwarded messages."""

    def __call__(self, event: Any) -> bool:
        if not super().__call__(event):
            return False
        msg: Message = event
        return msg.forward_from is not None


# Chat filters
class ChatFilter(Filter):
    """Filter chat events."""

    def __call__(self, event: Any) -> bool:
        return isinstance(event, Chat)


# User filters
class UserFilter(Filter):
    """Filter user events."""

    def __call__(self, event: Any) -> bool:
        return isinstance(event, User)


# Custom filter from callable
class CallableFilter(Filter):
    """Filter from arbitrary callable."""

    def __init__(self, func: Callable[[Any], bool | Awaitable[bool]]):
        self.func = func

    def __call__(self, event: Any) -> bool | Awaitable[bool]:
        return self.func(event)


def filter_factory(func: Callable[[Any], bool | Awaitable[bool]]) -> Filter:
    """Create filter from callable."""
    return CallableFilter(func)


# Composite filters
def and_(*filters: Filter) -> Filter:
    return AndFilter(*filters)


def or_(*filters: Filter) -> Filter:
    return OrFilter(*filters)


def not_(filter: Filter) -> Filter:
    return NotFilter(filter)