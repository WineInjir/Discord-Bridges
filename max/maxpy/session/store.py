from __future__ import annotations

import aiosqlite
import json
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Optional
from dataclasses import dataclass, asdict
from ..types.user import User, SyncState
from ..enums import DeviceType
from ..exceptions import ConfigError


@dataclass
class SessionInfo:
    """Stored session information."""

    token: str
    device_id: str
    phone: str | None = None
    mt_instance_id: str | None = None
    chats_sync: str | None = None
    contacts_sync: str | None = None
    drafts_sync: str | None = None
    presence_sync: str | None = None
    config_hash: str | None = None
    user_agent: dict[str, Any] | None = None
    created_at: float = 0
    updated_at: float = 0

    def __post_init__(self):
        if self.created_at == 0:
            self.created_at = time.time()
        if self.updated_at == 0:
            self.updated_at = time.time()

    def to_sync_state(self) -> SyncState:
        """Convert to SyncState for login."""
        return SyncState(
            chats=self.chats_sync,
            contacts=self.contacts_sync,
            drafts=self.drafts_sync,
            presence=self.presence_sync,
        )


class StoreProtocol(ABC):
    """Abstract session store protocol."""

    @abstractmethod
    async def load_session(self) -> Optional[SessionInfo]:
        """Load the most recent session."""
        pass

    @abstractmethod
    async def load_session_by_device(self, device_id: str) -> Optional[SessionInfo]:
        """Load session by device ID."""
        pass

    @abstractmethod
    async def load_session_by_phone(self, phone: str) -> Optional[SessionInfo]:
        """Load session by phone number."""
        pass

    @abstractmethod
    async def save_session(self, session: SessionInfo) -> None:
        """Save or update session."""
        pass

    @abstractmethod
    async def update_token(self, old_token: str, new_token: str) -> None:
        """Update session token."""
        pass

    @abstractmethod
    async def delete_session(self, token: str) -> None:
        """Delete session."""
        pass

    @abstractmethod
    async def close(self) -> None:
        """Close store."""
        pass


class SQLiteStore(StoreProtocol):
    """SQLite session store with auto-migration."""

    SCHEMA_VERSION = 3

    def __init__(self, path: str):
        self.path = Path(path).expanduser().resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._db: aiosqlite.Connection | None = None

    async def _get_db(self) -> aiosqlite.Connection:
        if self._db is None:
            self._db = await aiosqlite.connect(str(self.path))
            self._db.row_factory = aiosqlite.Row
            await self._init_schema()
        return self._db

    async def _init_schema(self) -> None:
        db = await self._get_db()

        # Create sessions table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                token TEXT PRIMARY KEY,
                device_id TEXT NOT NULL,
                phone TEXT,
                mt_instance_id TEXT,
                chats_sync TEXT,
                contacts_sync TEXT,
                drafts_sync TEXT,
                presence_sync TEXT,
                config_hash TEXT,
                user_agent TEXT,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            )
        """)

        # Create indexes
        await db.execute("CREATE INDEX IF NOT EXISTS idx_sessions_device ON sessions(device_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_sessions_phone ON sessions(phone)")

        # Migration: add missing columns
        columns = await self._get_columns(db, "sessions")
        migrations = [
            ("mt_instance_id", "TEXT"),
            ("config_hash", "TEXT"),
            ("user_agent", "TEXT"),
        ]
        for col_name, col_type in migrations:
            if col_name not in columns:
                await db.execute(f"ALTER TABLE sessions ADD COLUMN {col_name} {col_type}")

        # Set default config_hash for existing rows
        await db.execute("UPDATE sessions SET config_hash = 'default' WHERE config_hash IS NULL")

        await db.commit()

    async def _get_columns(self, db: aiosqlite.Connection, table: str) -> set[str]:
        cursor = await db.execute(f"PRAGMA table_info({table})")
        rows = await cursor.fetchall()
        return {row["name"] for row in rows}

    async def load_session(self) -> Optional[SessionInfo]:
        db = await self._get_db()
        cursor = await db.execute(
            "SELECT * FROM sessions ORDER BY updated_at DESC LIMIT 1"
        )
        row = await cursor.fetchone()
        return self._row_to_session(row) if row else None

    async def load_session_by_device(self, device_id: str) -> Optional[SessionInfo]:
        db = await self._get_db()
        cursor = await db.execute(
            "SELECT * FROM sessions WHERE device_id = ? ORDER BY updated_at DESC LIMIT 1",
            (device_id,),
        )
        row = await cursor.fetchone()
        return self._row_to_session(row) if row else None

    async def load_session_by_phone(self, phone: str) -> Optional[SessionInfo]:
        db = await self._get_db()
        cursor = await db.execute(
            "SELECT * FROM sessions WHERE phone = ? ORDER BY updated_at DESC LIMIT 1",
            (phone,),
        )
        row = await cursor.fetchone()
        return self._row_to_session(row) if row else None

    async def save_session(self, session: SessionInfo) -> None:
        db = await self._get_db()
        session.updated_at = time.time()

        await db.execute("""
            INSERT INTO sessions (
                token, device_id, phone, mt_instance_id,
                chats_sync, contacts_sync, drafts_sync, presence_sync,
                config_hash, user_agent, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(token) DO UPDATE SET
                device_id = excluded.device_id,
                phone = excluded.phone,
                mt_instance_id = excluded.mt_instance_id,
                chats_sync = excluded.chats_sync,
                contacts_sync = excluded.contacts_sync,
                drafts_sync = excluded.drafts_sync,
                presence_sync = excluded.presence_sync,
                config_hash = excluded.config_hash,
                user_agent = excluded.user_agent,
                updated_at = excluded.updated_at
        """, (
            session.token,
            session.device_id,
            session.phone,
            session.mt_instance_id,
            session.chats_sync,
            session.contacts_sync,
            session.drafts_sync,
            session.presence_sync,
            session.config_hash,
            json.dumps(session.user_agent) if session.user_agent else None,
            session.created_at,
            session.updated_at,
        ))
        await db.commit()

    async def update_token(self, old_token: str, new_token: str) -> None:
        db = await self._get_db()
        await db.execute(
            "UPDATE sessions SET token = ?, updated_at = ? WHERE token = ?",
            (new_token, time.time(), old_token),
        )
        await db.commit()

    async def delete_session(self, token: str) -> None:
        db = await self._get_db()
        await db.execute("DELETE FROM sessions WHERE token = ?", (token,))
        await db.commit()

    async def close(self) -> None:
        if self._db:
            await self._db.close()
            self._db = None

    def _row_to_session(self, row: aiosqlite.Row) -> SessionInfo:
        return SessionInfo(
            token=row["token"],
            device_id=row["device_id"],
            phone=row["phone"],
            mt_instance_id=row["mt_instance_id"],
            chats_sync=row["chats_sync"],
            contacts_sync=row["contacts_sync"],
            drafts_sync=row["drafts_sync"],
            presence_sync=row["presence_sync"],
            config_hash=row["config_hash"],
            user_agent=json.loads(row["user_agent"]) if row["user_agent"] else None,
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )


class InMemoryStore(StoreProtocol):
    """In-memory session store (for testing/ephemeral)."""

    def __init__(self):
        self._sessions: dict[str, SessionInfo] = {}

    async def load_session(self) -> Optional[SessionInfo]:
        if not self._sessions:
            return None
        return max(self._sessions.values(), key=lambda s: s.updated_at)

    async def load_session_by_device(self, device_id: str) -> Optional[SessionInfo]:
        for session in self._sessions.values():
            if session.device_id == device_id:
                return session
        return None

    async def load_session_by_phone(self, phone: str) -> Optional[SessionInfo]:
        for session in self._sessions.values():
            if session.phone == phone:
                return session
        return None

    async def save_session(self, session: SessionInfo) -> None:
        session.updated_at = time.time()
        self._sessions[session.token] = session

    async def update_token(self, old_token: str, new_token: str) -> None:
        if old_token in self._sessions:
            session = self._sessions.pop(old_token)
            session.token = new_token
            session.updated_at = time.time()
            self._sessions[new_token] = session

    async def delete_session(self, token: str) -> None:
        self._sessions.pop(token, None)

    async def close(self) -> None:
        self._sessions.clear()


class SessionManager:
    """High-level session manager."""

    def __init__(self, store: StoreProtocol):
        self.store = store

    async def load_session(self, device_id: str | None = None, phone: str | None = None) -> Optional[SessionInfo]:
        """Load session by priority: device_id > phone > most recent."""
        if device_id:
            session = await self.store.load_session_by_device(device_id)
            if session:
                return session

        if phone:
            session = await self.store.load_session_by_phone(phone)
            if session:
                return session

        return await self.store.load_session()

    async def save_session(self, session: SessionInfo) -> None:
        await self.store.save_session(session)

    async def rotate_token(self, old_token: str, new_token: str) -> None:
        await self.store.update_token(old_token, new_token)

    async def delete_session(self, token: str) -> None:
        await self.store.delete_session(token)

    async def close(self) -> None:
        await self.store.close()