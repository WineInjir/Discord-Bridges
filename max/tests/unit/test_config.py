"""Unit tests for configuration."""

from __future__ import annotations

import pytest
from pathlib import Path

from maxpy.config import (
    MaxConfig,
    TransportConfig,
    AuthConfig,
    SessionConfig,
    ConnectionConfig,
    create_config,
)
from maxpy.enums import TransportType, AuthType, DeviceType
from maxpy.exceptions import ConfigError


class TestTransportConfig:
    """Tests for TransportConfig."""

    def test_default_values(self):
        config = TransportConfig()
        assert config.type == TransportType.TCP
        assert config.host == "api2.oneme.ru"
        assert config.port == 443
        assert config.use_ssl is True

    def test_custom_values(self):
        config = TransportConfig(
            type=TransportType.REST,
            host="custom.host",
            port=8080,
            proxy="socks5://proxy:1080",
        )
        assert config.type == TransportType.REST
        assert config.host == "custom.host"
        assert config.port == 8080
        assert config.proxy == "socks5://proxy:1080"


class TestAuthConfig:
    """Tests for AuthConfig."""

    def test_instance_token_auth(self):
        config = AuthConfig(
            type=AuthType.INSTANCE_TOKEN,
            id_instance=12345,
            api_token_instance="token123",
        )
        assert config.type == AuthType.INSTANCE_TOKEN
        assert config.id_instance == 12345

    def test_instance_token_missing_fields(self):
        with pytest.raises(ConfigError):
            AuthConfig(type=AuthType.INSTANCE_TOKEN)

    def test_sms_auth(self):
        config = AuthConfig(
            type=AuthType.SMS,
            phone="+79001234567",
        )
        assert config.type == AuthType.SMS
        assert config.phone == "+79001234567"

    def test_sms_auth_missing_phone(self):
        with pytest.raises(ConfigError):
            AuthConfig(type=AuthType.SMS)

    def test_session_token_auth(self):
        config = AuthConfig(
            type=AuthType.SESSION_TOKEN,
            token="session_token_123",
        )
        assert config.type == AuthType.SESSION_TOKEN
        assert config.token == "session_token_123"

    def test_session_token_missing_token(self):
        with pytest.raises(ConfigError):
            AuthConfig(type=AuthType.SESSION_TOKEN)

    def test_qr_auth(self):
        config = AuthConfig(type=AuthType.QR)
        assert config.type == AuthType.QR


class TestSessionConfig:
    """Tests for SessionConfig."""

    def test_default_values(self):
        config = SessionConfig()
        assert config.name == "default"
        assert config.persist is True
        assert config.device_type == DeviceType.ANDROID

    def test_path_expansion(self):
        config = SessionConfig(path="~/test/sessions")
        assert str(Path.home() / "test" / "sessions") in config.path


class TestConnectionConfig:
    """Tests for ConnectionConfig."""

    def test_default_values(self):
        config = ConnectionConfig()
        assert config.reconnect is True
        assert config.reconnect_delay == 1.0
        assert config.request_timeout == 30.0


class TestMaxConfig:
    """Tests for MaxConfig."""

    def test_create_from_components(self):
        config = create_config(
            transport=TransportType.TCP,
            phone="+79001234567",
            session_name="test",
        )
        assert config.transport.type == TransportType.TCP
        assert config.auth.type == AuthType.SMS
        assert config.auth.phone == "+79001234567"
        assert config.session.name == "test"

    def test_create_with_instance_token(self):
        config = create_config(
            transport=TransportType.REST,
            id_instance=12345,
            api_token_instance="token123",
        )
        assert config.transport.type == TransportType.REST
        assert config.auth.type == AuthType.INSTANCE_TOKEN
        assert config.auth.id_instance == 12345

    def test_create_with_session_token(self):
        config = create_config(
            transport=TransportType.TCP,
            token="session_123",
        )
        assert config.auth.type == AuthType.SESSION_TOKEN
        assert config.auth.token == "session_123"

    def test_to_dict_masks_secrets(self):
        config = MaxConfig(
            auth=AuthConfig(
                type=AuthType.INSTANCE_TOKEN,
                id_instance=12345,
                api_token_instance="secret_token",
            ),
        )
        data = config.to_dict()
        assert data["auth"]["api_token_instance"] == "***"

    def test_to_dict_masks_session_token(self):
        config = MaxConfig(
            auth=AuthConfig(
                type=AuthType.SESSION_TOKEN,
                token="secret_session",
            ),
        )
        data = config.to_dict()
        assert data["auth"]["token"] == "***"