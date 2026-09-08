# MaxPy

[![PyPI](https://img.shields.io/pypi/v/maxpy)](https://pypi.org/project/maxpy/)
[![Python](https://img.shields.io/pypi/pyversions/maxpy)](https://pypi.org/project/maxpy/)
[![License](https://img.shields.io/pypi/l/maxpy)](https://github.com/maxpy/maxpy/blob/main/LICENSE)

**Unified Python SDK for MAX messenger** - combining Green-API REST API and Internal MAX API (TCP/WebSocket) into a single, type-safe, async-first library.

## Features

- 🔄 **Multi-Transport**: REST (Green-API), TCP (Mobile API), WebSocket (Web API)
- 🔐 **Multiple Auth**: Instance tokens, Session tokens, SMS, QR code, 2FA
- 📦 **Type-Safe**: Full Pydantic v2 models for all requests/responses/events
- ⚡ **Async-First**: Built on asyncio, no blocking I/O
- 🎯 **Event System**: Hierarchical routers with filters (inspired by aiogram/PyMax)
- 💾 **Session Persistence**: SQLite with auto-migration
- 🔌 **Auto-Reconnect**: Exponential backoff with circuit breaker
- 📁 **File Handling**: Streaming upload/download with progress
- 📝 **Markdown**: Rich message formatting
- 🧪 **Well-Tested**: Unit + integration tests with mock transports

## Installation

```bash
pip install maxpy

# With optional dependencies
pip install maxpy[tinytag]  # For voice/video duration detection
pip install maxpy[dev]      # Development dependencies
```

## Quick Start

### REST API (Green-API)

```python
import asyncio
from maxpy import MaxClient, TransportType

async def main():
    client = MaxClient(
        transport=TransportType.REST,
        id_instance=123456789,
        api_token_instance="your_token_here",
    )

    await client.start()

    # Send message
    await client.messages.send_text("79001234567@c.us", "Hello from MaxPy!")

    # Send photo
    from maxpy import Photo
    await client.messages.send_photo("79001234567@c.us", Photo(path="photo.jpg"), caption="Nice photo!")

    await client.stop()

asyncio.run(main())
```

### Internal API (TCP - Mobile)

```python
import asyncio
from maxpy import MaxClient, TransportType

async def main():
    client = MaxClient(
        transport=TransportType.TCP,
        phone="+79001234567",
        session_name="my_session",
    )

    # Register message handler
    @client.on_message()
    async def handle_message(message, client):
        if message.text == "ping":
            await message.reply("pong!")

    await client.start()
    print("Bot running... Press Ctrl+C to stop")

    # Keep running
    try:
        await asyncio.Event().wait()
    except KeyboardInterrupt:
        await client.stop()

asyncio.run(main())
```

### Internal API (WebSocket - Web)

```python
import asyncio
from maxpy import MaxClient, TransportType

async def main():
    client = MaxClient(
        transport=TransportType.WEBSOCKET,
        # QR code will be shown in console
    )

    @client.on_message()
    async def on_message(message, client):
        print(f"New message: {message.text}")

    await client.start()
    # QR code displayed - scan with MAX app

asyncio.run(main())
```

## Configuration

### Environment Variables

```bash
# Transport
MAXPY_TRANSPORT__TYPE=tcp
MAXPY_TRANSPORT__HOST=api2.oneme.ru
MAXPY_TRANSPORT__PORT=443
MAXPY_TRANSPORT__PROXY=socks5://user:pass@host:port

# Auth
MAXPY_AUTH__TYPE=sms
MAXPY_AUTH__PHONE=+79001234567

# Session
MAXPY_SESSION__NAME=default
MAXPY_SESSION__PERSIST=true
MAXPY_SESSION__PATH=~/.local/share/maxpy/sessions

# Connection
MAXPY_CONNECTION__RECONNECT=true
MAXPY_CONNECTION__RECONNECT_DELAY=1.0
MAXPY_CONNECTION__REQUEST_TIMEOUT=30.0
```

### Config File (TOML)

```toml
# ~/.config/maxpy/config.toml
[transport]
type = "tcp"
host = "api2.oneme.ru"
port = 443

[auth]
type = "sms"
phone = "+79001234567"

[session]
name = "default"
persist = true

[connection]
reconnect = true
reconnect_delay = 1.0
request_timeout = 30.0

[logging]
level = "INFO"
format = "pretty"
```

### Programmatic Config

```python
from maxpy import MaxClient, MaxConfig, TransportConfig, AuthConfig

config = MaxConfig(
    transport=TransportConfig(type="tcp", proxy="socks5://..."),
    auth=AuthConfig(type="sms", phone="+79001234567"),
    session=SessionConfig(name="bot", persist=True),
)

client = MaxClient(config)
```

## Event Handling

### Decorators

```python
from maxpy import MaxClient, CommandFilter, TextFilter

client = MaxClient(...)

# Handle all messages
@client.on_message()
async def on_any_message(message, client):
    print(f"Received: {message.text}")

# Handle specific command
@client.on_message(CommandFilter("start"))
async def on_start(message, client):
    await message.reply("Welcome!")

# Handle text containing keyword
@client.on_message(TextFilter(contains="help"))
async def on_help(message, client):
    await message.reply("Help text...")

# Handle photos only
@client.on_message(PhotoFilter())
async def on_photo(message, client):
    await message.reply("Nice photo!")

# Handle messages from specific user
@client.on_message(FromUserFilter(123456789))
async def on_admin(message, client):
    await message.reply("Hello admin!")
```

### Routers (Modular Handlers)

```python
from maxpy import Router

# Create sub-router
admin_router = Router("admin")

@admin_router.on_message(CommandFilter("stats"))
async def admin_stats(message, client):
    await message.reply("Bot stats...")

@admin_router.on_message(CommandFilter("broadcast"))
async def admin_broadcast(message, client):
    await message.reply("Broadcast sent!")

# Include in main router
client.include_router(admin_router)
```

### Startup & Error Handlers

```python
@client.on_start()
async def on_startup(client):
    print("Bot started!")
    # Send notification to admin
    await client.messages.send_text("admin_id", "Bot is online!")

@client.on_error(scope="global")
async def on_error(error, context):
    print(f"Error in {context.handler}: {error}")
    # Send to error tracking service
```

## File Handling

```python
from maxpy import Photo, Video, Voice, VideoNote, Document

# Send photo from file
photo = Photo(path="photo.jpg")
await client.messages.send_photo(chat_id, photo, caption="My photo")

# Send photo from bytes
photo = Photo(raw=image_bytes, name="image.png")
await client.messages.send_photo(chat_id, photo)

# Send photo from URL
photo = Photo(url="https://example.com/image.jpg")
await client.messages.send_photo(chat_id, photo)

# Large file upload (streaming)
doc = Document(path="large_file.pdf")
file_id = await client.files.upload_file(doc)
await client.messages.send_file(chat_id, file_id)

# Video note (round video)
video_note = VideoNote(path="circle.mp4", duration=30)
await client.messages.send_video_note(chat_id, video_note)
```

## Chat Management

```python
# Create group
chat = await client.chats.create_group("My Group", ["user1", "user2", "user3"])

# Invite users
await client.chats.invite_users_to_group(chat_id, ["user4", "user5"])

# Get members
members = await client.chats.get_members(chat_id)

# Promote admin
await client.chats.add_admin(chat_id, "user1", permissions={"can_delete_messages": True})

# Change settings
await client.chats.change_group_settings(chat_id, can_send_media=False, pre_history=True)

# Join via invite link
chat = await client.chats.join_group("https://max.ru/join/abc123")
```

## User Management

```python
# Get profile
profile = await client.self.get_profile()

# Update profile
await client.self.update_profile(first_name="New Name", bio="New bio")

# Search by phone
user = await client.users.search_by_phone("+79001234567")

# Get contacts
contacts = await client.users.get_cached_users()

# Add contact
await client.users.add_contact("user_id")

# Get active sessions
sessions = await client.users.get_sessions()
await client.users.close_session("session_id")
```

## Error Handling

```python
from maxpy import (
    MaxError,
    AuthError,
    SessionExpiredError,
    RateLimitError,
    ConnectionError,
    APIError,
)

try:
    await client.messages.send_text(chat_id, "Hello")
except SessionExpiredError:
    # Token expired, relogin
    await client.relogin()
except RateLimitError as e:
    # Wait and retry
    await asyncio.sleep(e.retry_after or 5)
    await client.messages.send_text(chat_id, "Hello")
except ConnectionError:
    # Network issue, will auto-reconnect
    pass
except APIError as e:
    print(f"API error {e.status_code}: {e.message}")
except MaxError as e:
    print(f"MaxPy error: {e}")
```

## Running as a Bot

```python
# bot.py
from maxpy import MaxClient, TransportType, CommandFilter
import asyncio

client = MaxClient(
    transport=TransportType.TCP,
    phone="+79001234567",
    session_name="my_bot",
)

@client.on_message(CommandFilter("start"))
async def cmd_start(message, client):
    await message.reply("👋 Hello! I'm a MaxPy bot.")

@client.on_message(CommandFilter("echo"))
async def cmd_echo(message, client):
    text = message.text.replace("/echo ", "", 1)
    await message.reply(text or "Nothing to echo")

@client.on_message(CommandFilter("photo"))
async def cmd_photo(message, client):
    from maxpy import Photo
    photo = Photo(url="https://picsum.photos/400/300")
    await client.messages.send_photo(message.chat_id, photo, caption="Random photo!")

@client.on_start()
async def on_start(client):
    print("Bot started!")

async def main():
    await client.start()
    try:
        await asyncio.Event().wait()
    except KeyboardInterrupt:
        await client.stop()

if __name__ == "__main__":
    asyncio.run(main())
```

Run with:
```bash
python bot.py
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
                        MaxClient
├─────────────────────────────────────────────────────────────┤
  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
  │  Transport  │  │    Auth     │  │     Session         │  │
  │  (REST/TCP/WS) │  (SMS/QR/Token) │  (SQLite/Memory)    │  │
  └─────────────┘  └─────────────┘  └─────────────────────┘  │
├─────────────────────────────────────────────────────────────┤
  ┌──────────────────────┐  ┌──────────────────────────────┐  │
  │   ConnectionManager  │  │         Dispatcher           │  │
  │  (Reconnect, Ping,   │  │  (Routers, Filters, Events)  │  │
  │   Request/Response)  │  │                              │  │
  └──────────────────────┘  └──────────────────────────────┘  │
├─────────────────────────────────────────────────────────────┤
  ┌────────────────────────────────────────────────────────┐  │
  │                    ApiFacade                           │  │
  │  Messages │ Chats │ Users │ Files │ Self │ Bots │ Auth │  │
  └────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

## Comparison

| Feature | Green-API | PyMax | **MaxPy** |
|---------|-----------|-------|-----------|
| Transport | REST only | TCP + WS | **REST + TCP + WS** |
| Auth | Instance token | SMS + QR + Session | **All of the above** |
| Real-time | Long-polling | Native push | **Native push** |
| Models | Raw dicts | Pydantic | **Pydantic v2** |
| Events | Basic callbacks | Router + Filters | **Router + Filters** |
| Session | Manual | SQLite | **SQLite + Memory** |
| Reconnect | None | Basic | **Exponential + Circuit Breaker** |
| Files | Memory only | Streaming | **Streaming + Chunked** |
| Type Safety | Minimal | Good | **Full** |

## Limitations

⚠️ **Important**: TCP and WebSocket transports use MAX's **internal API** which is:
- Not officially documented
- Subject to change without notice
- May violate Terms of Service
- Use at your own risk

For production bots, consider using **Green-API REST transport** which is official and stable.

## Contributing

1. Fork the repository
2. Create feature branch
3. Add tests
4. Run `ruff check` and `mypy`
5. Submit PR

## License

MIT License - see [LICENSE](LICENSE) for details.

## Acknowledgments

- [green-api/max-api-client-python](https://github.com/green-api/max-api-client-python) - REST API reference
- [MaxApiTeam/PyMax](https://github.com/MaxApiTeam/PyMax) - Internal API implementation
- [aiogram](https://github.com/aiogram/aiogram) - Router/filter inspiration