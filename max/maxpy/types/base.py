from __future__ import annotations

from typing import Any, ClassVar
from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    """Base model with camelCase aliases and extra fields allowed."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        arbitrary_types_allowed=True,
        extra="allow",
        str_strip_whitespace=True,
        validate_assignment=True,
        ser_json_timedelta="iso8601",
        ser_json_bytes="base64",
    )

    # Class variable to track if this model has been initialized
    _initialized: ClassVar[bool] = False

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        cls._initialized = True


class TimestampMixin:
    """Mixin for timestamp fields."""

    timestamp: int | None = None  # Unix timestamp in milliseconds


class Identifiable:
    """Mixin for identifiable objects."""

    id: str | int | None = None