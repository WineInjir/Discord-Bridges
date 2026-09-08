from __future__ import annotations

import asyncio
import time
import uuid
from typing import Any, Optional
from dataclasses import dataclass, field
from collections import defaultdict

from ..transport.base import Transport
from ..transport.tcp import TCPTransport, TCPPacketHeader, TCPOpcode
from ..transport.websocket import WebSocketTransport, WSFrame
from ..enums import ConnectionState, EventType
from ..types.event import Event, RawEvent, DisconnectEvent
from ..exceptions import ConnectionError, TransportError, ReconnectFailedError, PingTimeoutError
from .state import ConnectionState as ConnectionStateEnum


@dataclass
class PendingRequest:
    """Pending request waiting for response."""

    future: asyncio.Future
    sequence: int
    command: int
    created_at: float = field(default_factory=time.time)
    timeout: float = 30.0


class PendingRequests:
    """Manages pending request/response correlation."""

    def __init__(self, default_timeout: float = 30.0):
        self._requests: dict[int, PendingRequest] = {}
        self._default_timeout = default_timeout
        self._lock = asyncio.Lock()

    async def add(self, sequence: int, command: int, timeout: float | None = None) -> asyncio.Future:
        """Add a pending request and return its future."""
        future = asyncio.get_event_loop().create_future()
        pending = PendingRequest(
            future=future,
            sequence=sequence,
            command=command,
            timeout=timeout or self._default_timeout,
        )
        async with self._lock:
            self._requests[sequence] = pending
        return future

    async def resolve(self, sequence: int, result: Any) -> bool:
        """Resolve a pending request."""
        async with self._lock:
            pending = self._requests.pop(sequence, None)
        if pending and not pending.future.done():
            pending.future.set_result(result)
            return True
        return False

    async def reject(self, sequence: int, error: Exception) -> bool:
        """Reject a pending request."""
        async with self._lock:
            pending = self._requests.pop(sequence, None)
        if pending and not pending.future.done():
            pending.future.set_exception(error)
            return True
        return False

    async def cleanup_expired(self) -> list[PendingRequest]:
        """Remove and return expired requests."""
        now = time.time()
        expired = []
        async with self._lock:
            to_remove = [
                seq for seq, req in self._requests.items()
                if now - req.created_at > req.timeout
            ]
            for seq in to_remove:
                expired.append(self._requests.pop(seq))
        return expired

    async def cancel_all(self, error: Exception) -> None:
        """Cancel all pending requests."""
        async with self._lock:
            for pending in self._requests.values():
                if not pending.future.done():
                    pending.future.set_exception(error)
            self._requests.clear()

    def __len__(self) -> int:
        return len(self._requests)


class ConnectionManager:
    """Manages transport connection, reconnection, and request/response."""

    def __init__(
        self,
        transport: Transport,
        reconnect: bool = True,
        reconnect_delay: float = 1.0,
        reconnect_max_delay: float = 60.0,
        reconnect_attempts: int = 10,
        ping_interval: float = 30.0,
        request_timeout: float = 30.0,
    ):
        self.transport = transport
        self.reconnect = reconnect
        self.reconnect_delay = reconnect_delay
        self.reconnect_max_delay = reconnect_max_delay
        self.reconnect_attempts = reconnect_attempts
        self.ping_interval = ping_interval
        self.request_timeout = request_timeout

        self._state = ConnectionStateEnum.DISCONNECTED
        self._pending = PendingRequests(request_timeout)
        self._recv_task: asyncio.Task | None = None
        self._ping_task: asyncio.Task | None = None
        self._reconnect_task: asyncio.Task | None = None
        self._event_queue: asyncio.Queue[Event] = asyncio.Queue()
        self._running = False
        self._connection_lost = False
        self._last_ping_time: float | None = None
        self._lock = asyncio.Lock()

        # Callbacks
        self._on_event: callable | None = None
        self._on_state_change: callable | None = None
        self._on_disconnect: callable | None = None

    @property
    def state(self) -> ConnectionStateEnum:
        return self._state

    @property
    def is_connected(self) -> bool:
        return self._state == ConnectionStateEnum.CONNECTED

    @property
    def transport_type(self) -> str:
        return self.transport.transport_type.value

    def set_event_handler(self, handler: callable) -> None:
        self._on_event = handler

    def set_state_change_handler(self, handler: callable) -> None:
        self._on_state_change = handler

    def set_disconnect_handler(self, handler: callable) -> None:
        self._on_disconnect = handler

    def _set_state(self, state: ConnectionStateEnum) -> None:
        if self._state != state:
            old_state = self._state
            self._state = state
            if self._on_state_change:
                try:
                    # Handle both sync and async callbacks
                    result = self._on_state_change(old_state, state)
                    if asyncio.iscoroutine(result):
                        # Schedule the coroutine
                        asyncio.create_task(result)
                except Exception:
                    pass

    async def connect(self) -> None:
        """Connect transport."""
        async with self._lock:
            if self._state in (ConnectionStateEnum.CONNECTING, ConnectionStateEnum.CONNECTED):
                return

            self._set_state(ConnectionStateEnum.CONNECTING)

        try:
            await self.transport.connect()
            self._connection_lost = False
        except Exception as e:
            self._set_state(ConnectionStateEnum.DISCONNECTED)
            raise

    async def start(self) -> None:
        """Start connection manager (receive loop + ping)."""
        self._running = True
        self._recv_task = asyncio.create_task(self._recv_loop())
        self._ping_task = asyncio.create_task(self._ping_loop())

    async def stop(self) -> None:
        """Stop connection manager."""
        self._running = False

        if self._recv_task:
            self._recv_task.cancel()
            try:
                await self._recv_task
            except asyncio.CancelledError:
                pass

        if self._ping_task:
            self._ping_task.cancel()
            try:
                await self._ping_task
            except asyncio.CancelledError:
                pass

        if self._reconnect_task:
            self._reconnect_task.cancel()
            try:
                await self._reconnect_task
            except asyncio.CancelledError:
                pass

        await self._pending.cancel_all(ConnectionError("Connection closed"))
        await self.transport.close()
        self._set_state(ConnectionStateEnum.DISCONNECTED)

    async def send_request(
        self,
        command: int,
        payload: dict[str, Any],
        opcode: int = TCPOpcode.REQUEST,
        timeout: float | None = None,
    ) -> Any:
        """Send request and wait for response."""
        if not self.is_connected:
            raise ConnectionError("Not connected")

        # Get sequence from transport
        if isinstance(self.transport, TCPTransport):
            sequence = await self.transport.send_packet(command, payload, opcode)
        else:
            # For WebSocket/REST, we'd need different approach
            # For now, generate UUID
            sequence = int(uuid.uuid4().int & 0xFFFFFFFF)
            # This would need transport-specific implementation
            raise NotImplementedError("Non-TCP transports need custom implementation")

        future = await self._pending.add(sequence, command, timeout or self.request_timeout)

        try:
            return await asyncio.wait_for(future, timeout=timeout or self.request_timeout)
        except asyncio.TimeoutError:
            await self._pending.reject(sequence, ConnectionError("Request timeout"))
            raise

    async def _recv_loop(self) -> None:
        """Background receive loop."""
        while self._running:
            try:
                if isinstance(self.transport, TCPTransport):
                    result = await self.transport.receive()
                    if result is None:
                        break
                    header, payload = result
                    await self._handle_tcp_packet(header, payload)

                elif isinstance(self.transport, WebSocketTransport):
                    frame = await self.transport.receive()
                    if frame is None:
                        break
                    await self._handle_ws_frame(frame)

                else:
                    # REST doesn't have a receive loop
                    break

            except asyncio.CancelledError:
                break
            except ConnectionError:
                break
            except Exception as e:
                if self._running:
                    await self._handle_error(e)

        # Connection lost
        if self._running:
            self._connection_lost = True
            await self._handle_disconnect()

    async def _handle_tcp_packet(self, header: TCPPacketHeader, payload: dict[str, Any]) -> None:
        """Handle incoming TCP packet."""
        # Check if it's a response to a pending request
        if header.opcode in (TCPOpcode.RESPONSE, TCPOpcode.ERROR):
            resolved = await self._pending.resolve(header.sequence, (header, payload))
            if not resolved:
                # No pending request, might be an event
                await self._emit_event(header, payload)
            return

        # It's an event or push notification
        await self._emit_event(header, payload)

    async def _handle_ws_frame(self, frame: WSFrame) -> None:
        """Handle incoming WebSocket frame."""
        # Check if it's a response to a pending request
        if frame.request_id:
            try:
                seq = int(frame.request_id)
                resolved = await self._pending.resolve(seq, frame)
                if resolved:
                    return
            except ValueError:
                pass

        # It's an event
        await self._emit_ws_event(frame)

    async def _emit_event(self, header: TCPPacketHeader, payload: dict[str, Any]) -> None:
        """Emit TCP event."""
        # Convert to unified event
        event = self._tcp_to_event(header, payload)
        if event:
            await self._event_queue.put(event)
            if self._on_event:
                try:
                    await self._on_event(event)
                except Exception:
                    pass

    async def _emit_ws_event(self, frame: WSFrame) -> None:
        """Emit WebSocket event."""
        event = self._ws_to_event(frame)
        if event:
            await self._event_queue.put(event)
            if self._on_event:
                try:
                    await self._on_event(event)
                except Exception:
                    pass

    def _tcp_to_event(self, header: TCPPacketHeader, payload: dict[str, Any]) -> Event | None:
        """Convert TCP packet to unified event."""
        # Map command to event type
        from ..transport.tcp import TCPCommand

        event_map = {
            TCPCommand.MSG_SEND: EventType.MESSAGE_NEW,
            TCPCommand.MSG_EDIT: EventType.MESSAGE_EDIT,
            TCPCommand.MSG_DELETE: EventType.MESSAGE_DELETE,
            TCPCommand.CHAT_MARK: EventType.MESSAGE_READ,
            TCPCommand.CHAT_UPDATE: EventType.CHAT_UPDATE,
            TCPCommand.CHAT_MEMBERS_UPDATE: EventType.CHAT_UPDATE,
            TCPCommand.CONTACT_UPDATE: EventType.USER_UPDATE,
            TCPCommand.SESSIONS_INFO: EventType.USER_UPDATE,
            TCPCommand.PROFILE: EventType.USER_UPDATE,
            TCPCommand.FOLDERS_UPDATE: EventType.CHAT_UPDATE,
            TCPCommand.CONFIG: EventType.USER_UPDATE,
            # Upload ready events
            # These would come from specific opcodes
        }

        event_type = event_map.get(header.command)
        if event_type:
            from ..types.event import map_event_type
            event_class = map_event_type(event_type)
            try:
                return event_class(type=event_type, timestamp=int(time.time() * 1000), **payload)
            except Exception:
                pass

        # Raw event fallback
        return RawEvent(
            type=EventType.RAW,
            timestamp=int(time.time() * 1000),
            opcode=header.opcode,
            payload=payload,
        )

    def _ws_to_event(self, frame: WSFrame) -> Event | None:
        """Convert WebSocket frame to unified event."""
        event_map = {
            "msg_send": EventType.MESSAGE_NEW,
            "msg_edit": EventType.MESSAGE_EDIT,
            "msg_delete": EventType.MESSAGE_DELETE,
            "chat_mark": EventType.MESSAGE_READ,
            "chat_update": EventType.CHAT_UPDATE,
            "chat_members_update": EventType.CHAT_UPDATE,
            "contact_update": EventType.USER_UPDATE,
            "sessions_info": EventType.USER_UPDATE,
            "profile": EventType.USER_UPDATE,
            "folders_update": EventType.CHAT_UPDATE,
            "config": EventType.USER_UPDATE,
        }

        event_type = event_map.get(frame.type)
        if event_type:
            from ..types.event import map_event_type
            event_class = map_event_type(event_type)
            try:
                return event_class(type=event_type, timestamp=int(time.time() * 1000), **frame.payload)
            except Exception:
                pass

        return RawEvent(
            type=EventType.RAW,
            timestamp=int(time.time() * 1000),
            opcode=0,
            payload=frame.payload,
        )

    async def _ping_loop(self) -> None:
        """Send periodic pings."""
        while self._running:
            try:
                await asyncio.sleep(self.ping_interval)

                if not self.is_connected:
                    continue

                self._last_ping_time = time.time()

                if isinstance(self.transport, TCPTransport):
                    await self.transport.send_packet(
                        command=0,  # Ping command
                        payload={},
                        opcode=TCPOpcode.PING,
                    )
                elif isinstance(self.transport, WebSocketTransport):
                    await self.transport.send_request("ping", {})

            except asyncio.CancelledError:
                break
            except Exception:
                # Ping failed, connection might be dead
                self._connection_lost = True
                break

    async def _handle_disconnect(self) -> None:
        """Handle connection loss."""
        self._set_state(ConnectionStateEnum.DISCONNECTED)

        if self._on_disconnect:
            try:
                await self._on_disconnect(self._connection_lost)
            except Exception:
                pass

        # Emit disconnect event
        event = DisconnectEvent(
            type=EventType.DISCONNECT,
            timestamp=int(time.time() * 1000),
            reason="Connection lost",
            will_reconnect=self.reconnect,
        )
        await self._event_queue.put(event)

        # Attempt reconnect
        if self.reconnect:
            await self._schedule_reconnect()

    async def _schedule_reconnect(self) -> None:
        """Schedule reconnection with exponential backoff."""
        delay = self.reconnect_delay

        for attempt in range(1, self.reconnect_attempts + 1):
            if not self._running:
                break

            self._set_state(ConnectionStateEnum.RECONNECTING)

            try:
                await asyncio.sleep(delay)
                await self.connect()
                await self._authenticate()
                self._set_state(ConnectionStateEnum.CONNECTED)
                self._connection_lost = False
                return  # Success
            except Exception as e:
                if attempt == self.reconnect_attempts:
                    raise ReconnectFailedError(
                        f"Reconnect failed after {attempt} attempts",
                        attempts=attempt,
                        last_error=e,
                    )
                delay = min(delay * 2, self.reconnect_max_delay)

    async def _authenticate(self) -> None:
        """Re-authenticate after reconnect."""
        # This would need access to auth flow
        # For now, just set state to authenticating
        self._set_state(ConnectionStateEnum.AUTHENTICATING)
        # Actual auth would be triggered by client

    async def _handle_error(self, error: Exception) -> None:
        """Handle receive loop error."""
        if self._on_event:
            try:
                from ..types.event import ErrorEvent
                event = ErrorEvent(
                    type=EventType.ERROR,
                    timestamp=int(time.time() * 1000),
                    error=str(error),
                    error_type=type(error).__name__,
                )
                await self._event_queue.put(event)
                await self._on_event(event)
            except Exception:
                pass

    async def get_event(self) -> Event | None:
        """Get next event from queue."""
        try:
            return await asyncio.wait_for(self._event_queue.get(), timeout=0.1)
        except asyncio.TimeoutError:
            return None

    def get_stats(self) -> dict[str, Any]:
        """Get connection statistics."""
        return {
            "state": self._state.value,
            "transport": self.transport_type,
            "pending_requests": len(self._pending),
            "transport_metadata": {
                "bytes_sent": self.transport.metadata.bytes_sent,
                "bytes_received": self.transport.metadata.bytes_received,
                "requests_count": self.transport.metadata.requests_count,
                "errors_count": self.transport.metadata.errors_count,
            },
        }