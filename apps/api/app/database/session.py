from __future__ import annotations

from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


def create_engine_and_session(
    database_url: str,
) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    # SQLite is still useful for local development and tests, but its writer
    # lock is process-wide.  Let short concurrent task/event writes wait for
    # the active writer instead of surfacing an avoidable ``database is
    # locked`` failure during cancellation or SSE persistence.
    connect_args = {"timeout": 30} if database_url.startswith("sqlite") else {}
    engine = create_async_engine(
        database_url,
        pool_pre_ping=True,
        connect_args=connect_args,
    )
    if database_url.startswith("sqlite") and ":memory:" not in database_url:
        # WAL lets the local UI/read endpoints continue polling while the
        # Runtime worker persists checkpoints.  Keep SQLite's default sync
        # level; this changes writer/read concurrency without weakening the
        # durability guarantee of terminal task state.
        def configure_sqlite(dbapi_connection: object, _record: object) -> None:
            cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
            try:
                cursor.execute("PRAGMA journal_mode=WAL")
                cursor.execute("PRAGMA busy_timeout=30000")
            finally:
                cursor.close()

        event.listen(engine.sync_engine, "connect", configure_sqlite)
    return engine, async_sessionmaker(engine, expire_on_commit=False)
