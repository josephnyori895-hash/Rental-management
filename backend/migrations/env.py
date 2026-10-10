"""
Rental OS — Alembic Environment (async)

Imports every model so autogenerate sees the full schema.
"""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.core.database import Base

# ── Import ALL models so they register on Base.metadata ──────────
from app.models.base import *        # AuditLog + mixins
from app.models.business import *    # Business, User, UserRole, SubscriptionTier
from app.models.tenant import *      # Tenant
from app.models.lease import *       # Lease, LeaseStatus
from app.models.property import *    # Property, Unit, enums
from app.models.billing import *     # Invoice, Payment, DepositRefund
from app.models.event import *       # EventLog
from app.notifications.models import *  # NotificationLog
from app.documents.models import *  # Document

# Reuse the application's DSN translation, so migrations connect exactly as the
# app does. A hosted Postgres DSN carries `?sslmode=require`, which SQLAlchemy's
# asyncpg dialect rejects as an unknown keyword — reading `settings.DATABASE_URL`
# directly here would make `alembic upgrade head` fail on a deploy while the app
# itself connected fine.
from app.core.database import DATABASE_CONNECT_ARGS, DATABASE_URL as _DATABASE_URL

config = context.config
config.set_main_option("sqlalchemy.url", _DATABASE_URL)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        connect_args=DATABASE_CONNECT_ARGS,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
