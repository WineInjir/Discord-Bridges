# Feature Comparison Matrix: Green-API vs PyMax

| FEATURE | REPOSITORY | IMPLEMENTATION | STATUS | ACTION |
|---------|------------|----------------|--------|--------|
| **Authentication** | | | | |
| SMS Auth (code) | PyMax | `SmsAuthFlow.request_code()` + `send_code()` | ✅ Complete | KEEP |
| SMS Auth (Green-API) | Green-API | `account.startAuthorization()` + `sendAuthorizationCode()` | ⚠️ Deprecated | REMOVE |
| QR Auth | PyMax | `QrAuthFlow` + `ConsoleQrHandler` | ✅ Complete | KEEP |
| QR Auth (Green-API) | Green-API | `account.qr()` | ✅ Works | MERGE |
| Session Token | Both | PyMax: `ExtraConfig.token`; Green-API: `idInstance`+`apiTokenInstance` | ✅ Both | MERGE |
| 2FA Password | PyMax | `AuthService.check_password()` | ✅ Complete | KEEP |
| Registration | PyMax | `AuthService.confirm_registration()` | ✅ Complete | KEEP |
| Session Persistence | PyMax | SQLite `SessionStore` with migration | ✅ Complete | KEEP |
| Session Persistence | Green-API | None | ❌ Missing | IMPROVE |
| Logout | Both | PyMax: `AuthService.logout()`; Green-API: `account.logout()` | ✅ Both | MERGE |
| **Transport** | | | | |
| HTTP/REST | Green-API | `requests.Session` (sync only) | ✅ Works | KEEP (as RESTTransport) |
| TCP (Internal API) | PyMax | `TCPTransport` + custom binary protocol (msgpack) | ✅ Complete | KEEP |
| WebSocket (Internal API) | PyMax | `WebSocketTransport` + JSON protocol | ✅ Complete | KEEP |
| Proxy Support | PyMax | `python-socks` (SOCKS5/HTTP) | ✅ Complete | KEEP |
| SSL/TLS | PyMax | Custom CA cert embedded | ✅ Complete | KEEP |
| Compression | PyMax | LZ4/Zstd decoder only (encoder disabled) | ⚠️ Partial | IMPROVE |
| **Client Lifecycle** | | | | |
| Start/Connect | PyMax | `Client.connect()` + `Client.start()` (reconnect loop) | ✅ Complete | KEEP |
| Start (Green-API) | Green-API | Implicit on first request | ✅ Works | MERGE |
| Stop/Close | Both | PyMax: `close()`; Green-API: none explicit | ✅ PyMax | KEEP |
| Reconnect | PyMax | Configurable delay, infinite loop | ✅ Complete | KEEP |
| Relogin on Token Expiry | PyMax | Auto-detect `FAIL_LOGIN_TOKEN` → relogin | ✅ Complete | KEEP |
| Graceful Shutdown | PyMax | Task cancellation, connection close | ✅ Complete | KEEP |
| Connection State | PyMax | `is_open`, `_connection_lost` | ✅ Complete | KEEP |
| **Messages** | | | | |
| Send Text | Both | PyMax: `send_message()`; Green-API: `sending.sendMessage()` | ✅ Both | MERGE |
| Send File (Upload) | Both | PyMax: upload URL + HTTP POST; Green-API: multipart | ✅ Both | MERGE |
| Send File (URL) | Green-API | `sending.sendFileByUrl()` | ✅ Works | KEEP |
| Send Photo | PyMax | `UploadService.upload_photo()` | ✅ Complete | KEEP |
| Send Video | PyMax | `UploadService.upload_video()` + waiter | ✅ Complete | KEEP |
| Send Voice | PyMax | `UploadService.upload_voice()` + waiter | ✅ Complete | KEEP |
| Send VideoNote | PyMax | `UploadService.upload_video_note()` | ✅ Complete | KEEP |
| Send Poll | PyMax | `PollAttachment` in message | ✅ Complete | KEEP |
| Send Location | Green-API | ❌ Not implemented | ❌ Missing | REIMPLEMENT |
| Send Contact | Green-API | ❌ Not implemented | ❌ Missing | REIMPLEMENT |
| Edit Message | PyMax | `MessageService.edit_message()` | ✅ Complete | KEEP |
| Delete Message | Both | PyMax: `delete_message()`; Green-API: ❌ | ✅ PyMax | KEEP |
| Forward Message | PyMax | `MessageService.forward_message()` | ✅ Complete | KEEP |
| Reply/Quote | Both | Both support `reply_to`/`quotedMessageId` | ✅ Both | MERGE |
| Reactions | PyMax | `add_reaction`, `get_reactions`, `remove_reaction` | ✅ Complete | KEEP |
| Read Receipts | Both | PyMax: `read_message()`; Green-API: `marking.readChat()` | ✅ Both | MERGE |
| Message History | Both | PyMax: `fetch_history()`; Green-API: `journals.getChatHistory()` | ✅ Both | MERGE |
| Get Message by ID | Both | PyMax: `get_message()`; Green-API: `journals.getMessage()` | ✅ Both | MERGE |
| Search Messages | Both | ❌ Neither implements | ❌ Missing | REIMPLEMENT |
| Scheduled Send | PyMax | `send_at` parameter (datetime/timedelta) | ✅ Complete | KEEP |
| Pin Message | PyMax | `pin_message()` | ✅ Complete | KEEP |
| **Chats** | | | | |
| Get Chat Info | PyMax | `ChatService.get_chat()` | ✅ Complete | KEEP |
| List Chats | Both | PyMax: `fetch_chats()`; Green-API: `journals.getChats()` | ✅ Both | MERGE |
| Create Group | Both | PyMax: `create_group()`; Green-API: `groups.createGroup()` | ✅ Both | MERGE |
| Create Channel | PyMax | `ChatService.invite_users_to_channel()` | ✅ Complete | KEEP |
| Rename Chat | Both | PyMax: `change_group_settings()`; Green-API: `groups.updateGroupName()` | ✅ Both | MERGE |
| Get Members | PyMax | `get_chat_members()` | ✅ Complete | KEEP |
| Add Participant | Both | PyMax: `invite_users_to_group()`; Green-API: `groups.addGroupParticipant()` | ✅ Both | MERGE |
| Remove Participant | Both | PyMax: `remove_users_from_group()`; Green-API: `groups.removeGroupParticipant()` | ✅ Both | MERGE |
| Promote/Demote Admin | Both | PyMax: `add_admin()`; Green-API: `setGroupAdmin`/`removeAdmin` | ✅ Both | MERGE |
| Set Avatar | Both | PyMax: `change_group_profile()`; Green-API: `groups.setGroupPicture()` | ✅ Both | MERGE |
| Leave Chat | Both | PyMax: `leave_group()`; Green-API: `groups.leaveGroup()` | ✅ Both | MERGE |
| Delete Chat | PyMax | `delete_chat()` | ✅ Complete | KEEP |
| Invite Links | PyMax | `resolve_group_by_link()`, `rework_invite_link()` | ✅ Complete | KEEP |
| Join Requests | PyMax | `get/confirm/decline_join_requests()` | ✅ Complete | KEEP |
| Chat Folders | PyMax | `SelfService` folders API | ✅ Complete | KEEP |
| Mute/Unmute | Both | ❌ Neither implements | ❌ Missing | REIMPLEMENT |
| Archive/Unarchive | Green-API | ❌ Not implemented | ❌ Missing | REIMPLEMENT |
| **Users** | | | | |
| Get Profile | Both | PyMax: `SelfService.get_profile()`; Green-API: `account.getAccountSettings()` | ✅ Both | MERGE |
| Update Profile | PyMax | `SelfService.update_profile()` | ✅ Complete | KEEP |
| Get User by ID | Both | PyMax: `get_user()`; Green-API: `serviceMethods.getContactInfo()` | ✅ Both | MERGE |
| Search by Phone | Both | PyMax: `search_by_phone()`; Green-API: `serviceMethods.checkAccount()` | ✅ Both | MERGE |
| Get Contacts | Both | PyMax: `fetch_users()`; Green-API: `serviceMethods.getContacts()` | ✅ Both | MERGE |
| Add/Remove Contact | PyMax | `add_contact()`/`remove_contact()` | ✅ Complete | KEEP |
| Import Contacts | PyMax | `import_contacts()` | ✅ Complete | KEEP |
| Get Sessions | PyMax | `get_sessions()` | ✅ Complete | KEEP |
| Close Sessions | PyMax | `close_session()` | ✅ Complete | KEEP |
| Presence/Status | PyMax | `PresenceEvent` via dispatcher | ✅ Complete | KEEP |
| Avatar | Both | PyMax: `change_profile_photo()`; Green-API: `account.setProfilePicture()` | ✅ Both | MERGE |
| **Files/Media** | | | | |
| Upload Photo | PyMax | `UploadService.upload_photo()` (multipart, validation) | ✅ Complete | KEEP |
| Upload Video | PyMax | `UploadService.upload_video()` (chunked, waiter) | ✅ Complete | KEEP |
| Upload Voice | PyMax | `UploadService.upload_voice()` (chunked, waiter) | ✅ Complete | KEEP |
| Upload File | Both | PyMax: chunked + waiter; Green-API: raw binary in memory | ✅ PyMax | KEEP |
| Download File | Both | PyMax: `get_file_by_id()`; Green-API: `receiving.downloadFile()` | ✅ Both | MERGE |
| Streaming | PyMax | `BaseFile.iter_chunks()` async generator | ✅ Complete | KEEP |
| Large Files | PyMax | Chunked upload (1MB), 15min timeout | ✅ Complete | KEEP |
| Progress Callbacks | Both | ❌ Neither implements | ❌ Missing | REIMPLEMENT |
| MIME Detection | PyMax | `Photo.validate_photo()` (ext + MIME) | ✅ Complete | KEEP |
| Thumbnail/Preview | PyMax | VideoNote returns `thumbhash` | ✅ Complete | KEEP |
| **Events** | | | | |
| Event Types | PyMax | 11 types (message, chat, user, reaction, typing, presence, media ready) | ✅ Complete | KEEP |
| Event Types | Green-API | 6 webhook types (incoming/outgoing, status, state, call) | ✅ Works | MERGE |
| Long Polling | Green-API | `webhooks.startReceivingNotifications()` (blocking) | ⚠️ Blocking only | REIMPLEMENT |
| WebSocket Events | PyMax | Native WebSocket + dispatcher | ✅ Complete | KEEP |
| TCP Events | PyMax | Native TCP + dispatcher | ✅ Complete | KEEP |
| Router/Filter System | PyMax | Hierarchical routers, sync/async filters, error scopes | ✅ Complete | KEEP |
| Decorator API | PyMax | `@router.on_message()`, `@router.on_start()`, etc. | ✅ Complete | KEEP |
| Raw Events | PyMax | `on_raw()` receives `InboundFrame` | ✅ Complete | KEEP |
| Startup Handlers | PyMax | `on_start()` handlers | ✅ Complete | KEEP |
| Error Handlers | PyMax | `@router.on_error(GLOBAL/LOCAL)` | ✅ Complete | KEEP |
| Disconnect Handlers | PyMax | `on_disconnect()` | ✅ Complete | KEEP |
| **Error Handling** | | | | |
| Exception Hierarchy | PyMax | `PyMaxError` → `ApiError`, `UploadError` | ✅ Complete | KEEP |
| Exception Hierarchy | Green-API | Single `GreenAPIError` | ⚠️ Basic | REIMPLEMENT |
| Error Context | PyMax | `ErrorContext` with client, event, handler, router | ✅ Complete | KEEP |
| Rate Limit Handling | Green-API | Retry on 429 only (fixed backoff) | ⚠️ Limited | IMPROVE |
| Rate Limit Handling | PyMax | No built-in | ❌ Missing | REIMPLEMENT |
| Retry Logic | Green-API | urllib3 Retry (POST retries!) | ❌ Broken | REIMPLEMENT |
| Retry Logic | PyMax | Connection-level reconnect only | ⚠️ Partial | IMPROVE |
| **Models/Types** | | | | |
| Pydantic Models | PyMax | Full domain models (`CamelModel` with camelCase aliases) | ✅ Complete | KEEP |
| Raw Dict | Green-API | All responses as raw `dict` | ❌ No types | REIMPLEMENT |
| Attachment Types | PyMax | Discriminated unions (Photo, Video, File, Voice, etc.) | ✅ Complete | KEEP |
| Extra Fields Allowed | PyMax | `extra="allow"` on all models | ✅ Complete | KEEP |
| **Configuration** | | | | |
| Constructor Config | Both | Both use constructor parameters | ✅ Both | MERGE |
| Config File/Env | Both | ❌ Neither supports | ❌ Missing | REIMPLEMENT |
| Logging | Both | Both have logging (PyMax: pretty colors; Green-API: basic) | ✅ Both | MERGE |
| **Testing** | | | | |
| Unit Tests | PyMax | Comprehensive mocks, fixtures, service tests | ✅ Complete | KEEP |
| Unit Tests | Green-API | Single test file, basic mocks | ⚠️ Minimal | IMPROVE |
| Integration Tests | Both | ❌ Neither has real integration tests | ❌ Missing | REIMPLEMENT |
| Fake Transport | PyMax | `FakeApp`, `FakeStore`, `FakeDispatcher` | ✅ Complete | KEEP |
| **Documentation** | | | | |
| README | Both | Both have comprehensive README | ✅ Both | MERGE |
| Sphinx Docs | PyMax | Full Sphinx (12+ pages) | ✅ Complete | KEEP |
| Docstrings | Both | Both have good docstrings | ✅ Both | MERGE |
| Examples | Both | Both have example scripts | ✅ Both | MERGE |
| Migration Guide | Both | ❌ Neither has | ❌ Missing | REIMPLEMENT |
| **Advanced** | | | | |
| Fingerprinting | PyMax | SHA256 device attestation for TCP | ✅ Complete | KEEP |
| Version Catalog | PyMax | Android version → fingerprint mapping | ✅ Complete | KEEP |
| Telemetry | PyMax | Navigation + event telemetry | ✅ Complete | KEEP |
| Markdown Formatting | PyMax | `Formatter` with element parsing | ✅ Complete | KEEP |
| Webhook Server | Both | ❌ Neither implements | ❌ Missing | REIMPLEMENT |
| Broadcast Lists | Green-API | ❌ Not implemented | ❌ Missing | REIMPLEMENT |
| Message Templates | Green-API | ❌ Not implemented | ❌ Missing | REIMPLEMENT |