from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Literal
from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from .enums import (
    TransportType,
    AuthType,
    DeviceType,
    DEFAULT_TCP_HOST,
    DEFAULT_TCP_PORT,
    DEFAULT_WS_URL,
    DEFAULT_REST_HOST,
    DEFAULT_REST_API_VERSION,
    DEFAULT_RECONNECT_DELAY,
    DEFAULT_RECONNECT_MAX_DELAY,
    DEFAULT_RECONNECT_ATTEMPTS,
    DEFAULT_REQUEST_TIMEOUT,
    DEFAULT_PING_INTERVAL,
    DEFAULT_UPLOAD_TIMEOUT,
    DEFAULT_UPLOAD_CHUNK_SIZE,
    GREEN_API_MEDIA_HOST,
)
from .exceptions import ConfigError


class TransportConfig(BaseSettings):
    """Transport configuration."""

    type: TransportType = TransportType.TCP
    host: str = DEFAULT_TCP_HOST
    port: int = DEFAULT_TCP_PORT
    ws_url: str = DEFAULT_WS_URL
    rest_host: str = DEFAULT_REST_HOST
    rest_api_version: str = DEFAULT_REST_API_VERSION
    rest_media_host: str = GREEN_API_MEDIA_HOST
    use_ssl: bool = True
    proxy: str | None = None
    custom_ca: str | None = None  # Path to custom CA cert

    model_config = SettingsConfigDict(env_prefix="MAXPY_TRANSPORT_")


class AuthConfig(BaseSettings):
    """Authentication configuration."""

    type: AuthType = AuthType.SMS
    phone: str | None = None
    token: str | None = None  # Instance token (REST) or session token (TCP/WS)
    id_instance: int | None = None  # Green-API
    api_token_instance: str | None = None  # Green-API
    email: str | None = None  # For partner API or 2FA email

    model_config = SettingsConfigDict(env_prefix="MAXPY_AUTH_")

    @model_validator(mode="after")
    def validate_auth(self) -> AuthConfig:
        if self.type == AuthType.INSTANCE_TOKEN:
            if not self.id_instance or not self.api_token_instance:
                raise ConfigError(
                    "INSTANCE_TOKEN auth requires id_instance and api_token_instance"
                )
        elif self.type == AuthType.SESSION_TOKEN:
            if not self.token:
                raise ConfigError("SESSION_TOKEN auth requires token")
        elif self.type == AuthType.SMS:
            if not self.phone:
                raise ConfigError("SMS auth requires phone")
        elif self.type == AuthType.QR:
            # QR doesn't require phone upfront
            pass
        return self


class SessionConfig(BaseSettings):
    """Session persistence configuration."""

    name: str = "default"
    persist: bool = True
    path: str = "~/.local/share/maxpy/sessions"
    device_id: str | None = None
    device_type: DeviceType = DeviceType.ANDROID
    app_version: str | None = None
    mt_instance_id: str | None = None

    model_config = SettingsConfigDict(env_prefix="MAXPY_SESSION_")

    @field_validator("path", mode="before")
    @classmethod
    def expand_path(cls, v: str) -> str:
        return str(Path(v).expanduser().resolve())


class ConnectionConfig(BaseSettings):
    """Connection configuration."""

    reconnect: bool = True
    reconnect_delay: float = DEFAULT_RECONNECT_DELAY
    reconnect_max_delay: float = DEFAULT_RECONNECT_MAX_DELAY
    reconnect_attempts: int = DEFAULT_RECONNECT_ATTEMPTS
    request_timeout: float = DEFAULT_REQUEST_TIMEOUT
    ping_interval: float = DEFAULT_PING_INTERVAL
    upload_timeout: float = DEFAULT_UPLOAD_TIMEOUT
    upload_chunk_size: int = DEFAULT_UPLOAD_CHUNK_SIZE
    relogin: bool = True
    password_max_attempts: int | None = 3
    sync_overrides: dict[str, bool] = Field(default_factory=dict)

    model_config = SettingsConfigDict(env_prefix="MAXPY_CONNECTION_")


class LoggingConfig(BaseSettings):
    """Logging configuration."""

    level: str = "INFO"
    format: Literal["pretty", "json"] = "pretty"
    file: str | None = None
    colors: bool = True

    model_config = SettingsConfigDict(env_prefix="MAXPY_LOG_")


class TelemetryConfig(BaseSettings):
    """Telemetry configuration."""

    enabled: bool = True
    endpoint: str | None = None

    model_config = SettingsConfigDict(env_prefix="MAXPY_TELEMETRY_")


class FingerprintConfig(BaseSettings):
    """Device fingerprint configuration."""

    android_version: str | None = None
    android_build: str | None = None
    sdk_version: int | None = None
    locale: str = "en_US"
    timezone: str = "UTC"

    model_config = SettingsConfigDict(env_prefix="MAXPY_FINGERPRINT_")


class MaxConfig(BaseSettings):
    """Main MaxPy configuration."""

    transport: TransportConfig = Field(default_factory=TransportConfig)
    auth: AuthConfig = Field(default_factory=AuthConfig)
    session: SessionConfig = Field(default_factory=SessionConfig)
    connection: ConnectionConfig = Field(default_factory=ConnectionConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    telemetry: TelemetryConfig = Field(default_factory=TelemetryConfig)
    fingerprint: FingerprintConfig = Field(default_factory=FingerprintConfig)

    # Extra config for backward compatibility / advanced use
    extra: dict[str, Any] = Field(default_factory=dict)

    model_config = SettingsConfigDict(
        env_file=(".env", "maxpy.env", "config.env"),
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        extra="ignore",
    )

    @classmethod
    def from_file(cls, path: str | Path) -> MaxConfig:
        """Load config from TOML file."""
        import tomllib
        path = Path(path).expanduser().resolve()
        if not path.exists():
            raise ConfigError(f"Config file not found: {path}")
        with open(path, "rb") as f:
            data = tomllib.load(f)
        return cls(**data)

    @classmethod
    def from_env(cls) -> MaxConfig:
        """Load config from environment variables only."""
        return cls(_env_file=None)

    def to_dict(self) -> dict[str, Any]:
        """Export config as dictionary (without sensitive data)."""
        data = self.model_dump()
        # Mask sensitive fields
        if "auth" in data:
            auth = data["auth"]
            if auth.get("api_token_instance"):
                auth["api_token_instance"] = "***"
            if auth.get("token"):
                auth["token"] = "***"
        return data


# Convenience function for quick config
def create_config(
    transport: TransportType | str = TransportType.TCP,
    phone: str | None = None,
    token: str | None = None,
    id_instance: int | None = None,
    api_token_instance: str | None = None,
    session_name: str = "default",
    persist_session: bool = True,
    **kwargs,
) -> MaxConfig:
    """Create config with common parameters."""
    auth_type: AuthType
    if transport == TransportType.REST or (id_instance and api_token_instance):
        auth_type = AuthType.INSTANCE_TOKEN
    elif token:
        auth_type = AuthType.SESSION_TOKEN
    elif phone:
        auth_type = AuthType.SMS
    else:
        auth_type = AuthType.QR

    return MaxConfig(
        transport=TransportConfig(type=transport),
        auth=AuthConfig(
            type=auth_type,
            phone=phone,
            token=token,
            id_instance=id_instance,
            api_token_instance=api_token_instance,
        ),
        session=SessionConfig(name=session_name, persist=persist_session),
        **kwargs,
    )