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

engine = create_async_engine(
    str(settings.DATABASE_URL),
    pool_size=50,
    max_overflow=30,
    pool_pre_ping=True,
    echo=settings.DATABASE_ECHO,
    future=True,
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
