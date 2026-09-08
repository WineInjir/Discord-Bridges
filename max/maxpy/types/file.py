from __future__ import annotations

import os
import mimetypes
from pathlib import Path
from typing import Any, AsyncGenerator, Literal
from pydantic import Field, field_validator, model_validator
from .base import CamelModel
from ..enums import (
    ALLOWED_PHOTO_EXTENSIONS,
    ALLOWED_VIDEO_EXTENSIONS,
    ALLOWED_VOICE_EXTENSIONS,
    ALLOWED_VIDEO_NOTE_EXTENSIONS,
    MIME_TYPE_MAP,
    MAX_PHOTO_SIZE,
    MAX_VIDEO_SIZE,
    MAX_VOICE_SIZE,
    MAX_FILE_SIZE,
)


class BaseFile(CamelModel):
    """Base file abstraction for uploads."""

    # Only one of these should be set
    raw: bytes | None = Field(default=None, exclude=True)
    path: str | None = None
    url: str | None = None

    # Metadata
    name: str | None = None
    mime_type: str | None = None
    size: int | None = None

    def __init__(self, **data):
        # Handle path-like objects
        if "path" in data and data["path"] is not None:
            data["path"] = str(data["path"])
        super().__init__(**data)

    @model_validator(mode="before")
    @classmethod
    def set_defaults(cls, data: dict[str, Any]) -> dict[str, Any]:
        """Set default values for name, mime_type, size from path/url/raw."""
        data = data.copy()
        
        # Set name from path if not provided
        if "name" not in data or data["name"] is None:
            path = data.get("path")
            if path:
                data["name"] = Path(path).name
        
        # Set mime_type from name if not provided
        if "mime_type" not in data or data["mime_type"] is None:
            name = data.get("name")
            if name:
                mime, _ = mimetypes.guess_type(name)
                data["mime_type"] = mime
        
        # Set size from raw/path if not provided
        if "size" not in data or data["size"] is None:
            raw = data.get("raw")
            if raw is not None:
                data["size"] = len(raw)
            else:
                path = data.get("path")
                if path and os.path.exists(path):
                    data["size"] = os.path.getsize(path)
        
        return data

    @model_validator(mode="after")
    def validate_source(self) -> BaseFile:
        sources = sum(1 for x in (self.raw, self.path, self.url) if x is not None)
        if sources != 1:
            raise ValueError("Exactly one of raw, path, or url must be provided")
        return self

    async def read(self) -> bytes:
        """Read entire file content."""
        if self.raw is not None:
            return self.raw
        if self.path is not None:
            with open(self.path, "rb") as f:
                return f.read()
        if self.url is not None:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(self.url) as resp:
                    return await resp.read()
        raise ValueError("No file source available")

    def get_size(self) -> int:
        """Get file size synchronously."""
        if self.size is not None:
            return self.size
        if self.raw is not None:
            return len(self.raw)
        if self.path is not None and os.path.exists(self.path):
            return os.path.getsize(self.path)
        return 0

    async def iter_chunks(self, chunk_size: int = 1024 * 1024) -> AsyncGenerator[bytes, None]:
        """Iterate file in chunks."""
        if self.raw is not None:
            for i in range(0, len(self.raw), chunk_size):
                yield self.raw[i : i + chunk_size]
            return

        if self.path is not None:
            with open(self.path, "rb") as f:
                while chunk := f.read(chunk_size):
                    yield chunk
            return

        if self.url is not None:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(self.url) as resp:
                    async for chunk in resp.content.iter_chunked(chunk_size):
                        yield chunk
            return

        raise ValueError("No file source available")

    def validate_extension(self, allowed: set[str]) -> tuple[str, str]:
        """Validate file extension and return (ext, mime_type)."""
        if not self.name:
            raise ValueError("File name required for validation")
        ext = Path(self.name).suffix.lower().lstrip(".")
        if ext not in allowed:
            raise ValueError(f"Extension .{ext} not allowed. Allowed: {allowed}")
        mime = self.mime_type or MIME_TYPE_MAP.get(ext, "application/octet-stream")
        return ext, mime

    async def validate_size(self, max_size: int) -> None:
        """Validate file size."""
        size = self.get_size()
        if size == 0:
            # Need to read to get size
            if self.url:
                import aiohttp
                async with aiohttp.ClientSession() as session:
                    async with session.head(self.url) as resp:
                        size = int(resp.headers.get("Content-Length", 0))
            elif self.path:
                size = os.path.getsize(self.path)
            elif self.raw:
                size = len(self.raw)

        if size > max_size:
            raise ValueError(f"File size {size} exceeds maximum {max_size}")


class Photo(BaseFile):
    """Photo file."""

    @model_validator(mode="after")
    def validate_photo(self) -> Photo:
        self.validate_extension(ALLOWED_PHOTO_EXTENSIONS)
        return self

    async def validate_for_upload(self) -> None:
        await self.validate_size(MAX_PHOTO_SIZE)
        self.validate_extension(ALLOWED_PHOTO_EXTENSIONS)


class Video(BaseFile):
    """Video file."""

    duration: int | None = None  # seconds
    width: int | None = None
    height: int | None = None

    @model_validator(mode="after")
    def validate_video(self) -> Video:
        self.validate_extension(ALLOWED_VIDEO_EXTENSIONS)
        return self

    async def validate_for_upload(self) -> None:
        await self.validate_size(MAX_VIDEO_SIZE)
        self.validate_extension(ALLOWED_VIDEO_EXTENSIONS)


class VideoNote(BaseFile):
    """Video note (round video)."""

    duration: int | None = None  # seconds
    length: int | None = None  # diameter in pixels
    thumbhash: str | None = None  # Base64 encoded thumbhash

    @model_validator(mode="after")
    def validate_video_note(self) -> VideoNote:
        self.validate_extension(ALLOWED_VIDEO_NOTE_EXTENSIONS)
        return self

    async def validate_for_upload(self) -> None:
        await self.validate_size(MAX_VIDEO_SIZE)
        self.validate_extension(ALLOWED_VIDEO_NOTE_EXTENSIONS)

    def get_duration(self) -> int | None:
        """Get video duration (requires tinytag)."""
        if self.duration is not None:
            return self.duration
        try:
            from tinytag import TinyTag
            if self.path:
                tag = TinyTag.get(self.path)
                self.duration = int(tag.duration) if tag.duration else None
            elif self.raw:
                # Can't easily get duration from raw bytes without temp file
                pass
        except ImportError:
            pass
        return self.duration


class Voice(BaseFile):
    """Voice message."""

    duration: int | None = None  # seconds
    waveform: bytes | None = None  # Waveform data for visualization

    @model_validator(mode="after")
    def validate_voice(self) -> Voice:
        self.validate_extension(ALLOWED_VOICE_EXTENSIONS)
        return self

    async def validate_for_upload(self) -> None:
        await self.validate_size(MAX_VOICE_SIZE)
        self.validate_extension(ALLOWED_VOICE_EXTENSIONS)

    def get_duration(self) -> int | None:
        """Get voice duration (requires tinytag)."""
        if self.duration is not None:
            return self.duration
        try:
            from tinytag import TinyTag
            if self.path:
                tag = TinyTag.get(self.path)
                self.duration = int(tag.duration) if tag.duration else None
        except ImportError:
            pass
        return self.duration


class Document(BaseFile):
    """Generic document/file."""

    async def validate_for_upload(self) -> None:
        await self.validate_size(MAX_FILE_SIZE)


class UploadResponse(CamelModel):
    """Upload response."""

    token: str
    file_id: str | None = None
    url: str | None = None
    photo: Photo | None = None
    video: Video | None = None
    voice: Voice | None = None
    video_note: VideoNote | None = None
    file: Document | None = None


class DownloadResponse(CamelModel):
    """Download response."""

    url: str
    expires_at: int | None = None


# Upload request models
class PhotoUploadRequest(CamelModel):
    file: Photo
    profile: bool = False


class VideoUploadRequest(CamelModel):
    file: Video


class VoiceUploadRequest(CamelModel):
    file: Voice


class VideoNoteUploadRequest(CamelModel):
    file: VideoNote


class FileUploadRequest(CamelModel):
    file: Document


# Alias for backward compatibility
File = Document