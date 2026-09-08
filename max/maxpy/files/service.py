from __future__ import annotations

import asyncio
import aiohttp
import hashlib
import os
from pathlib import Path
from typing import AsyncGenerator
from dataclasses import dataclass

from ..types.file import BaseFile, Photo, Video, Voice, VideoNote, Document, UploadResponse
from ..enums import UploadType, DEFAULT_UPLOAD_CHUNK_SIZE
from ..exceptions import UploadError, FileValidationError


@dataclass
class UploadWaiter:
    """Waits for upload processing completion."""

    event_type: str
    timeout: float = 60.0


class FileService:
    """File upload/download service."""

    def __init__(self, client: "MaxClient"):
        self.client = client
        self._upload_waiters: dict[str, asyncio.Future] = {}

    async def upload(
        self,
        file: BaseFile,
        upload_type: UploadType,
        profile: bool = False,
    ) -> UploadResponse:
        """Upload file to MAX."""
        # Validate file
        if isinstance(file, Photo):
            await file.validate_for_upload()
        elif isinstance(file, Video):
            await file.validate_for_upload()
        elif isinstance(file, Voice):
            await file.validate_for_upload()
        elif isinstance(file, VideoNote):
            await file.validate_for_upload()
            # Get duration if not set
            if file.duration is None:
                file.get_duration()
        elif isinstance(file, Document):
            await file.validate_for_upload()

        # Get upload URL
        if isinstance(self.client.connection.transport, TCPTransport):
            return await self._upload_tcp(file, upload_type, profile)
        elif isinstance(self.client.connection.transport, WebSocketTransport):
            return await self._upload_ws(file, upload_type, profile)
        else:
            return await self._upload_rest(file, upload_type, profile)

    async def _upload_tcp(
        self,
        file: BaseFile,
        upload_type: UploadType,
        profile: bool = False,
    ) -> UploadResponse:
        """Upload via TCP transport."""
        from ..transport.tcp import TCPCommand

        # Map upload type to command
        command_map = {
            UploadType.PHOTO: TCPCommand.PHOTO_UPLOAD,
            UploadType.VIDEO: TCPCommand.VIDEO_UPLOAD,
            UploadType.VOICE: TCPCommand.VIDEO_UPLOAD,  # Same as video
            UploadType.VIDEO_NOTE: TCPCommand.VIDEO_UPLOAD,
            UploadType.FILE: TCPCommand.FILE_UPLOAD,
            UploadType.PROFILE_PHOTO: TCPCommand.PHOTO_UPLOAD,
            UploadType.GROUP_PHOTO: TCPCommand.PHOTO_UPLOAD,
        }

        command = command_map.get(upload_type)
        if not command:
            raise UploadError(f"Unsupported upload type: {upload_type}")

        # Request upload URL
        seq = await self.client.connection.send_request(
            command=command,
            payload={"profile": profile} if profile else {},
        )

        header, payload = seq
        if header.opcode == TCPOpcode.ERROR:
            raise UploadError(payload.get("error", "Failed to get upload URL"))

        upload_url = payload.get("url") or payload.get("uploadUrl")
        file_token = payload.get("token") or payload.get("fileToken")

        if not upload_url:
            raise UploadError("No upload URL received")

        # Upload file via HTTP
        await self._http_upload(upload_url, file)

        # Wait for processing if needed
        if upload_type in (UploadType.VIDEO, UploadType.VIDEO_NOTE, UploadType.VOICE, UploadType.FILE):
            await self._wait_for_processing(upload_type, file_token)

        return UploadResponse(
            token=file_token,
            file_id=payload.get("fileId"),
            url=payload.get("url"),
        )

    async def _upload_ws(
        self,
        file: BaseFile,
        upload_type: UploadType,
        profile: bool = False,
    ) -> UploadResponse:
        """Upload via WebSocket transport."""
        from ..transport.websocket import WSOpcode

        opcode_map = {
            UploadType.PHOTO: WSOpcode.PHOTO_UPLOAD_URL,
            UploadType.VIDEO: WSOpcode.VIDEO_UPLOAD_URL,
            UploadType.VOICE: WSOpcode.VIDEO_UPLOAD_URL,
            UploadType.VIDEO_NOTE: WSOpcode.VIDEO_UPLOAD_URL,
            UploadType.FILE: WSOpcode.FILE_UPLOAD_URL,
        }

        opcode = opcode_map.get(upload_type)
        if not opcode:
            raise UploadError(f"Unsupported upload type: {upload_type}")

        # Request upload URL
        request_id = str(id(file))
        await self.client.connection.transport.send_request(opcode, {"profile": profile}, request_id)

        # Wait for response
        # This would need a proper response handling mechanism
        # For now, simplified
        raise NotImplementedError("WebSocket upload not fully implemented")

    async def _upload_rest(
        self,
        file: BaseFile,
        upload_type: UploadType,
        profile: bool = False,
    ) -> UploadResponse:
        """Upload via REST (Green-API)."""
        # Green-API uses multipart upload
        if upload_type == UploadType.PHOTO:
            endpoint = "waInstance{{idInstance}}/sendFileByUpload/{{token}}"
        else:
            endpoint = "media/waInstance{{idInstance}}/sendFileByUpload/{{token}}"

        # This would use the REST transport
        raise NotImplementedError("REST upload not fully implemented")

    async def _http_upload(self, url: str, file: BaseFile) -> None:
        """Upload file via HTTP PUT/POST with chunking."""
        chunk_size = self.client.config.connection.upload_chunk_size
        file_size = file.get_size()

        headers = {
            "Content-Type": file.mime_type or "application/octet-stream",
        }

        async with aiohttp.ClientSession() as session:
            offset = 0
            async for chunk in file.iter_chunks(chunk_size):
                chunk_headers = headers.copy()
                chunk_headers["Content-Range"] = f"bytes {offset}-{offset + len(chunk) - 1}/{file_size}"
                chunk_headers["Content-Length"] = str(len(chunk))

                async with session.put(url, data=chunk, headers=chunk_headers) as resp:
                    if resp.status >= 400:
                        text = await resp.text()
                        raise UploadError(f"Upload failed: {resp.status} - {text}")

                offset += len(chunk)

    async def _wait_for_processing(self, upload_type: UploadType, token: str) -> None:
        """Wait for file processing to complete."""
        event_map = {
            UploadType.VIDEO: "video_ready",
            UploadType.VIDEO_NOTE: "video_ready",
            UploadType.VOICE: "voice_ready",
            UploadType.FILE: "file_ready",
        }

        event_name = event_map.get(upload_type)
        if not event_name:
            return

        future = asyncio.get_event_loop().create_future()
        self._upload_waiters[token] = future

        try:
            await asyncio.wait_for(future, timeout=60.0)
        except asyncio.TimeoutError:
            raise UploadError(f"Timeout waiting for {event_name}")
        finally:
            self._upload_waiters.pop(token, None)

    def notify_processing_complete(self, token: str) -> None:
        """Notify that processing is complete."""
        future = self._upload_waiters.get(token)
        if future and not future.done():
            future.set_result(True)