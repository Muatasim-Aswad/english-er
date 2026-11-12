"""Async SQLite engine and session wiring."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

DEFAULT_BUSY_TIMEOUT_MS = 5_000


def sqlite_url(path: Path) -> str:
    """Return an aiosqlite URL for an absolute database path."""

    return f"sqlite+aiosqlite:///{path.expanduser().resolve()}"


def _configure_sqlite(engine: Engine, busy_timeout_ms: int) -> None:
    @event.listens_for(engine, "connect")
    def set_sqlite_pragmas(dbapi_connection: object, _connection_record: object) -> None:
        cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
        try:
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute(f"PRAGMA busy_timeout={busy_timeout_ms:d}")
            cursor.execute("PRAGMA journal_mode=WAL")
        finally:
            cursor.close()


@dataclass(slots=True)
class Database:
    """Owned async engine plus its session factory."""

    engine: AsyncEngine
    sessions: async_sessionmaker[AsyncSession]

    @classmethod
    def create(
        cls,
        url: str,
        *,
        busy_timeout_ms: int = DEFAULT_BUSY_TIMEOUT_MS,
    ) -> Database:
        if busy_timeout_ms < 0:
            raise ValueError("busy_timeout_ms must not be negative")
        engine = create_async_engine(url)
        if engine.url.get_backend_name() == "sqlite":
            _configure_sqlite(engine.sync_engine, busy_timeout_ms)
        return cls(
            engine=engine,
            sessions=async_sessionmaker(engine, expire_on_commit=False),
        )

    async def close(self) -> None:
        await self.engine.dispose()
