"""
RENTAL OS — Lease Model

Module:
    Lease (rental agreement binding a Tenant to a Unit). The heart of the
    rental domain: drives rent invoices, occupancy and deposits.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from uuid import UUID

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDMixin, utcnow


class LeaseStatus(str, Enum):
    PENDING = "pending"
    ACTIVE = "active"
    ENDED = "ended"
    TERMINATED = "terminated"


class Lease(Base, UUIDMixin, TimestampMixin):
    """A rental agreement between a tenant and a unit."""

    __tablename__ = "leases"

    business_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    unit_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("units.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    property_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("properties.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    rent_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    deposit_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"), nullable=False)
    payment_day: Mapped[int] = mapped_column(default=1, nullable=False)  # day-of-month rent falls due
    payment_frequency: Mapped[str] = mapped_column(String(20), default="monthly", nullable=False)
    status: Mapped[str] = mapped_column(String(20), default=LeaseStatus.PENDING.value, nullable=False, index=True)
    tenant_signed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    owner_signed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    signed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    unit = relationship("Unit")
    tenant = relationship("Tenant", back_populates="leases")
    invoices = relationship("Invoice", back_populates="lease", lazy="selectin")
