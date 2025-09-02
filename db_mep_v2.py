# db_mep_v2.py
from __future__ import annotations

import logging
import os
from typing import Optional, AsyncGenerator

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy.exc import NoSuchModuleError
from sqlalchemy import create_engine as create_sync_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# -----------------------------------------------------------------------------
# Log
# -----------------------------------------------------------------------------
logger = logging.getLogger("mep.db")

# -----------------------------------------------------------------------------
# Config
# -----------------------------------------------------------------------------
# Read DB URL from env; provide a safe local default (sync psycopg2).
DATABASE_URL: str = (
    os.getenv("DATABASE_URL", "postgresql+psycopg2://postgres:postgres@127.0.0.1:5432/mep")
).strip()


def _derive_sync_url(url: str) -> str:
    """
    Convert async URLs to a sync driver-compatible URL for create_engine.
    - postgresql+asyncpg://  -> postgresql+psycopg2://
    - postgresql+psycopg://  -> postgresql+psycopg2://
    Keep other variants unchanged.
    """
    if "+asyncpg" in url:
        return url.replace("+asyncpg", "+psycopg2")
    if "+psycopg" in url and "+psycopg2" not in url:
        return url.replace("+psycopg", "+psycopg2")
    return url


# -----------------------------------------------------------------------------
# Async engine / session (lazy init)
# -----------------------------------------------------------------------------
_async_engine = None
_async_session_factory: Optional[async_sessionmaker[AsyncSession]] = None


def _init_async_engine() -> None:
    global _async_engine, _async_session_factory
    if _async_engine is not None:
        return
    try:
        _async_engine = create_async_engine(DATABASE_URL, pool_pre_ping=True, future=True)
        _async_session_factory = async_sessionmaker(
            bind=_async_engine,
            expire_on_commit=False,
            autoflush=False,
            autocommit=False,
        )
        logger.info("Async engine initialized (%s).", DATABASE_URL)
    except NoSuchModuleError as e:
        logger.error("Async driver missing for URL %s: %s", DATABASE_URL, e)
        _async_engine = None
        _async_session_factory = None


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency (async). Raises if driver/URL is invalid.
    """
    if _async_session_factory is None:
        _init_async_engine()
    if _async_session_factory is None:
        raise RuntimeError("Database is disabled or async driver missing.")
    session: AsyncSession = _async_session_factory()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


async def get_session_optional() -> AsyncGenerator[Optional[AsyncSession], None]:
    """
    Optional version: yields None if the DB is unavailable (no exception).
    Useful for routes that can work in a degraded mode.
    """
    if _async_session_factory is None:
        _init_async_engine()
    if _async_session_factory is None:
        yield None
        return
    session: AsyncSession = _async_session_factory()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


# -----------------------------------------------------------------------------
# Sync engine (eager init) — used by main1.py and repositories
# -----------------------------------------------------------------------------
SYNC_DATABASE_URL = _derive_sync_url(DATABASE_URL)
engine = None  # exported


def _init_sync_engine() -> None:
    global engine
    if engine is not None:
        return
    try:
        engine = create_sync_engine(
            SYNC_DATABASE_URL,
            pool_size=5,         # persistent connections
            max_overflow=10,     # temporary extras
            pool_recycle=1800,   # recycle after 30 min (avoid timeouts)
            pool_pre_ping=True,  # check connection before use
            future=True,
        )
        logger.info("Sync engine initialized (%s).", SYNC_DATABASE_URL)
    except NoSuchModuleError as e:
        logger.error("Sync driver missing for URL %s: %s", SYNC_DATABASE_URL, e)
        engine = None


_init_sync_engine()


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
def is_db_enabled_sync() -> bool:
    """True if the sync engine is available."""
    return engine is not None


def get_sync_url() -> str:
    """Return the effective URL used by the sync engine."""
    return SYNC_DATABASE_URL


__all__ = [
    "DATABASE_URL",
    "engine",
    "get_sync_url",
    "is_db_enabled_sync",
    "get_session",
    "get_session_optional",
]



