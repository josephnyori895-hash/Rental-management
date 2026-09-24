"""
RENTAL OS — Notification Log Model

Tracks every SMS/WhatsApp message sent: reminders, receipts, alerts.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    DateTime,
    ForeignKey,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDMixin, utcnow


class NotificationLog(Base, UUIDMixin, TimestampMixin):
    """Record of every notification sent."""

    __tablename__ = "notification_log"

    business_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    tenant_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    channel: Mapped[str] = mapped_column(
        String(20), nullable=False, comment="sms | whatsapp | email"
    )
    recipient: Mapped[str] = mapped_column(
        String(40), nullable=False, comment="Phone number or email"
    )
    template_name: Mapped[str | None] = mapped_column(
        String(80), nullable=True, comment="rent_reminder | payment_receipt | custom"
    )
    subject: Mapped[str | None] = mapped_column(String(200), nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), default="pending", nullable=False, index=True,
        comment="pending | sent | failed | simulated"
    )
    provider: Mapped[str] = mapped_column(
        String(30), default="console", nullable=False,
        comment="console | africastalking | twilio"
    )
    provider_message_id: Mapped[str | None] = mapped_column(
        String(120), nullable=True, comment="Provider's message ID (for tracking)"
    )
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
