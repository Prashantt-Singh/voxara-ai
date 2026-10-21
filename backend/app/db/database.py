"""
Voxara AI - PostgreSQL Database Engine & Session Manager (SQLAlchemy 2.0 Async)

Supports:
- PostgreSQL (Local development & Cloud: Neon / Supabase) via asyncpg with SSL connection pooling
- Thread-safe, non-blocking async session scopes
- Fail-fast connection testing and auto-reconnects (pool_pre_ping=True)
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator, Optional
from sqlalchemy import event, text
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
    Manages SQLAlchemy AsyncEngine and sessionmaker lifecycles for PostgreSQL.
    """

    def __init__(self, database_url: Optional[str] = None):
        self._custom_url = database_url
        self._engine: Optional[AsyncEngine] = None
        self._sessionmaker: Optional[async_sessionmaker[AsyncSession]] = None

    @property
    def url(self) -> str:
        return self._custom_url or settings.normalized_database_url

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
        url = self.url

        connect_args = {}
        if url.startswith("postgresql"):
            # Disable asyncpg statement cache for maximum compatibility with
            # transaction poolers (PgBouncer, Supabase pooler, Neon serverless)
            connect_args = {"statement_cache_size": 0}
        elif url.startswith("sqlite"):
            # Used only in explicit isolated test fixtures
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

    async def check_connection(self) -> bool:
        """
        Tests whether the database server is reachable and accepting queries.
        Returns True if successful, False otherwise.
        """
        try:
            async with self.engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            return True
        except Exception as exc:
            logger.warning("Database connection check failed: %s", exc)
            return False

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
