from __future__ import annotations

import asyncio
import json
import time
from typing import Any
from urllib.parse import urljoin

import aiohttp
from aiohttp import ClientTimeout, TCPConnector

from .base import Transport, TransportFactory
from ..config import TransportConfig
from ..enums import TransportType
from ..exceptions import (
    TransportError,
    ConnectionError,
    RateLimitError,
    NotFoundError,
    ForbiddenError,
    ValidationError,
    ServerError,
    APIError,
    wrap_error,
)
from ..types.common import JSONDict


class RESTTransport(Transport):
    """REST transport for Green-API."""

    def __init__(self, config: TransportConfig):
        super().__init__(config)
        self._session: aiohttp.ClientSession | None = None
        self._id_instance: int | None = None
        self._api_token: str | None = None
        self._base_url: str = ""
        self._media_url: str = ""

    async def connect(self) -> None:
        """Initialize HTTP session."""
        if self._session and not self._session.closed:
            return

        # Build base URLs
        self._base_url = f"{self.config.rest_host}/{self.config.rest_api_version}"
        self._media_url = self.config.rest_media_host

        # Extract auth from config
        from ..config import AuthConfig
        # We'll get auth from the client

        # Create session with connection pooling
        connector = TCPConnector(
            limit=100,
            limit_per_host=30,
            ttl_dns_cache=300,
            enable_cleanup_closed=True,
        )
        timeout = ClientTimeout(
            total=self.config.request_timeout,
            connect=10,
            sock_read=self.config.request_timeout,
        )

        self._session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            headers={
                "User-Agent": "MaxPy/0.1.0",
                "Accept": "application/json",
            },
        )
        self._connected = True
        self._metadata.connected_at = time.time()

    def set_credentials(self, id_instance: int, api_token: str) -> None:
        """Set Green-API credentials."""
        self._id_instance = id_instance
        self._api_token = api_token

    def _build_url(self, endpoint: str, is_media: bool = False) -> str:
        """Build full URL for endpoint."""
        base = self._media_url if is_media else self._base_url
        # Replace placeholders
        endpoint = endpoint.replace("{{idInstance}}", str(self._id_instance))
        endpoint = endpoint.replace("{{token}}", self._api_token or "")
        return urljoin(base + "/", endpoint.lstrip("/"))

    async def send(self, data: bytes | str) -> None:
        """Not used for REST - use request() instead."""
        raise NotImplementedError("Use request() method for REST transport")

    async def receive(self) -> bytes | str | None:
        """Not used for REST - use request() instead."""
        raise NotImplementedError("Use request() method for REST transport")

    async def request(
        self,
        method: str,
        endpoint: str,
        *,
        json_data: JSONDict | None = None,
        form_data: aiohttp.FormData | None = None,
        files: dict[str, tuple[str, bytes, str]] | None = None,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        is_media: bool = False,
        timeout: float | None = None,
    ) -> JSONDict:
        """Make HTTP request."""
        if not self._connected or not self._session:
            raise ConnectionError("Transport not connected")

        url = self._build_url(endpoint, is_media)

        # Prepare request
        request_headers = {"Content-Type": "application/json"}
        if headers:
            request_headers.update(headers)

        # Handle multipart/form-data
        if files or form_data:
            request_headers.pop("Content-Type", None)  # Let aiohttp set boundary
            form = form_data or aiohttp.FormData()
            if files:
                for field_name, (filename, content, content_type) in files.items():
                    form.add_field(field_name, content, filename=filename, content_type=content_type)
        else:
            form = None

        request_timeout = ClientTimeout(total=timeout or self.config.request_timeout)

        try:
            async with self._session.request(
                method=method.upper(),
                url=url,
                json=json_data if not form else None,
                data=form,
                params=params,
                headers=request_headers,
                timeout=request_timeout,
            ) as response:
                self._mark_sent(len(str(json_data)) if json_data else 0)
                self._mark_received(response.content_length or 0)

                # Parse response
                content_type = response.headers.get("Content-Type", "")
                if "application/json" in content_type:
                    result = await response.json()
                else:
                    text = await response.text()
                    try:
                        result = json.loads(text)
                    except json.JSONDecodeError:
                        result = {"text": text}

                # Handle errors
                if response.status >= 400:
                    self._mark_error()
                    await self._handle_error(response.status, result, url, method)

                return result

        except asyncio.TimeoutError as e:
            self._mark_error()
            raise ConnectionError(f"Request timeout: {url}", endpoint=url, transport="rest", original_error=e)
        except aiohttp.ClientError as e:
            self._mark_error()
            raise TransportError(f"Client error: {e}", endpoint=url, transport="rest", original_error=e)

    async def _handle_error(
        self,
        status: int,
        data: JSONDict,
        url: str,
        method: str,
    ) -> None:
        """Handle HTTP error responses."""
        error_msg = data.get("message") or data.get("error") or f"HTTP {status}"
        error_code = data.get("code") or data.get("errorCode")

        if status == 429:
            retry_after = data.get("retryAfter") or data.get("retry_after")
            raise RateLimitError(
                error_msg,
                retry_after=float(retry_after) if retry_after else None,
                status_code=status,
                response_data=data,
                endpoint=url,
                transport="rest",
            )
        elif status == 404:
            raise NotFoundError(
                error_msg,
                status_code=status,
                response_data=data,
                endpoint=url,
                transport="rest",
            )
        elif status == 403:
            raise ForbiddenError(
                error_msg,
                status_code=status,
                response_data=data,
                endpoint=url,
                transport="rest",
            )
        elif status == 400:
            raise ValidationError(
                error_msg,
                status_code=status,
                response_data=data,
                endpoint=url,
                transport="rest",
            )
        elif status >= 500:
            raise ServerError(
                error_msg,
                status_code=status,
                response_data=data,
                endpoint=url,
                transport="rest",
            )
        else:
            raise APIError(
                error_msg,
                code=error_code,
                status_code=status,
                response_data=data,
                endpoint=url,
                transport="rest",
            )

    async def close(self) -> None:
        """Close HTTP session."""
        self._closing = True
        if self._session and not self._session.closed:
            await self._session.close()
        self._connected = False
        self._session = None


# Register transport
TransportFactory.register(TransportType.REST, RESTTransport)