"""
IMANI Business OS

Module:
    Event Log Model

Author:
    OpenAI + Your Team

Purpose:
    Immutable event store for the event-driven architecture.
    Every system event is recorded here for audit,
    debugging, and replay capabilities.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, utcnow


class EventLog(Base):
    """
    Immutable event store record.

    Each row represents one domain event that occurred
    in the system. Events are never updated or deleted —
    only appended.
    """

    __tablename__ = "event_log"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    event_id: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, index=True
    )
    event_type: Mapped[str] = mapped_column(
        String(128), nullable=False, index=True
    )
    aggregate_id: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True
    )
    business_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    correlation_id: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True, index=True
    )
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    data: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False, index=True
    )

    def __repr__(self) -> str:
        return f"<Event {self.event_type} [{self.event_id[:8]}]>"
