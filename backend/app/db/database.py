"""
Voxara AI - Database Engine & Session Manager (SQLAlchemy 2.0 Async)

Supports:
- Cloud PostgreSQL (Neon / Supabase) via asyncpg with SSL connection pooling
- Local zero-dependency SQLite fallback via aiosqlite for local tests and development
- Thread-safe, non-blocking async session scopes
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator, Optional
from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import settings
from app.db.base import Base

logger = logging.getLogger("voxara-database")


class DatabaseManager:
    """
    Manages SQLAlchemy AsyncEngine and sessionmaker lifecycles.
    """

    def __init__(self, database_url: Optional[str] = None):
        self._url = database_url or settings.normalized_database_url
        self._engine: Optional[AsyncEngine] = None
        self._sessionmaker: Optional[async_sessionmaker[AsyncSession]] = None

    @property
    def engine(self) -> AsyncEngine:
        if self._engine is None:
            self._init_engine()
        assert self._engine is not None
        return self._engine

    @property
    def sessionmaker(self) -> async_sessionmaker[AsyncSession]:
        if self._sessionmaker is None:
            self._init_engine()
        assert self._sessionmaker is not None
        return self._sessionmaker

    def _init_engine(self) -> None:
        url = self._url

        # If using SQLite locally, ensure directory exists and configure foreign keys
        connect_args = {}
        if url.startswith("sqlite"):
            # Ensure local data directory exists
            if ":///" in url and not url.endswith(":memory:"):
                raw_path = url.split(":///", 1)[1]
                path_obj = Path(raw_path)
                path_obj.parent.mkdir(parents=True, exist_ok=True)
            connect_args = {"check_same_thread": False}

        self._engine = create_async_engine(
            url,
            connect_args=connect_args,
            echo=False,
            future=True,
            pool_pre_ping=True,  # Critical for Neon serverless / Supabase pooling reconnects
        )

        # Enforce foreign keys on SQLite connections
        if url.startswith("sqlite"):
            @event.listens_for(self._engine.sync_engine, "connect")
            def _set_sqlite_pragma(dbapi_connection, connection_record):
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.close()

        self._sessionmaker = async_sessionmaker(
            bind=self._engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )
        logger.info("Initialized DatabaseManager with URL dialect: %s", url.split("://", 1)[0])

    async def init_db(self) -> None:
        """
        Creates all defined database tables and indices if they do not exist.
        """
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database schema initialized successfully.")

    async def close_db(self) -> None:
        """
        Disposes of database engine and connection pools.
        """
        if self._engine is not None:
            await self._engine.dispose()
            self._engine = None
            self._sessionmaker = None
            logger.info("Database engine closed.")

    @asynccontextmanager
    async def session(self) -> AsyncGenerator[AsyncSession, None]:
        """
        Context manager providing an AsyncSession with automatic commit/rollback.
        """
        async with self.sessionmaker() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise


# Global database manager singleton
db_manager = DatabaseManager()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency yielding an async database session.
    """
    async with db_manager.session() as session:
        yield session
