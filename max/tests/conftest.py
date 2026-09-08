"""Pytest configuration and fixtures."""

from __future__ import annotations

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock

from maxpy.config import MaxConfig, TransportConfig, AuthConfig, SessionConfig
from maxpy.enums import TransportType, AuthType


@pytest.fixture
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_config():
    """Create a mock configuration."""
    return MaxConfig(
        transport=TransportConfig(type=TransportType.TCP),
        auth=AuthConfig(type=AuthType.SMS, phone="+79001234567"),
        session=SessionConfig(name="test", persist=False),
    )


@pytest.fixture
def mock_transport():
    """Create a mock transport."""
    transport = AsyncMock()
    transport.connect = AsyncMock()
    transport.send = AsyncMock()
    transport.receive = AsyncMock()
    transport.close = AsyncMock()
    transport.is_connected = True
    transport.transport_type = TransportType.TCP
    return transport


@pytest.fixture
def mock_tcp_transport():
    """Create a mock TCP transport with packet support."""
    from maxpy.transport.tcp import TCPOpcode
    from tests.fixtures import FakeTCPTransport
    return FakeTCPTransport()


@pytest.fixture
def mock_ws_transport():
    """Create a mock WebSocket transport."""
    from tests.fixtures import FakeWSTransport
    return FakeWSTransport()


@pytest.fixture
def test_message():
    """Create a test message."""
    from tests.fixtures import create_test_message
    return create_test_message()


@pytest.fixture
def test_chat():
    """Create a test chat."""
    from tests.fixtures import create_test_chat
    return create_test_chat()


@pytest.fixture
def test_user():
    """Create a test user."""
    from tests.fixtures import create_test_user
    return create_test_user()


@pytest.fixture
def mock_client():
    """Create a mock client."""
    from tests.fixtures import create_mock_client
    return create_mock_client()


# Pytest-asyncio configuration
pytest_plugins = ["pytest_asyncio"]


def pytest_configure(config):
    """Configure pytest."""
    config.addinivalue_line(
        "markers", "unit: Unit tests"
    )
    config.addinivalue_line(
        "markers", "integration: Integration tests (require real API)"
    )
    config.addinivalue_line(
        "markers", "slow: Slow tests"
    )