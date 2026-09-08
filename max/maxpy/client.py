from __future__ import annotations

import asyncio
import time
from typing import Any, Optional, Callable, Awaitable
from pathlib import Path
from .exceptions import ConnectionError, APIError

from .config import MaxConfig, TransportConfig, AuthConfig, SessionConfig, create_config
from .transport import TransportFactory
from .enums import TransportType
from .transport.tcp import TCPTransport
from .transport.websocket import WebSocketTransport
from .transport.rest import RESTTransport
from .auth import (
    AuthFlow,
    AuthService,
    RESTAuthFlow,
    SmsAuthFlow,
    QrAuthFlow,
    SessionTokenAuthFlow,
    ConsoleSmsCodeProvider,
    ConsoleQrHandler,
    ConsolePasswordProvider,
)
from .session import SessionManager, SQLiteStore, InMemoryStore, SessionInfo
from .connection import ConnectionManager
from .dispatch import Dispatcher, Router
from .api import ApiFacade
from .files import FileService
from .utils import configure_logging, get_logger, FingerprintGenerator
from .types import Message, Chat, User
from .enums import TransportType as TransportTypeEnum, AuthType, ConnectionState
from .exceptions import (
    MaxError,
    AuthError,
    SessionExpiredError,
    ConfigError,
    ConnectionError,
    wrap_error,
)

logger = get_logger("client")


class MaxClient:
    """Main MAX client - unified interface for all transports."""

    def __init__(
        self,
        config: MaxConfig | None = None,
        *,
        transport: TransportTypeEnum | str = TransportTypeEnum.TCP,
        phone: str | None = None,
        token: str | None = None,
        id_instance: int | None = None,
        api_token_instance: str | None = None,
        session_name: str = "default",
        persist_session: bool = True,
        work_dir: str | Path | None = None,
        sms_code_provider: Any | None = None,
        password_provider: Any | None = None,
        qr_handler: Any | None = None,
        reconnect: bool = True,
        reconnect_delay: float = 1.0,
        request_timeout: float = 30.0,
        log_level: str = "INFO",
        **kwargs,
    ):
        """
        Initialize MAX client.

        Args:
            config: Full MaxConfig object (takes precedence over other args)
            transport: Transport type ("tcp", "websocket", "rest")
            phone: Phone number for SMS auth (TCP)
            token: Session token (TCP/WS) or instance token (REST)
            id_instance: Green-API instance ID (REST)
            api_token_instance: Green-API API token (REST)
            session_name: Session name for persistence
            persist_session: Whether to persist session to disk
            work_dir: Working directory for session storage
            sms_code_provider: Custom SMS code provider
            password_provider: Custom 2FA password provider
            qr_handler: Custom QR code handler
            reconnect: Enable auto-reconnect
            reconnect_delay: Initial reconnect delay (seconds)
            request_timeout: Request timeout (seconds)
            log_level: Logging level
        """
        # Build config
        if config is None:
            config = create_config(
                transport=transport,
                phone=phone,
                token=token,
                id_instance=id_instance,
                api_token_instance=api_token_instance,
                session_name=session_name,
                persist_session=persist_session,
                reconnect=reconnect,
                reconnect_delay=reconnect_delay,
                request_timeout=request_timeout,
            )
            config.logging.level = log_level

        self.config = config
        self._started = False
        self._closed = False

        # Setup logging
        configure_logging(
            level=config.logging.level,
            format=config.logging.format,
            use_colors=config.logging.colors,
        )

        # Create transport
        self.transport = TransportFactory.create(config.transport)

        # Set REST credentials if needed
        if isinstance(self.transport, RESTTransport):
            if config.auth.type == AuthType.INSTANCE_TOKEN:
                self.transport.set_credentials(config.auth.id_instance, config.auth.api_token_instance)

        # Create auth flow
        self.auth_flow = self._create_auth_flow(config.auth)

        # Set auth providers
        self._setup_auth_providers(
            sms_code_provider,
            password_provider,
            qr_handler,
        )

        # Create session store
        work_dir = Path(work_dir) if work_dir else Path(config.session.path)
        if config.session.persist:
            self.session_store = SQLiteStore(str(work_dir / "sessions.db"))
        else:
            self.session_store = InMemoryStore()

        self.session_manager = SessionManager(self.session_store)

        # Create connection manager
        self.connection = ConnectionManager(
            transport=self.transport,
            reconnect=config.connection.reconnect,
            reconnect_delay=config.connection.reconnect_delay,
            reconnect_max_delay=config.connection.reconnect_max_delay,
            reconnect_attempts=config.connection.reconnect_attempts,
            ping_interval=config.connection.ping_interval,
            request_timeout=config.connection.request_timeout,
        )

        # Set up event handling
        self.connection.set_event_handler(self._on_event)
        self.connection.set_state_change_handler(self._on_state_change)
        self.connection.set_disconnect_handler(self._on_disconnect)

        # Create dispatcher
        self.dispatcher = Dispatcher()
        self.dispatcher.bind_client(self)
        self.router = self.dispatcher.router

        # Create API facade
        self.api = ApiFacade(self)
        self.messages = self.api.messages
        self.chats = self.api.chats
        self.users = self.api.users
        self.files = self.api.files
        self.self = self.api.self
        self.bots = self.api.bots
        self.auth = self.api.auth

        # Fingerprint generator
        self.fingerprint_generator = FingerprintGenerator(
            android_version=config.fingerprint.android_version,
            android_build=config.fingerprint.android_build,
            sdk_version=config.fingerprint.sdk_version,
            locale=config.fingerprint.locale,
            timezone=config.fingerprint.timezone,
        )

        # Internal state
        self._user: User | None = None
        _token: str | None = None
        self._event_handlers: dict[str, list[Callable]] = {}
        self._startup_tasks: list[Awaitable] = []

    def _create_auth_flow(self, auth_config: AuthConfig) -> AuthFlow:
        """Create appropriate auth flow based on config."""
        if auth_config.type == AuthType.INSTANCE_TOKEN:
            return RESTAuthFlow(auth_config)
        elif auth_config.type == AuthType.SESSION_TOKEN:
            return SessionTokenAuthFlow(auth_config)
        elif auth_config.type == AuthType.SMS:
            return SmsAuthFlow(auth_config)
        elif auth_config.type == AuthType.QR:
            return QrAuthFlow(auth_config)
        else:
            raise ConfigError(f"Unknown auth type: {auth_config.type}")

    def _setup_auth_providers(
        self,
        sms_provider: Any | None,
        password_provider: Any | None,
        qr_handler: Any | None,
    ) -> None:
        """Set up auth providers."""
        if isinstance(self.auth_flow, SmsAuthFlow):
            if sms_provider:
                self.auth_flow.set_sms_provider(sms_provider)
            elif self.config.auth.phone:
                self.auth_flow.set_sms_provider(ConsoleSmsCodeProvider())

            if password_provider:
                self.auth_flow.set_password_provider(password_provider)
            else:
                self.auth_flow.set_password_provider(ConsolePasswordProvider())

        elif isinstance(self.auth_flow, QrAuthFlow):
            if qr_handler:
                self.auth_flow.set_qr_handler(qr_handler)
            else:
                self.auth_flow.set_qr_handler(ConsoleQrHandler())

            if password_provider:
                self.auth_flow.set_password_provider(password_provider)
            else:
                self.auth_flow.set_password_provider(ConsolePasswordProvider())

    async def start(self) -> None:
        """Start the client - connect, authenticate, start event loop."""
        if self._started:
            return

        logger.info("Starting MaxClient...")

        # Try to restore session
        await self._restore_session()

        # Connect
        logger.info("Connecting transport...")
        await self.connection.connect()
        logger.info(f"Transport connected: {self.transport.is_connected if hasattr(self.transport, 'is_connected') else 'N/A'}")
        logger.info(f"Transport reader: {self.transport._reader if hasattr(self.transport, '_reader') else 'N/A'}")

        # Authenticate
        logger.info("Starting authentication...")
        await self._authenticate()

        # Start connection manager
        await self.connection.start()

        # Emit startup
        await self.dispatcher.emit_start()

        self._started = True
        logger.info("MaxClient started successfully")

    async def _restore_session(self) -> None:
        """Restore session from store."""
        session = await self.session_manager.load_session(
            device_id=self.config.session.device_id,
            phone=self.config.auth.phone,
        )

        if session:
            logger.info(f"Restored session: {session.token[:8]}...")
            # Update config with session data
            if session.mt_instance_id:
                self.config.auth.token = session.token
                # Create session token auth flow
                self.auth_flow = SessionTokenAuthFlow(self.config.auth)
            self._token = session.token

    async def _authenticate(self) -> None:
        """Perform authentication."""
        self.connection._set_state(ConnectionState.AUTHENTICATING)

        # Set fingerprint for TCP
        if isinstance(self.transport, TCPTransport):
            fingerprint = self.fingerprint_generator.generate(self.config.session.device_id)
            self.transport.set_fingerprint(fingerprint)

            # Do handshake first (required before auth)
            await self._do_handshake()

        # Perform auth
        auth_service = AuthService(self.transport, self.auth_flow)
        result = await auth_service.login()

        if not result.success:
            raise AuthError(result.error or "Authentication failed")

        self._token = result.token
        self._user = result.user

        # Save session
        if self.config.session.persist and result.token:
            session_info = SessionInfo(
                token=result.token,
                device_id=self.config.session.device_id or self.fingerprint_generator._generate_device_id(),
                phone=self.config.auth.phone,
                mt_instance_id=self.config.session.mt_instance_id,
                user_agent=self.fingerprint_generator.get_user_agent(),
            )
            await self.session_manager.save_session(session_info)

        logger.info(f"Authenticated as {result.user.get_full_name() if result.user else 'unknown'}")

    async def _do_handshake(self) -> None:
        """Perform initial handshake for TCP transport."""
        from maxpy.transport.tcp import TCPTransport, TCPOpcode
        
        if not isinstance(self.transport, TCPTransport):
            return
            
        device_id = self.config.session.device_id or self.fingerprint_generator._generate_device_id()
        
        # Build user agent payload (matches PyMax MobileUserAgentPayload)
        user_agent = {
            "deviceType": "ANDROID",
            "appVersion": "26.25.0",
            "osVersion": "14",
            "timezone": "UTC",
            "screen": "1080x2400",
            "pushDeviceType": "GCM",
            "arch": "arm64",
            "locale": "en_US",
            "buildNumber": 100,
            "deviceName": "Pixel 8",
            "deviceLocale": "en_US",
            "release": 34,
        }
        
        # Send handshake (SESSION_INIT with REQUEST cmd)
        seq = await self.transport.send_packet(
            cmd=0,  # REQUEST
            opcode=TCPOpcode.SESSION_INIT,
            payload={
                "userAgent": user_agent,
                "deviceId": device_id,
            },
        )

        # Wait for handshake response
        result = await self.transport.receive()
        if result is None:
            raise ConnectionError("Handshake failed: connection closed (no response)")
        header, payload = result
        if header.opcode == 3:  # ERROR
            from maxpy.exceptions import AuthError
            raise AuthError(payload.get("error", "Handshake failed"))

        logger.debug(f"Handshake successful: {payload}")

    async def _on_event(self, event: Any) -> None:
        """Handle incoming event."""
        await self.dispatcher.dispatch(event)

    async def _on_state_change(self, old_state: ConnectionState, new_state: ConnectionState) -> None:
        """Handle connection state change."""
        logger.debug(f"Connection state: {old_state.value} -> {new_state.value}")

        if new_state == ConnectionState.CONNECTED:
            # Re-emit start on reconnect
            await self.dispatcher.emit_start()

    async def _on_disconnect(self, will_reconnect: bool) -> None:
        """Handle disconnect."""
        await self.dispatcher.emit_disconnect(None, will_reconnect, self.config.connection.reconnect_delay)

    async def stop(self) -> None:
        """Stop the client gracefully."""
        if self._closed:
            return

        logger.info("Stopping MaxClient...")
        self._closed = True

        await self.connection.stop()
        await self.session_manager.close()

        self._started = False
        logger.info("MaxClient stopped")

    async def close(self) -> None:
        """Alias for stop()."""
        await self.stop()

    async def relogin(self) -> None:
        """Force re-authentication."""
        logger.info("Relogging...")
        if self._token:
            await self.session_manager.delete_session(self._token)
        await self._authenticate()

    def on_event(self, event_type: str) -> Callable:
        """Register generic event handler."""
        def decorator(func: Callable) -> Callable:
            if event_type not in self._event_handlers:
                self._event_handlers[event_type] = []
            self._event_handlers[event_type].append(func)
            return func
        return decorator

    def on_message(self, *filters) -> Callable:
        """Decorator for message handlers."""
        return self.router.on_message(*filters)

    def on_message_edit(self, *filters) -> Callable:
        """Decorator for message edit handlers."""
        return self.router.on_message_edit(*filters)

    def on_message_delete(self, *filters) -> Callable:
        """Decorator for message delete handlers."""
        return self.router.on_message_delete(*filters)

    def on_message_read(self, *filters) -> Callable:
        """Decorator for message read handlers."""
        return self.router.on_message_read(*filters)

    def on_typing(self, *filters) -> Callable:
        """Decorator for typing handlers."""
        return self.router.on_typing(*filters)

    def on_presence(self, *filters) -> Callable:
        """Decorator for presence handlers."""
        return self.router.on_presence(*filters)

    def on_reaction_update(self, *filters) -> Callable:
        """Decorator for reaction handlers."""
        return self.router.on_reaction_update(*filters)

    def on_chat_update(self, *filters) -> Callable:
        """Decorator for chat update handlers."""
        return self.router.on_chat_update(*filters)

    def on_raw(self, *filters) -> Callable:
        """Decorator for raw event handlers."""
        return self.router.on_raw(*filters)

    def on_start(self) -> Callable:
        """Decorator for startup handlers."""
        return self.router.on_start()

    def on_error(self, scope: str = "local") -> Callable:
        """Decorator for error handlers."""
        from .enums import ErrorScope
        return self.router.on_error(ErrorScope(scope))

    def on_disconnect(self) -> Callable:
        """Decorator for disconnect handlers."""
        return self.router.on_disconnect()

    def include_router(self, router: Router) -> None:
        """Include a router."""
        self.dispatcher.include_router(router)

    async def _send_request(self, method: str, request: Any) -> Any:
        """Send request via appropriate transport."""
        if isinstance(self.transport, RESTTransport):
            return await self._send_request_rest(method, request)
        elif isinstance(self.transport, TCPTransport):
            return await self._send_request_tcp(method, request)
        elif isinstance(self.transport, WebSocketTransport):
            return await self._send_request_ws(method, request)
        else:
            raise NotImplementedError(f"Transport {type(self.transport)} not supported")

    async def _send_request_rest(self, method: str, request: Any) -> Any:
        """Send request via REST transport (Green-API)."""
        # Map method to Green-API endpoint
        endpoint_map = {
            "send_message": ("POST", "waInstance{{idInstance}}/sendMessage/{{token}}", False),
            "edit_message": ("POST", "waInstance{{idInstance}}/editMessage/{{token}}", False),
            "delete_message": ("DELETE", "waInstance{{idInstance}}/deleteMessage/{{token}}", False),
            "forward_message": ("POST", "waInstance{{idInstance}}/forwardMessages/{{token}}", False),
            "get_history": ("POST", "waInstance{{idInstance}}/getChatHistory/{{token}}", False),
            "get_messages": ("POST", "waInstance{{idInstance}}/getMessage/{{token}}", False),
            "pin_message": ("POST", "waInstance{{idInstance}}/pinMessage/{{token}}", False),
            "unpin_message": ("POST", "waInstance{{idInstance}}/unpinMessage/{{token}}", False),
            "add_reaction": ("POST", "waInstance{{idInstance}}/addReaction/{{token}}", False),
            "remove_reaction": ("POST", "waInstance{{idInstance}}/removeReaction/{{token}}", False),
            "get_reactions": ("POST", "waInstance{{idInstance}}/getReactions/{{token}}", False),
            "read_message": ("POST", "waInstance{{idInstance}}/readChat/{{token}}", False),
            "vote_poll": ("POST", "waInstance{{idInstance}}/votePoll/{{token}}", False),
            "get_poll_state": ("POST", "waInstance{{idInstance}}/getPollState/{{token}}", False),
            "get_chat": ("GET", "waInstance{{idInstance}}/getChat/{{token}}", False),
            "get_chats": ("GET", "waInstance{{idInstance}}/getChats/{{token}}", False),
            "fetch_chats": ("GET", "waInstance{{idInstance}}/getChats/{{token}}", False),
            "create_group": ("POST", "waInstance{{idInstance}}/createGroup/{{token}}", False),
            "invite_to_group": ("POST", "waInstance{{idInstance}}/addGroupParticipant/{{token}}", False),
            "remove_from_group": ("POST", "waInstance{{idInstance}}/removeGroupParticipant/{{token}}", False),
            "change_group_settings": ("POST", "waInstance{{idInstance}}/updateGroupSettings/{{token}}", False),
            "change_group_profile": ("POST", "waInstance{{idInstance}}/setGroupPicture/{{token}}", True),  # media
            "join_group": ("POST", "waInstance{{idInstance}}/joinGroup/{{token}}", False),
            "resolve_link": ("POST", "waInstance{{idInstance}}/getInviteLinkInfo/{{token}}", False),
            "rework_invite_link": ("POST", "waInstance{{idInstance}}/reworkInviteLink/{{token}}", False),
            "get_members": ("POST", "waInstance{{idInstance}}/getGroupData/{{token}}", False),
            "leave_group": ("POST", "waInstance{{idInstance}}/leaveGroup/{{token}}", False),
            "delete_chat": ("POST", "waInstance{{idInstance}}/deleteChat/{{token}}", False),
            "add_admin": ("POST", "waInstance{{idInstance}}/setGroupAdmin/{{token}}", False),
            "remove_admin": ("POST", "waInstance{{idInstance}}/removeAdmin/{{token}}", False),
            "get_join_requests": ("POST", "waInstance{{idInstance}}/getJoinRequests/{{token}}", False),
            "confirm_join_requests": ("POST", "waInstance{{idInstance}}/confirmJoinRequests/{{token}}", False),
            "decline_join_requests": ("POST", "waInstance{{idInstance}}/declineJoinRequests/{{token}}", False),
            "get_user": ("POST", "waInstance{{idInstance}}/getContactInfo/{{token}}", False),
            "get_users": ("POST", "waInstance{{idInstance}}/getContacts/{{token}}", False),
            "search_by_phone": ("POST", "waInstance{{idInstance}}/checkAccount/{{token}}", False),
            "get_sessions": ("GET", "waInstance{{idInstance}}/getSessions/{{token}}", False),
            "close_session": ("POST", "waInstance{{idInstance}}/closeSession/{{token}}", False),
            "close_all_sessions": ("POST", "waInstance{{idInstance}}/logoutAll/{{token}}", False),
            "add_contact": ("POST", "waInstance{{idInstance}}/addContact/{{token}}", False),
            "remove_contact": ("POST", "waInstance{{idInstance}}/removeContact/{{token}}", False),
            "import_contacts": ("POST", "waInstance{{idInstance}}/importContacts/{{token}}", False),
            "get_profile": ("GET", "waInstance{{idInstance}}/getAccountSettings/{{token}}", False),
            "update_profile": ("POST", "waInstance{{idInstance}}/setAccountSettings/{{token}}", False),
            "change_profile_photo": ("POST", "waInstance{{idInstance}}/setProfilePicture/{{token}}", True),
            "get_folders": ("GET", "waInstance{{idInstance}}/getFolders/{{token}}", False),
            "update_folder": ("POST", "waInstance{{idInstance}}/updateFolder/{{token}}", False),
            "delete_folder": ("POST", "waInstance{{idInstance}}/deleteFolder/{{token}}", False),
            "get_privacy": ("GET", "waInstance{{idInstance}}/getPrivacy/{{token}}", False),
            "set_privacy": ("POST", "waInstance{{idInstance}}/setPrivacy/{{token}}", False),
            "logout": ("GET", "waInstance{{idInstance}}/logout/{{token}}", False),
            "set_2fa": ("POST", "waInstance{{idInstance}}/set2FA/{{token}}", False),
            "remove_2fa": ("POST", "waInstance{{idInstance}}/remove2FA/{{token}}", False),
            "change_password": ("POST", "waInstance{{idInstance}}/changePassword/{{token}}", False),
            "download_file": ("POST", "waInstance{{idInstance}}/downloadFile/{{token}}", False),
            "download_video": ("POST", "waInstance{{idInstance}}/downloadVideo/{{token}}", False),
            "bot_get_info": ("GET", "waInstance{{idInstance}}/getBotInfo/{{token}}", False),
            "bot_send": ("POST", "waInstance{{idInstance}}/sendBotMessage/{{token}}", False),
        }

        if method not in endpoint_map:
            raise NotImplementedError(f"Method {method} not implemented for REST transport")

        http_method, endpoint, is_media = endpoint_map[method]

        # Convert request to dict
        if hasattr(request, "model_dump"):
            payload = request.model_dump(exclude_none=True)
        elif isinstance(request, dict):
            payload = request
        else:
            payload = {}

        # Handle file uploads (multipart)
        files = None
        json_data = payload

        if method in ("change_group_profile", "change_profile_photo") and "photo" in payload:
            # These would need multipart handling
            pass

        return await self.transport.request(
            method=http_method,
            endpoint=endpoint,
            json_data=json_data,
            is_media=is_media,
        )

    async def _send_request_tcp(self, method: str, request: Any) -> Any:
        """Send request via TCP transport (internal API)."""
        from .transport.tcp import TCPCommand, TCPOpcode

        method_map = {
            "send_message": TCPCommand.MSG_SEND,
            "edit_message": TCPCommand.MSG_EDIT,
            "delete_message": TCPCommand.MSG_DELETE,
            "forward_message": TCPCommand.MSG_SEND,  # Forward uses send with forward_from
            "get_history": TCPCommand.CHAT_HISTORY,
            "get_messages": TCPCommand.MSG_GET,
            "pin_message": TCPCommand.MSG_SEND,  # Pin via update
            "unpin_message": TCPCommand.MSG_SEND,
            "add_reaction": TCPCommand.MSG_REACTION,
            "remove_reaction": TCPCommand.MSG_CANCEL_REACTION,
            "get_reactions": TCPCommand.MSG_GET_REACTIONS,
            "read_message": TCPCommand.CHAT_MARK,
            "vote_poll": TCPCommand.SEND_VOTE,
            "get_poll_state": TCPCommand.MSG_GET,
            "get_chat": TCPCommand.CHAT_INFO,
            "get_chats": TCPCommand.CHATS_LIST,
            "fetch_chats": TCPCommand.CHATS_LIST,
            "create_group": TCPCommand.CHAT_JOIN,  # Create group via join with params
            "invite_to_group": TCPCommand.CHAT_MEMBERS_UPDATE,
            "remove_from_group": TCPCommand.CHAT_MEMBERS_UPDATE,
            "change_group_settings": TCPCommand.CHAT_UPDATE,
            "change_group_profile": TCPCommand.CHAT_UPDATE,
            "join_group": TCPCommand.CHAT_JOIN,
            "resolve_link": TCPCommand.LINK_INFO,
            "rework_invite_link": TCPCommand.CHAT_UPDATE,
            "get_members": TCPCommand.CHAT_MEMBERS,
            "leave_group": TCPCommand.CHAT_LEAVE,
            "delete_chat": TCPCommand.CHAT_DELETE,
            "add_admin": TCPCommand.CHAT_MEMBERS_UPDATE,
            "remove_admin": TCPCommand.CHAT_MEMBERS_UPDATE,
            "get_join_requests": TCPCommand.CHAT_MEMBERS_UPDATE,
            "confirm_join_requests": TCPCommand.CHAT_MEMBERS_UPDATE,
            "decline_join_requests": TCPCommand.CHAT_MEMBERS_UPDATE,
            "get_user": TCPCommand.CONTACT_INFO,
            "get_users": TCPCommand.CONTACT_INFO,
            "search_by_phone": TCPCommand.CONTACT_INFO_BY_PHONE,
            "get_sessions": TCPCommand.SESSIONS_INFO,
            "close_session": TCPCommand.SESSIONS_CLOSE,
            "close_all_sessions": TCPCommand.SESSIONS_CLOSE,
            "add_contact": TCPCommand.CONTACT_UPDATE,
            "remove_contact": TCPCommand.CONTACT_UPDATE,
            "import_contacts": TCPCommand.SYNC,
            "get_profile": TCPCommand.PROFILE,
            "update_profile": TCPCommand.PROFILE,
            "change_profile_photo": TCPCommand.PHOTO_UPLOAD,
            "get_folders": TCPCommand.FOLDERS_GET,
            "update_folder": TCPCommand.FOLDERS_UPDATE,
            "delete_folder": TCPCommand.FOLDERS_DELETE,
            "get_privacy": TCPCommand.CONFIG,
            "set_privacy": TCPCommand.CONFIG,
            "logout": TCPCommand.LOGOUT,
            "download_file": TCPCommand.FILE_DOWNLOAD,
            "download_video": TCPCommand.VIDEO_PLAY,
        }

        if method not in method_map:
            raise NotImplementedError(f"Method {method} not implemented for TCP transport")

        command = method_map[method]

        # Convert request to payload
        if hasattr(request, "model_dump"):
            payload = request.model_dump(exclude_none=True, by_alias=True)
        elif isinstance(request, dict):
            payload = request
        else:
            payload = {}

        # Add token to payload for authenticated requests
        if self._token and method not in ("logout",):
            payload["token"] = self._token

        header, response = await self.connection.send_request(
            command=command,
            payload=payload,
        )

        if header.opcode == TCPOpcode.ERROR:
            from .exceptions import APIError
            error_msg = response.get("error", "Unknown error")
            error_code = response.get("errorCode") or response.get("code")
            raise APIError(error_msg, error_code=error_code, response_data=response, transport="tcp")

        return response

    async def _send_request_ws(self, method: str, request: Any) -> Any:
        """Send request via WebSocket transport (internal API)."""
        from .transport.websocket import WSOpcode

        method_map = {
            "send_message": WSOpcode.MSG_SEND,
            "edit_message": WSOpcode.MSG_EDIT,
            "delete_message": WSOpcode.MSG_DELETE,
            "forward_message": WSOpcode.MSG_SEND,
            "get_history": WSOpcode.CHAT_HISTORY,
            "get_messages": WSOpcode.MSG_GET,
            "pin_message": WSOpcode.MSG_SEND,
            "unpin_message": WSOpcode.MSG_SEND,
            "add_reaction": WSOpcode.MSG_REACTION,
            "remove_reaction": WSOpcode.MSG_CANCEL_REACTION,
            "get_reactions": WSOpcode.MSG_GET_REACTIONS,
            "read_message": WSOpcode.CHAT_MARK,
            "vote_poll": WSOpcode.SEND_VOTE,
            "get_poll_state": WSOpcode.MSG_GET,
            "get_chat": WSOpcode.CHAT_INFO,
            "get_chats": WSOpcode.CHATS_LIST,
            "fetch_chats": WSOpcode.CHATS_LIST,
            "create_group": WSOpcode.CHAT_JOIN,
            "invite_to_group": WSOpcode.CHAT_MEMBERS_UPDATE,
            "remove_from_group": WSOpcode.CHAT_MEMBERS_UPDATE,
            "change_group_settings": WSOpcode.CHAT_UPDATE,
            "change_group_profile": WSOpcode.CHAT_UPDATE,
            "join_group": WSOpcode.CHAT_JOIN,
            "resolve_link": WSOpcode.LINK_INFO,
            "rework_invite_link": WSOpcode.CHAT_UPDATE,
            "get_members": WSOpcode.CHAT_MEMBERS,
            "leave_group": WSOpcode.CHAT_LEAVE,
            "delete_chat": WSOpcode.CHAT_DELETE,
            "add_admin": WSOpcode.CHAT_MEMBERS_UPDATE,
            "remove_admin": WSOpcode.CHAT_MEMBERS_UPDATE,
            "get_join_requests": WSOpcode.CHAT_MEMBERS_UPDATE,
            "confirm_join_requests": WSOpcode.CHAT_MEMBERS_UPDATE,
            "decline_join_requests": WSOpcode.CHAT_MEMBERS_UPDATE,
            "get_user": WSOpcode.CONTACT_INFO,
            "get_users": WSOpcode.CONTACT_INFO,
            "search_by_phone": WSOpcode.CONTACT_INFO_BY_PHONE,
            "get_sessions": WSOpcode.SESSIONS_INFO,
            "close_session": WSOpcode.SESSIONS_CLOSE,
            "close_all_sessions": WSOpcode.SESSIONS_CLOSE,
            "add_contact": WSOpcode.CONTACT_UPDATE,
            "remove_contact": WSOpcode.CONTACT_UPDATE,
            "import_contacts": WSOpcode.SYNC,
            "get_profile": WSOpcode.PROFILE,
            "update_profile": WSOpcode.PROFILE,
            "change_profile_photo": WSOpcode.PHOTO_UPLOAD,
            "get_folders": WSOpcode.FOLDERS_GET,
            "update_folder": WSOpcode.FOLDERS_UPDATE,
            "delete_folder": WSOpcode.FOLDERS_DELETE,
            "get_privacy": WSOpcode.CONFIG,
            "set_privacy": WSOpcode.CONFIG,
            "logout": WSOpcode.LOGOUT,
            "download_file": WSOpcode.FILE_DOWNLOAD,
            "download_video": WSOpcode.VIDEO_PLAY,
        }

        if method not in method_map:
            raise NotImplementedError(f"Method {method} not implemented for WebSocket transport")

        opcode = method_map[method]

        # Convert request to payload
        if hasattr(request, "model_dump"):
            payload = request.model_dump(exclude_none=True, by_alias=True)
        elif isinstance(request, dict):
            payload = request
        else:
            payload = {}

        # Add token
        if self._token and method not in ("logout",):
            payload["token"] = self._token

        # For WebSocket, we need to send request and wait for response
        # This requires the connection manager to handle WS request/response
        request_id = str(id(payload))
        await self.transport.send_request(opcode, payload, request_id)

        # Wait for response (simplified - would need proper future tracking)
        # For now, we'll use the connection's pending requests
        future = await self.connection._pending.add(int(request_id), 0)
        try:
            frame = await asyncio.wait_for(future, timeout=self.config.connection.request_timeout)
            if frame.payload.get("error"):
                from .exceptions import APIError
                raise APIError(frame.payload["error"], response_data=frame.payload, transport="websocket")
            return frame.payload
        except asyncio.TimeoutError:
            raise ConnectionError("Request timeout", transport="websocket")

    async def _upload_file(self, file: Any, upload_type: str, **kwargs) -> Any:
        """Upload file via appropriate transport."""
        return await self.files.upload(file, upload_type, **kwargs)

    @property
    def user(self) -> User | None:
        """Get current user."""
        return self._user

    @property
    def token(self) -> str | None:
        """Get current session token."""
        return self._token

    @property
    def is_connected(self) -> bool:
        """Check if connected."""
        return self.connection.is_connected

    @property
    def is_started(self) -> bool:
        """Check if started."""
        return self._started and not self._closed

    def get_stats(self) -> dict[str, Any]:
        """Get client statistics."""
        return {
            "started": self._started,
            "connected": self.is_connected,
            "transport": self.transport.transport_type.value,
            "user": self._user.id if self._user else None,
            "connection": self.connection.get_stats(),
        }

    async def __aenter__(self) -> "MaxClient":
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.stop()


# Convenience function
async def create_client(
    transport: TransportTypeEnum | str = TransportTypeEnum.TCP,
    **kwargs,
) -> MaxClient:
    """Create and start client."""
    client = MaxClient(transport=transport, **kwargs)
    await client.start()
    return client