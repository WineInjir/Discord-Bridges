from __future__ import annotations

from typing import Any, NewType, Union
from pydantic import Field
from .base import CamelModel


# Type aliases for clarity
ChatId = NewType("ChatId", str)
UserId = NewType("UserId", str)
MessageId = NewType("MessageId", str)
FileId = NewType("FileId", str)
SessionId = NewType("SessionId", str)
InviteLink = NewType("InviteLink", str)
PhoneNumber = NewType("PhoneNumber", str)


class ChatIdUnion(CamelModel):
    """Union type for chat identifiers."""

    chat_id: str | int = Field(..., description="Chat ID (string or numeric)")

    def __str__(self) -> str:
        return str(self.chat_id)


class UserIdUnion(CamelModel):
    """Union type for user identifiers."""

    user_id: str | int = Field(..., description="User ID (string or numeric)")

    def __str__(self) -> str:
        return str(self.user_id)


class MessageIdUnion(CamelModel):
    """Union type for message identifiers."""

    message_id: str | int = Field(..., description="Message ID (string or numeric)")

    def __str__(self) -> str:
        return str(self.message_id)


# Common request/response wrappers
class BaseRequest(CamelModel):
    """Base request model."""

    pass


class BaseResponse(CamelModel):
    """Base response model."""

    success: bool = True


class ErrorResponse(CamelModel):
    """Error response from API."""

    code: int | None = None
    error: str | None = None
    message: str | None = None
    details: dict[str, Any] | None = None


class PaginationParams(CamelModel):
    """Pagination parameters."""

    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)
    marker: str | None = None


class PaginatedResponse(CamelModel):
    """Paginated response wrapper."""

    items: list[Any] = []
    total: int | None = None
    next_marker: str | None = None
    has_more: bool = False


class DateTimeRange(CamelModel):
    """Date/time range for queries."""

    from_ts: int | None = Field(default=None, alias="from")
    to_ts: int | None = Field(default=None, alias="to")


# Utility types
JSONDict = dict[str, Any]
JSONList = list[Any]