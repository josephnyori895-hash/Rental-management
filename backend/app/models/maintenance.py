"""
RENTAL OS — Maintenance Model

Module:
    MaintenanceTicket — tenant/caretaker reported issues with full lifecycle.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum
from uuid import UUID

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDMixin, utcnow


class TicketCategory(str, Enum):
    PLUMBING = "plumbing"
    ELECTRICAL = "electrical"
    STRUCTURAL = "structural"
    APPLIANCE = "appliance"
    PEST_CONTROL = "pest_control"
    CLEANING = "cleaning"
    SECURITY = "security"
    OTHER = "other"


class TicketPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class TicketStatus(str, Enum):
    OPEN = "open"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CLOSED = "closed"


class MaintenanceTicket(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "maintenance_tickets"

    business_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    property_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("properties.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    unit_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("units.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    tenant_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="SET NULL"),
        nullable=True,
    )
    reported_by: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    assigned_to: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(String(30), default=TicketCategory.OTHER.value, nullable=False, index=True)
    priority: Mapped[str] = mapped_column(String(10), default=TicketPriority.MEDIUM.value, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default=TicketStatus.OPEN.value, nullable=False, index=True)
    estimated_cost: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    actual_cost: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    vendor_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    vendor_phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    resolution_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    tenant_visible: Mapped[bool] = mapped_column(default=True, nullable=False)
