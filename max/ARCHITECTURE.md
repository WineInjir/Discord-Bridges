# MaxPy Unified Architecture

## Design Principles

1. **Transport Abstraction** - Single API over REST, TCP, and WebSocket
2. **Async-First** - All I/O is async; sync wrapper only for convenience
3. **Type Safety** - Pydantic v2 models for all requests/responses/events
4. **Extensible Events** - Hierarchical router with filters (from PyMax)
5. **Unified Models** - Common domain models regardless of transport
6. **Reliability** - Exponential backoff, circuit breaker, idempotency
7. **Configuration** - Pydantic Settings + env vars + config file

---

## Package Structure

```
maxpy/
├── __init__.py              # Public exports
├── _version.py              # Version info
├── client.py                # Main entry point: MaxClient
├── config.py                # Configuration (Pydantic Settings)
├── exceptions.py            # Exception hierarchy
├── enums.py                 # Shared enums
├── types/                   # Domain models (Pydantic)
│   ├── __init__.py
│   ├── base.py              # BaseModel with camelCase aliases
│   ├── user.py              # User, Profile, Contact, Session
│   ├── chat.py              # Chat, Group, Channel, Member, InviteLink
│   ├── message.py           # Message, Attachment types, Reaction, Poll
│   ├── file.py              # File, Photo, Video, Voice, VideoNote
│   ├── event.py             # Event types (MessageEvent, ChatEvent, etc.)
│   └── common.py            # Common types (ChatId, MessageId, etc.)
├── transport/               # Transport abstraction layer
│   ├── __init__.py
│   ├── base.py              # Transport protocol, TransportConfig
│   ├── rest.py              # RESTTransport (Green-API)
│   ├── tcp.py               # TCPTransport (PyMax internal API)
│   ├── websocket.py         # WebSocketTransport (PyMax internal API)
│   └── factory.py           # TransportFactory
├── auth/                    # Authentication layer
│   ├── __init__.py
│   ├── base.py              # AuthFlow protocol
│   ├── rest.py              # RESTAuthFlow (Green-API instance token)
│   ├── sms.py               # SmsAuthFlow (PyMax)
│   ├── qr.py                # QrAuthFlow (PyMax)
│   ├── session.py           # SessionTokenAuthFlow
│   └── providers.py         # Code/Qr/Password provider protocols
├── session/                 # Session persistence
│   ├── __init__.py
│   ├── store.py             # StoreProtocol, SQLiteStore, MemoryStore
│   ├── models.py            # SessionInfo
│   └── manager.py           # SessionManager
├── connection/              # Connection management
│   ├── __init__.py
│   ├── manager.py           # ConnectionManager
│   ├── pending.py           # Pending request tracking
│   └── state.py             # ConnectionState enum
├── dispatch/                # Event dispatch & routing
│   ├── __init__.py
│   ├── dispatcher.py        # Dispatcher
│   ├── router.py            # Router
│   ├── filters.py           # Built-in filters
│   ├── mapping.py           # EventMapper (transport-specific)
│   └── enums.py             # EventType, ErrorScope
├── api/                     # High-level API services
│   ├── __init__.py
│   ├── facade.py            # ApiFacade
│   ├── messages.py          # MessageService
│   ├── chats.py             # ChatService
│   ├── users.py             # UserService
│   ├── files.py             # FileService
│   ├── self.py              # SelfService (profile, folders, privacy)
│   ├── bots.py              # BotService
│   └── auth.py              # AuthService
├── files/                   # File abstraction
│   ├── __init__.py
│   ├── base.py              # BaseFile, AsyncFileReader
│   ├── photo.py             # Photo
│   ├── video.py             # Video, VideoNote
│   ├── voice.py             # Voice
│   └── document.py          # Document/File
├── formatting/              # Message formatting
│   ├── __init__.py
│   ├── markdown.py          # MarkdownFormatter
│   └── elements.py          # Markdown elements (Bold, Code, Link, etc.)
├── utils/                   # Utilities
│   ├── __init__.py
│   ├── retry.py             # Retry policies, exponential backoff
│   ├── rate_limit.py        # Rate limiter (token bucket)
│   ├── fingerprint.py       # Device fingerprinting
│   ├── version.py           # Version catalog
│   └── logging.py           # Logging configuration
└── sync/                    # Sync wrapper (optional)
    ├── __init__.py
    └── client.py            # SyncMaxClient
```

---

## Layer Responsibilities

### 1. Transport Layer (`transport/`)
- **Transport** (Protocol): `connect()`, `send()`, `receive()`, `close()`, `is_connected`
- **RESTTransport**: `aiohttp` client for Green-API REST endpoints
- **TCPTransport**: PyMax binary protocol (msgpack + custom framing)
- **WebSocketTransport**: PyMax JSON protocol over WebSocket
- **TransportFactory**: Creates transport based on config

### 2. Authentication Layer (`auth/`)
- **AuthFlow** (Protocol): `authenticate()`, `refresh()`, `logout()`
- **RESTAuthFlow**: Green-API instance token (no flow, just headers)
- **SmsAuthFlow**: Phone → code → optional 2FA
- **QrAuthFlow**: QR request → display → poll → confirm → optional 2FA
- **SessionTokenAuthFlow**: Direct token restore from session store
- **Providers**: `SmsCodeProvider`, `QrHandler`, `PasswordProvider`

### 3. Session Layer (`session/`)
- **StoreProtocol**: `load()`, `save()`, `delete()`, `update_token()`
- **SQLiteStore**: Persistent with migration (from PyMax)
- **MemoryStore**: In-memory for testing/ephemeral
- **SessionManager**: Coordinates store + auth flow + token lifecycle

### 4. Connection Layer (`connection/`)
- **ConnectionManager**: 
  - Manages transport lifecycle
  - Request/response correlation (sequence IDs)
  - Background receive loop
  - Reconnect with exponential backoff
  - Ping/keepalive
- **PendingRequests**: `Future` per request, timeout handling

### 5. Dispatch Layer (`dispatch/`)
- **Dispatcher**: 
  - Routes events to routers
  - Manages handler registration
  - Error handling with scopes (GLOBAL/LOCAL)
  - Startup/disconnect handlers
- **Router**: Hierarchical, composable, filter support
- **Filters**: Sync/async predicates, combinable
- **EventMapper**: Transport-specific frame → unified Event

### 6. API Layer (`api/`)
- **ApiFacade**: Aggregates all services
- **Services**: MessageService, ChatService, UserService, FileService, SelfService, BotService, AuthService
- Each service uses transport-agnostic request/response models

### 7. File Layer (`files/`)
- **BaseFile**: Abstract async file source (path, URL, bytes)
- **Photo/Video/Voice/VideoNote/Document**: Typed subclasses with validation
- **AsyncFileReader**: Chunked reading for uploads

---

## Unified Public API

```python
# Main entry point
from maxpy import MaxClient, MaxConfig

# Configuration
config = MaxConfig(
    # Transport selection
    transport="tcp",  # "rest" | "tcp" | "websocket"
    
    # Auth (varies by transport)
    phone="+79001234567",      # TCP: SMS auth
    # token="...",              # REST: instance token / TCP: session token
    
    # Session
    session_name="my_session",
    persist_session=True,
    
    # Connection
    reconnect=True,
    reconnect_delay=1.0,
    request_timeout=30.0,
    
    # Optional
    proxy="socks5://...",
    log_level="INFO",
)

# Client
client = MaxClient(config)

# Event handlers (PyMax-style router)
@client.router.on_message()
async def on_message(message: Message, client: MaxClient):
    await message.reply("Echo: " + message.text)

@client.router.on_start()
async def on_start(client: MaxClient):
    print("Connected!")

# Lifecycle
await client.start()  # Connect, auth, start dispatch loop

# High-level API (transport-agnostic)
await client.messages.send(chat_id, "Hello!")
await client.messages.send_photo(chat_id, Photo(path="photo.jpg"))
await client.chats.create_group("My Group", [user_id1, user_id2])
await client.users.get_profile()

# File operations
file_id = await client.files.upload(Document(path="large.pdf"))
await client.messages.send_file(chat_id, file_id)

# Graceful shutdown
await client.stop()
```

---

## Transport-Specific Capabilities

| Feature | REST (Green-API) | TCP (Internal) | WebSocket (Internal) |
|---------|------------------|----------------|---------------------|
| **Auth** | Instance token only | SMS, QR, Session | QR, Session |
| **Real-time Events** | Long-polling (blocking) | Native push | Native push |
| **Message Send** | ✅ | ✅ | ✅ |
| **Message Edit/Delete** | ❌ | ✅ | ✅ |
| **Reactions** | ❌ | ✅ | ✅ |
| **Polls** | ❌ | ✅ | ✅ |
| **Chat Management** | Groups only | Full (groups, channels) | Full |
| **User Presence** | ❌ | ✅ | ✅ |
| **Session Persistence** | Manual | Automatic (SQLite) | Automatic (SQLite) |
| **File Upload** | Multipart (sync) | Chunked HTTP + waiter | Chunked HTTP + waiter |
| **Large Files** | ❌ (memory) | ✅ Streaming | ✅ Streaming |
| **Rate Limits** | 429 retry only | App-level | App-level |
| **Multi-device** | No | Yes (sessions API) | Yes |
| **ToS Risk** | Official API | **Unofficial** | **Unofficial** |

---

## Error Handling Strategy

```
MaxError (base)
├── ConfigError
├── AuthError
│   ├── InvalidCredentialsError
│   ├── TwoFactorRequiredError
│   ├── SessionExpiredError
│   └── QRCodeExpiredError
├── ConnectionError
│   ├── TransportError
│   ├── ReconnectFailedError
│   └── PingTimeoutError
├── APIError
│   ├── RateLimitError (retry_after)
│   ├── NotFoundError
│   ├── ForbiddenError
│   ├── ValidationError
│   └── ServerError
├── FileError
│   ├── UploadError
│   ├── DownloadError
│   └── ValidationError
└── DispatchError
```

All errors include: `request_id`, `endpoint`, `transport`, `original_error`, `timestamp`

---

## Retry & Reliability

### Connection Retry (Exponential Backoff)
```python
RetryPolicy(
    max_attempts=10,
    base_delay=1.0,
    max_delay=60.0,
    exponent=2.0,
    jitter=0.1,
    retry_on=(ConnectionError, TimeoutError, ServerError, RateLimitError),
)
```

### Request Retry (Idempotent Only)
- GET, PUT, DELETE: retry with backoff
- POST (send message): **NO RETRY** (idempotency key required)
- Upload: Resume from last chunk

### Circuit Breaker
- Trip after 5 consecutive failures
- Half-open after 30s
- Reset on success

---

## Configuration Precedence

1. Constructor arguments (highest)
2. Environment variables (`MAXPY_*`)
3. Config file (`~/.config/maxpy/config.toml` or `./maxpy.toml`)
4. Defaults (lowest)

```toml
# maxpy.toml
[transport]
type = "tcp"
host = "api2.oneme.ru"
port = 443

[auth]
phone = "+79001234567"

[session]
name = "default"
persist = true
path = "~/.local/share/maxpy/sessions"

[connection]
reconnect = true
reconnect_delay = 1.0
request_timeout = 30.0
ping_interval = 30.0

[logging]
level = "INFO"
format = "json"  # or "pretty"
```

---

## Testing Strategy

### Unit Tests (Fast, No Network)
- Mock transports (`FakeTransport`)
- Test all services with controlled responses
- Test router/filter logic
- Test retry policies
- Test model validation

### Integration Tests (Requires Test Account)
- Real transport against test MAX instance
- Test full auth flows
- Test message send/receive
- Test file upload/download
- Test reconnect scenarios

### Fixtures
- `fake_transport`: Controllable transport mock
- `fake_store`: In-memory session store
- `test_config`: Pre-configured test config
- `sample_messages`: Pre-built message fixtures

---

## Migration from Source Libraries

### From Green-API (`max-api-client-python`)
```python
# Old
from max_api_client_python import GreenApi
api = GreenApi(idInstance, apiTokenInstance)
api.sending.sendMessage(chatId, "Hello")

# New
from maxpy import MaxClient, MaxConfig
config = MaxConfig(transport="rest", token=f"{idInstance}:{apiTokenInstance}")
client = MaxClient(config)
await client.start()
await client.messages.send(chatId, "Hello")
```

### From PyMax
```python
# Old
from pymax import Client
client = Client(phone="+79001234567")
await client.start()

# New (minimal changes)
from maxpy import MaxClient, MaxConfig
config = MaxConfig(transport="tcp", phone="+79001234567")
client = MaxClient(config)
await client.start()
```

---

## Version Compatibility

- **Python**: 3.10+
- **Dependencies**: 
  - `pydantic>=2.10`
  - `pydantic-settings>=2.0`
  - `aiohttp>=3.9`
  - `websockets>=12.0`
  - `aiofiles>=23.0`
  - `python-socks>=2.4`
  - `msgpack>=1.0`
  - `zstandard>=0.22`
  - `lz4>=4.3`
  - `aiosqlite>=0.19`
  - `tenacity>=8.2` (for retry)
  - `pytz>=2024.1` (for datetime handling)

---

## Development Roadmap

### Phase 1 (Core) ✓
- [x] Architecture design
- [ ] Transport abstraction (REST, TCP, WS)
- [ ] Auth flows (SMS, QR, Session, REST)
- [ ] Session persistence (SQLite)
- [ ] Connection manager + reconnect
- [ ] Dispatcher + Router + Filters
- [ ] Base models + exceptions

### Phase 2 (API Services)
- [ ] MessageService (send, edit, delete, history, reactions)
- [ ] ChatService (create, manage, members, invites)
- [ ] UserService (lookup, contacts, sessions)
- [ ] FileService (upload, download, streaming)
- [ ] SelfService (profile, folders, privacy)
- [ ] BotService

### Phase 3 (Reliability)
- [ ] Retry policies + circuit breaker
- [ ] Rate limiter
- [ ] Idempotency keys
- [ ] Request timeout handling

### Phase 4 (Developer Experience)
- [ ] Sync wrapper
- [ ] CLI tool
- [ ] Comprehensive docs
- [ ] Migration guides
- [ ] Examples

### Phase 5 (Testing & Release)
- [ ] Unit tests (>90% coverage)
- [ ] Integration tests
- [ ] CI/CD pipeline
- [ ] PyPI release