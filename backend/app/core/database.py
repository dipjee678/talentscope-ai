"""Async SQLAlchemy 2.0 database engine and session management.

Supports PostgreSQL (+ pgvector) in production and SQLite (aiosqlite) in local dev.
"""
from __future__ import annotations

from pathlib import Path
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy import event
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings


class Base(DeclarativeBase):
    pass


def _ensure_sqlite_dir(database_url: str) -> None:
    if database_url.startswith("sqlite"):
        parts = database_url.split("///", 1)
        if len(parts) == 2 and parts[1] != ":memory:":
            db_path = Path(parts[1])
            db_path.parent.mkdir(parents=True, exist_ok=True)


def enable_sqlite_foreign_keys(async_engine: AsyncEngine) -> None:
    """SQLite ignores ON DELETE CASCADE unless foreign keys are switched on per connection.
    Without this, deleting a CV or account leaves orphaned rows locally (Postgres always enforces)."""

    @event.listens_for(async_engine.sync_engine, "connect")
    def _fk_pragma(dbapi_connection, _record):  # pragma: no cover - trivial
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def create_engine_from_url(database_url: str) -> AsyncEngine:
    _ensure_sqlite_dir(database_url)
    kwargs = {"echo": False, "future": True}
    if database_url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    else:
        kwargs["pool_pre_ping"] = True
        kwargs["pool_size"] = 10
        kwargs["max_overflow"] = 20
    eng = create_async_engine(database_url, **kwargs)
    if database_url.startswith("sqlite"):
        enable_sqlite_foreign_keys(eng)
    return eng


settings = get_settings()
engine: AsyncEngine = create_engine_from_url(settings.DATABASE_URL)
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db(target_engine: AsyncEngine | None = None) -> None:
    """Create tables (and pgvector extension on Postgres if available)."""
    eng = target_engine or engine
    # Ensure all models are imported before create_all
    from app.models import entities  # noqa: F401

    async with eng.begin() as conn:
        if str(eng.url).startswith("postgresql"):
            try:
                await conn.exec_driver_sql("CREATE EXTENSION IF NOT EXISTS vector")
            except Exception:
                pass
        await conn.run_sync(Base.metadata.create_all)
