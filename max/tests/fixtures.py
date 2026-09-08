"""Test fixtures and utilities."""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from dataclasses import dataclass

from maxpy.transport.base import Transport, TransportMetadata
from maxpy.transport.tcp import TCPTransport, TCPPacketHeader, TCPOpcode
from maxpy.transport.websocket import WebSocketTransport, WSFrame
from maxpy.enums import TransportType, ConnectionState, EventType
from maxpy.types import Message, Chat, User, Photo, PhotoAttachment
from maxpy.exceptions import ConnectionError


@dataclass
class FakeTransport(Transport):
    """Fake transport for testing."""

    def __init__(self, config=None):
        super().__init__(config or MagicMock())
        self._sent_data: list[bytes | str] = []
        self._receive_queue: asyncio.Queue = asyncio.Queue()
        self._connected = True

    async def connect(self) -> None:
        self._connected = True
        self._metadata.connected_at = 1234567890.0

    async def send(self, data: bytes | str) -> None:
        self._sent_data.append(data)

    async def receive(self) -> bytes | str | None:
        try:
            return await asyncio.wait_for(self._receive_queue.get(), timeout=0.1)
        except asyncio.TimeoutError:
            return None

    async def close(self) -> None:
        self._connected = False

    def queue_receive(self, data: bytes | str) -> None:
        self._receive_queue.put_nowait(data)

    def get_sent(self) -> list[bytes | str]:
        return self._sent_data.copy()


class FakeTCPTransport(FakeTransport):
    """Fake TCP transport for testing."""

    def __init__(self, config=None):
        super().__init__(config)
        self._sequence = 0

    async def send_packet(self, command: int, payload: dict, opcode: int = TCPOpcode.REQUEST, flags: int = 0, sequence: int | None = None) -> int:
        seq = sequence or self._next_sequence()
        self._sent_data.append({
            "command": command,
            "payload": payload,
            "opcode": opcode,
            "sequence": seq,
        })
        return seq

    def _next_sequence(self) -> int:
        self._sequence = (self._sequence + 1) % 65536
        return self._sequence

    def queue_response(self, sequence: int, payload: dict, opcode: int = TCPOpcode.RESPONSE) -> None:
        header = TCPPacketHeader(version=1, command=0, sequence=sequence, opcode=opcode, flags=0, length=0)
        self._receive_queue.put_nowait((header, payload))


class FakeWSTransport(FakeTransport):
    """Fake WebSocket transport for testing."""

    async def send_frame(self, frame: WSFrame) -> None:
        self._sent_data.append(frame.to_json())

    async def send_request(self, opcode: str, payload: dict, request_id: str | None = None) -> None:
        frame = WSFrame(type=opcode, payload=payload, request_id=request_id)
        await self.send_frame(frame)

    def queue_response(self, request_id: str, payload: dict) -> None:
        frame = WSFrame(type="response", payload=payload, request_id=request_id)
        self._receive_queue.put_nowait(frame)


def create_test_message(
    text: str = "Hello",
    chat_id: str = "test_chat",
    message_id: str = "msg_1",
    sender_id: str = "user_1",
) -> Message:
    """Create a test message."""
    return Message(
        id=message_id,
        chat_id=chat_id,
        sender_id=sender_id,
        text=text,
        created_at=1234567890,
    )


def create_test_chat(
    chat_id: str = "test_chat",
    title: str = "Test Chat",
    type: str = "group",
) -> Chat:
    """Create a test chat."""
    return Chat(
        id=chat_id,
        type=type,
        title=title,
        members_count=2,
    )


def create_test_user(
    user_id: str = "user_1",
    first_name: str = "Test",
    last_name: str = "User",
    phone: str = "+79001234567",
) -> User:
    """Create a test user."""
    return User(
        id=user_id,
        first_name=first_name,
        last_name=last_name,
        phone=phone,
    )


def create_test_photo(path: str = "test.jpg") -> Photo:
    """Create a test photo."""
    return Photo(path=path)


class MockClient:
    """Mock client for testing model methods."""

    def __init__(self):
        self.messages = AsyncMock()
        self.chats = AsyncMock()
        self.users = AsyncMock()


def create_mock_client() -> MockClient:
    """Create a mock client."""
    return MockClient()


def attach_client_to_models(client: MockClient, *models) -> None:
    """Attach mock client to models for convenience methods."""
    for model in models:
        model.set_client(client)