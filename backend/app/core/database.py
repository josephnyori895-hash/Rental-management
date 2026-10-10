"""
IMANI Business OS

Module:
    Database Core

Author:
    OpenAI + Your Team

Purpose:
    Async SQLAlchemy engine, session factory, and base model.
    All models inherit from Base.
"""

from __future__ import annotations

from typing import AsyncGenerator

from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

# ── PostgreSQL naming convention ────────────────────────────────
# Consistent constraint names for clean migrations and introspection
convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

metadata = MetaData(naming_convention=convention)

# ── Engine & Session ────────────────────────────────────────────

# Hosted Postgres poolers answer on a hostname that says so: Neon's is
# `...-pooler.<region>.aws.neon.tech`, PgBouncer deployments usually similar.
POOLER_HOST_MARKERS = ("-pooler", "pooler.")


def _connect_args_and_url(raw_url: str) -> tuple[dict, str]:
    """Translate a hosted DSN into asyncpg connection arguments.

    A managed Postgres is reached over TLS, usually behind a connection pooler,
    and both facts need saying explicitly:

      * asyncpg does not read `sslmode` from a URL, and SQLAlchemy's asyncpg
        dialect rejects the unknown keyword — so `?sslmode=require` (what every
        provider hands you) has to become `ssl="require"`.
      * asyncpg caches prepared statements per connection, which is
        incompatible with a transaction-mode pooler such as PgBouncer or Neon's
        pooler: the server may route the same connection elsewhere between
        statements, and the cached statement then does not exist. A DSN naming
        a pooler therefore opts out of that cache.

    Returns the connection arguments and the URL with those keys removed.
    """
    from sqlalchemy.engine import make_url

    url = make_url(raw_url)
    query = dict(url.query)
    connect_args: dict = {}

    sslmode = query.pop("sslmode", None)
    if sslmode:
        connect_args["ssl"] = str(sslmode)

    # channel_binding is libpq-only; asyncpg rejects it.
    query.pop("channel_binding", None)

    host = url.host or ""
    if "statement_cache_size" in query:
        connect_args["statement_cache_size"] = int(query.pop("statement_cache_size"))
    elif any(marker in host for marker in POOLER_HOST_MARKERS):
        connect_args["statement_cache_size"] = 0

    if not connect_args:
        return {}, raw_url

    return connect_args, url.set(query=query).render_as_string(hide_password=False)


DATABASE_CONNECT_ARGS, DATABASE_URL = _connect_args_and_url(str(settings.DATABASE_URL))

engine = create_async_engine(
    DATABASE_URL,
    pool_size=settings.DATABASE_POOL_SIZE,
    max_overflow=settings.DATABASE_MAX_OVERFLOW,
    pool_pre_ping=True,
    echo=settings.DATABASE_ECHO,
    future=True,
    connect_args=DATABASE_CONNECT_ARGS,
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """Base class for all IMANI database models."""

    metadata = metadata


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that yields an async database session.
    Session is automatically closed after the request completes.
    """
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """
    Create all tables. Used during initial setup and tests.
    In production, use Alembic migrations instead.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """Dispose of the connection pool on shutdown."""
    await engine.dispose()
