from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from typing import Any
from dataclasses import dataclass, field
from ..enums import TransportType
from ..config import TransportConfig
from ..exceptions import TransportError, ConnectionError


@dataclass
class TransportMetadata:
    """Metadata about the transport connection."""

    transport_type: TransportType
    host: str
    port: int | None = None
    url: str | None = None
    connected_at: float | None = None
    bytes_sent: int = 0
    bytes_received: int = 0
    requests_count: int = 0
    errors_count: int = 0


class Transport(ABC):
    """Abstract transport protocol."""

    def __init__(self, config: TransportConfig):
        self.config = config
        self._metadata = TransportMetadata(
            transport_type=config.type,
            host=config.host,
            port=config.port,
            url=config.ws_url,
        )
        self._connected = False
        self._closing = False
        self._lock = asyncio.Lock()

    @property
    def metadata(self) -> TransportMetadata:
        return self._metadata

    @property
    def is_connected(self) -> bool:
        return self._connected and not self._closing

    @property
    def transport_type(self) -> TransportType:
        return self.config.type

    @abstractmethod
    async def connect(self) -> None:
        """Establish connection."""
        pass

    @abstractmethod
    async def send(self, data: bytes | str) -> None:
        """Send data."""
        pass

    @abstractmethod
    async def receive(self) -> bytes | str | None:
        """Receive data. Returns None on graceful close."""
        pass

    @abstractmethod
    async def close(self) -> None:
        """Close connection."""
        pass

    async def __aenter__(self) -> Transport:
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()

    def _mark_sent(self, size: int) -> None:
        self._metadata.bytes_sent += size
        self._metadata.requests_count += 1

    def _mark_received(self, size: int) -> None:
        self._metadata.bytes_received += size

    def _mark_error(self) -> None:
        self._metadata.errors_count += 1


class TransportFactory:
    """Factory for creating transports."""

    _transports: dict[TransportType, type[Transport]] = {}

    @classmethod
    def register(cls, transport_type: TransportType, transport_class: type[Transport]) -> None:
        cls._transports[transport_type] = transport_class

    @classmethod
    def create(cls, config: TransportConfig) -> Transport:
        transport_class = cls._transports.get(config.type)
        if not transport_class:
            raise ConfigError(f"Unknown transport type: {config.type}")
        return transport_class(config)

    @classmethod
    def get_available(cls) -> list[TransportType]:
        return list(cls._transports.keys())


class ConfigError(Exception):
    """Configuration error for transport factory."""
    pass