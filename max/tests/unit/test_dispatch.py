"""Unit tests for dispatcher and filters."""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from maxpy.dispatch import (
    Router,
    Dispatcher,
    Filter,
    AndFilter,
    OrFilter,
    NotFilter,
    CommandFilter,
    TextFilter,
    MessageFilter,
    PrivateChatFilter,
    GroupChatFilter,
    FromUserFilter,
    OutgoingFilter,
    IncomingFilter,
    and_,
    or_,
    not_,
)
from maxpy.types import Message
from maxpy.enums import EventType, ChatType, ErrorScope


class TestRouter:
    """Tests for Router."""

    def test_register_handler(self):
        router = Router()
        handler = lambda event, client: None

        router.on(EventType.MESSAGE_NEW)(handler)

        handlers = router.iter_handlers(EventType.MESSAGE_NEW)
        assert len(handlers) == 1
        assert handlers[0].handler == handler

    def test_register_multiple_handlers(self):
        router = Router()
        handler1 = lambda event, client: None
        handler2 = lambda event, client: None

        router.on(EventType.MESSAGE_NEW)(handler1)
        router.on(EventType.MESSAGE_NEW)(handler2)

        handlers = router.iter_handlers(EventType.MESSAGE_NEW)
        assert len(handlers) == 2

    def test_include_router(self):
        parent = Router("parent")
        child = Router("child")
        handler = lambda event, client: None

        child.on(EventType.MESSAGE_NEW)(handler)
        parent.include_router(child)

        handlers = parent.iter_handlers(EventType.MESSAGE_NEW)
        assert len(handlers) == 1

    def test_convenience_decorators(self):
        router = Router()

        @router.on_message()
        def handle_message(event, client):
            pass

        @router.on_start()
        def handle_start(event, client):
            pass

        @router.on_error()
        def handle_error(error, ctx):
            pass

        assert len(router.iter_handlers(EventType.MESSAGE_NEW)) == 1
        assert len(router.iter_start_handlers()) == 1
        assert len(router.iter_error_handlers(ErrorScope.LOCAL)) == 1

    def test_filters(self):
        router = Router()
        filter1 = lambda event: True
        filter2 = lambda event: False

        @router.on(EventType.MESSAGE_NEW, filter1, filter2)
        def handler(event, client):
            pass

        handlers = router.iter_handlers(EventType.MESSAGE_NEW)
        assert len(handlers[0].filters) == 2


class TestDispatcher:
    """Tests for Dispatcher."""

    @pytest.mark.asyncio
    async def test_emit_start(self):
        dispatcher = Dispatcher()
        client = MagicMock()
        dispatcher.bind_client(client)

        called = []

        @dispatcher.router.on_start()
        async def on_start(event, client):
            called.append(True)

        await dispatcher.emit_start()
        assert len(called) == 1

    @pytest.mark.asyncio
    async def test_dispatch_event(self):
        dispatcher = Dispatcher()
        client = MagicMock()
        dispatcher.bind_client(client)

        received = []

        @dispatcher.router.on_message()
        async def on_message(event, client):
            received.append(event)

        # Create a mock message event
        from maxpy.types import MessageEvent, Message
        msg = Message(
            id="msg_1",
            chat_id="chat_1",
            sender_id="user_1",
            text="Hello",
            created_at=1234567890,
        )
        event = MessageEvent(message=msg, is_new=True)

        await dispatcher.dispatch(event)
        assert len(received) == 1
        assert received[0] is event


class TestFilters:
    """Tests for filters."""

    def test_message_filter(self):
        msg = Message(id="1", chat_id="c1", sender_id="u1", text="Hello", created_at=123)
        f = MessageFilter()
        assert f(msg) is True

    def test_text_filter_exact(self):
        msg = Message(id="1", chat_id="c1", sender_id="u1", text="Hello", created_at=123)
        f = TextFilter(text="Hello")
        assert f(msg) is True

        f = TextFilter(text="World")
        assert f(msg) is False

    def test_text_filter_contains(self):
        msg = Message(id="1", chat_id="c1", sender_id="u1", text="Hello world", created_at=123)
        f = TextFilter(contains="world")
        assert f(msg) is True

        f = TextFilter(contains="foo")
        assert f(msg) is False

    def test_command_filter(self):
        msg = Message(id="1", chat_id="c1", sender_id="u1", text="/start", created_at=123)
        f = CommandFilter("start")
        assert f(msg) is True

        msg = Message(id="1", chat_id="c1", sender_id="u1", text="!start", created_at=123)
        f = CommandFilter("start", prefixes=["/", "!"])
        assert f(msg) is True

        msg = Message(id="1", chat_id="c1", sender_id="u1", text="/stop", created_at=123)
        f = CommandFilter("start")
        assert f(msg) is False

    def test_from_user_filter(self):
        msg = Message(id="1", chat_id="c1", sender_id="user_123", text="Hi", created_at=123)
        f = FromUserFilter("user_123")
        assert f(msg) is True

        f = FromUserFilter("user_456")
        assert f(msg) is False

    def test_outgoing_filter(self):
        msg = Message(id="1", chat_id="c1", sender_id="u1", text="Hi", created_at=123, is_outgoing=True)
        f = OutgoingFilter()
        assert f(msg) is True

        msg = Message(id="1", chat_id="c1", sender_id="u1", text="Hi", created_at=123, is_outgoing=False)
        f = OutgoingFilter()
        assert f(msg) is False

    def test_incoming_filter(self):
        msg = Message(id="1", chat_id="c1", sender_id="u1", text="Hi", created_at=123, is_outgoing=False)
        f = IncomingFilter()
        assert f(msg) is True

    def test_and_filter(self):
        msg = Message(id="1", chat_id="c1", sender_id="u1", text="/start", created_at=123, is_outgoing=True)
        f = and_(CommandFilter("start"), OutgoingFilter())
        assert f(msg) is True

        msg = Message(id="1", chat_id="c1", sender_id="u1", text="/stop", created_at=123, is_outgoing=True)
        assert f(msg) is False

    def test_or_filter(self):
        msg = Message(id="1", chat_id="c1", sender_id="u1", text="Hello", created_at=123)
        f = or_(TextFilter(contains="Hello"), TextFilter(contains="World"))
        assert f(msg) is True

        msg = Message(id="1", chat_id="c1", sender_id="u1", text="Foo", created_at=123)
        assert f(msg) is False

    def test_not_filter(self):
        msg = Message(id="1", chat_id="c1", sender_id="u1", text="Hello", created_at=123)
        f = not_(TextFilter(contains="World"))
        assert f(msg) is True

        msg = Message(id="1", chat_id="c1", sender_id="u1", text="World", created_at=123)
        assert f(msg) is False

    def test_filter_composition(self):
        msg = Message(id="1", chat_id="c1", sender_id="user_1", text="/start hello", created_at=123)

        # Complex filter: command "start" AND from user_1 AND contains "hello"
        f = and_(
            CommandFilter("start"),
            FromUserFilter("user_1"),
            TextFilter(contains="hello"),
        )
        assert f(msg) is True