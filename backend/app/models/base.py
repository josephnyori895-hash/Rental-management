"""
IMANI Business OS

Module:
    Base Models — Mixins & Audit

Author:
    OpenAI + Your Team

Purpose:
    Shared model foundation: UUID PKs, timestamps,
    soft deletes, and a universal audit log.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, declared_attr

from app.core.database import Base


def utcnow() -> datetime:
    """Return the current UTC datetime."""
    return datetime.now(timezone.utc)


def new_uuid() -> uuid.UUID:
    """Generate a new UUID v4."""
    return uuid.uuid4()


# ── Mixins ──────────────────────────────────────────────────────


class TimestampMixin:
    """Adds created_at and updated_at timestamp columns."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        nullable=False,
        index=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
        nullable=False,
    )


class SoftDeleteMixin:
    """Adds is_deleted and deleted_at for soft deletes."""

    is_deleted: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        index=True,
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    def soft_delete(self) -> None:
        """Mark this record as deleted."""
        self.is_deleted = True
        self.deleted_at = utcnow()


class UUIDMixin:
    """Adds a UUID primary key."""

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=new_uuid,
        index=True,
    )


# ── Audit Log ───────────────────────────────────────────────────


class AuditLog(Base):
    """
    Immutable audit trail for all critical operations.

    Every INSERT, UPDATE, DELETE on sensitive tables
    should create an AuditLog entry via database triggers
    or application-level hooks.
    """

    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=new_uuid
    )
    business_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("businesses.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    table_name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    record_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    action: Mapped[str] = mapped_column(
        String(16), nullable=False
    )  # INSERT | UPDATE | DELETE
    old_values: Mapped[Optional[dict]] = mapped_column(
        Text, nullable=True
    )  # JSON string
    new_values: Mapped[Optional[dict]] = mapped_column(
        Text, nullable=True
    )  # JSON string
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    def __repr__(self) -> str:
        return f"<AuditLog {self.action} on {self.table_name} by {self.user_id}>"
