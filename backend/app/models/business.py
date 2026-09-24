"""
RENTAL OS — Business & Tenant Foundation Models

Module:
    Business (multi-tenant root) and User (staff/owner auth).

Purpose:
    Every rental operator is a Business tenant. Users belong to exactly one
    business and authenticate via email+password (owners/managers) or
    business slug + PIN (agents/caretakers on the floor).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from enum import Enum
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDMixin, utcnow


class UserRole(str, Enum):
    """Roles within a rental business tenant."""

    OWNER = "owner"
    MANAGER = "manager"
    AGENT = "agent"  # caretaker / property agent on the ground


class SubscriptionTier(str, Enum):
    """Billing tier for the operator."""

    BASIC = "basic"
    PRO = "pro"
    ENTERPRISE = "enterprise"


def _default_trial() -> datetime:
    return utcnow() + timedelta(days=14)


class Business(Base, UUIDMixin, TimestampMixin):
    """A rental operator (hostel, apartment block, estate, agency)."""

    __tablename__ = "businesses"

    name: Mapped[str] = mapped_column(String(160), nullable=False)
    slug: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    owner_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    subscription_tier: Mapped[str] = mapped_column(
        String(20), default=SubscriptionTier.BASIC.value, nullable=False
    )
    trial_ends_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_default_trial, nullable=False
    )
    settings: Mapped[dict] = mapped_column(JSON, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # ── M-Pesa / Daraja config (encrypted at rest, captured at enrollment) ──
    mpesa_consumer_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    mpesa_consumer_secret: Mapped[str | None] = mapped_column(Text, nullable=True)
    mpesa_passkey: Mapped[str | None] = mapped_column(Text, nullable=True)
    mpesa_shortcode: Mapped[str | None] = mapped_column(String(20), nullable=True)
    mpesa_callback_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    mpesa_env: Mapped[str] = mapped_column(String(10), default="sandbox", nullable=False)

    users = relationship("User", back_populates="business", lazy="selectin")


class User(Base, UUIDMixin, TimestampMixin):
    """Staff member of a rental business."""

    __tablename__ = "users"

    business_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(160), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    role: Mapped[str] = mapped_column(String(20), default=UserRole.AGENT.value, nullable=False, index=True)
    pin_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    business = relationship("Business", back_populates="users")
