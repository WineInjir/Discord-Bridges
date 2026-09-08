from __future__ import annotations

import asyncio
import inspect
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Awaitable, TypeVar
from collections import defaultdict

from ..enums import EventType, ErrorScope
from ..types.event import Event, BaseEvent
from ..exceptions import DispatchError, HandlerError, FilterError


T = TypeVar("T", bound=BaseEvent)
EventHandler = Callable[[T, Any], Awaitable[None]]
EventFilter = Callable[[T], bool | Awaitable[bool]]


@dataclass
class HandlerEntry:
    """Registered event handler."""

    event_type: EventType
    handler: EventHandler
    filters: list[EventFilter] = field(default_factory=list)
    router: "Router | None" = None


class Router:
    """Event router with hierarchical structure and filters."""

    def __init__(self, name: str | None = None):
        self.name = name or f"router_{id(self)}"
        self._handlers: dict[EventType, list[HandlerEntry]] = defaultdict(list)
        self._start_handlers: list[EventHandler] = []
        self._error_handlers: dict[ErrorScope, list[EventHandler]] = defaultdict(list)
        self._disconnect_handlers: list[EventHandler] = []
        self._child_routers: list[Router] = []
        self._parent: Router | None = None

    def include_router(self, router: "Router") -> None:
        """Include a child router."""
        router._parent = self
        self._child_routers.append(router)

    def _register_handler(
        self,
        event_type: EventType,
        handler: EventHandler,
        filters: list[EventFilter] = None,
    ) -> HandlerEntry:
        entry = HandlerEntry(
            event_type=event_type,
            handler=handler,
            filters=filters or [],
            router=self,
        )
        self._handlers[event_type].append(entry)
        return entry

    def on(
        self,
        event_type: EventType,
        *filters: EventFilter,
    ) -> Callable[[EventHandler], EventHandler]:
        """Register handler for event type with optional filters."""

        def decorator(handler: EventHandler) -> EventHandler:
            self._register_handler(event_type, handler, list(filters))
            return handler

        return decorator

    def on_start(self) -> Callable[[EventHandler], EventHandler]:
        """Register startup handler."""

        def decorator(handler: EventHandler) -> EventHandler:
            self._start_handlers.append(handler)
            return handler

        return decorator

    def on_error(self, scope: ErrorScope = ErrorScope.LOCAL) -> Callable[[EventHandler], EventHandler]:
        """Register error handler."""

        def decorator(handler: EventHandler) -> EventHandler:
            self._error_handlers[scope].append(handler)
            return handler

        return decorator

    def on_disconnect(self) -> Callable[[EventHandler], EventHandler]:
        """Register disconnect handler."""

        def decorator(handler: EventHandler) -> EventHandler:
            self._disconnect_handlers.append(handler)
            return handler

        return decorator

    # Convenience methods for common event types
    def on_message(self, *filters: EventFilter) -> Callable[[EventHandler], EventHandler]:
        return self.on(EventType.MESSAGE_NEW, *filters)

    def on_message_edit(self, *filters: EventFilter) -> Callable[[EventHandler], EventHandler]:
        return self.on(EventType.MESSAGE_EDIT, *filters)

    def on_message_delete(self, *filters: EventFilter) -> Callable[[EventHandler], EventHandler]:
        return self.on(EventType.MESSAGE_DELETE, *filters)

    def on_message_read(self, *filters: EventFilter) -> Callable[[EventHandler], EventHandler]:
        return self.on(EventType.MESSAGE_READ, *filters)

    def on_typing(self, *filters: EventFilter) -> Callable[[EventHandler], EventHandler]:
        return self.on(EventType.TYPING, *filters)

    def on_presence(self, *filters: EventFilter) -> Callable[[EventHandler], EventHandler]:
        return self.on(EventType.PRESENCE, *filters)

    def on_reaction_update(self, *filters: EventFilter) -> Callable[[EventHandler], EventHandler]:
        return self.on(EventType.REACTION_ADD, *filters)
        # Note: Could also handle REACTION_REMOVE

    def on_chat_update(self, *filters: EventFilter) -> Callable[[EventHandler], EventHandler]:
        return self.on(EventType.CHAT_UPDATE, *filters)

    def on_raw(self, *filters: EventFilter) -> Callable[[EventHandler], EventHandler]:
        return self.on(EventType.RAW, *filters)

    def iter_routers(self) -> list["Router"]:
        """Get all routers in tree (depth-first)."""
        routers = [self]
        for child in self._child_routers:
            routers.extend(child.iter_routers())
        return routers

    def iter_handlers(self, event_type: EventType) -> list[HandlerEntry]:
        """Get all handlers for event type in tree."""
        handlers = []
        for router in self.iter_routers():
            handlers.extend(router._handlers.get(event_type, []))
        return handlers

    def iter_error_handlers(self, scope: ErrorScope) -> list[EventHandler]:
        """Get all error handlers for scope."""
        handlers = []
        for router in self.iter_routers():
            handlers.extend(router._error_handlers.get(scope, []))
        return handlers

    def iter_disconnect_handlers(self) -> list[EventHandler]:
        """Get all disconnect handlers."""
        handlers = []
        for router in self.iter_routers():
            handlers.extend(router._disconnect_handlers)
        return handlers

    def iter_start_handlers(self) -> list[EventHandler]:
        """Get all startup handlers."""
        handlers = []
        for router in self.iter_routers():
            handlers.extend(router._start_handlers)
        return handlers


class Dispatcher:
    """Event dispatcher that routes events to routers."""

    def __init__(self):
        self._root_router = Router("root")
        self._bound_client: Any = None
        self._internal_handlers: dict[EventType, list[EventHandler]] = defaultdict(list)

    @property
    def router(self) -> Router:
        return self._root_router

    def bind_client(self, client: Any) -> None:
        self._bound_client = client

    def include_router(self, router: Router) -> None:
        self._root_router.include_router(router)

    def on_internal(self, event_type: EventType) -> Callable[[EventHandler], EventHandler]:
        """Register internal handler (runs before user handlers)."""

        def decorator(handler: EventHandler) -> EventHandler:
            self._internal_handlers[event_type].append(handler)
            return handler

        return decorator

    async def emit_start(self) -> None:
        """Emit startup event to all handlers."""
        for handler in self._root_router.iter_start_handlers():
            try:
                await handler(None, self._bound_client)
            except Exception as e:
                await self.emit_error(e, EventType.START, None, handler, self._root_router)

    async def dispatch(self, event: Event) -> None:
        """Dispatch event through router tree."""
        # Run internal handlers first
        for handler in self._internal_handlers.get(event.type, []):
            try:
                await handler(event, self._bound_client)
            except Exception as e:
                await self.emit_error(e, event.type, event, handler, self._root_router)

        # Run user handlers
        handlers = self._root_router.iter_handlers(event.type)
        for entry in handlers:
            # Check filters
            try:
                if entry.filters:
                    filter_results = []
                    for f in entry.filters:
                        result = f(event)
                        if inspect.isawaitable(result):
                            result = await result
                        filter_results.append(result)
                    if not all(filter_results):
                        continue  # Filters didn't match

                await entry.handler(event, self._bound_client)
            except Exception as e:
                await self.emit_error(e, event.type, event, entry.handler, entry.router)

    async def emit_error(
        self,
        error: Exception,
        event_type: EventType,
        event: Event | None,
        handler: EventHandler | None,
        router: Router,
    ) -> bool:
        """Emit error to error handlers."""
        from ..types.event import ErrorEvent

        error_event = ErrorEvent(
            type=EventType.ERROR,
            timestamp=int(__import__("time").time() * 1000),
            error=str(error),
            error_type=type(error).__name__,
        )

        handled = False

        # First try LOCAL error handlers (router's own)
        for h in router._error_handlers.get(ErrorScope.LOCAL, []):
            try:
                from ..exceptions import DispatchError
                ctx = DispatchError(
                    str(error),
                    request_id=None,
                    endpoint=None,
                    transport=None,
                    original_error=error,
                )
                await h(error, ctx)
                handled = True
            except Exception:
                pass

        # Then try GLOBAL error handlers
        for h in self._root_router.iter_error_handlers(ErrorScope.GLOBAL):
            try:
                from ..exceptions import DispatchError
                ctx = DispatchError(
                    str(error),
                    request_id=None,
                    endpoint=None,
                    transport=None,
                    original_error=error,
                )
                await h(error, ctx)
                handled = True
            except Exception:
                pass

        return handled

    async def emit_disconnect(self, error: Exception | None, will_reconnect: bool, delay: float) -> None:
        """Emit disconnect to handlers."""
        for handler in self._root_router.iter_disconnect_handlers():
            try:
                await handler(error, will_reconnect, delay)
            except Exception:
                pass