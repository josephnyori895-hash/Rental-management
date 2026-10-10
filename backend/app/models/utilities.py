"""
RENTAL OS — Utilities & Service-Charge Models

Module:
    UtilityRate (tariff + apportionment rule) and MeterReading (a unit
    meter, or a property-wide bulk meter).

Purpose:
    Utility billing. A caretaker logs a meter reading (WhatsApp or web),
    the reading is priced against the applicable tariff, and the tenant is
    invoiced through the normal `Invoice` row so it flows into the same
    double-entry ledger as rent.

    Shared meters (one water main for a whole block) are recorded with
    `unit_id = NULL` and apportioned across units by a `SplitMethod`.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import Enum
from uuid import UUID

from sqlalchemy import (
    Boolean,
    Date,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDMixin


class UtilityType(str, Enum):
    """What is being metered or charged for."""

    WATER = "water"
    ELECTRICITY = "electricity"
    GAS = "gas"
    WIFI = "wifi"
    GARBAGE = "garbage"
    SERVICE_CHARGE = "service_charge"
    OTHER = "other"


class SplitMethod(str, Enum):
    """How a shared (bulk) utility cost is divided across units."""

    METERED = "metered"  # by each unit's own consumption in the period
    EQUAL = "equal"  # same share per occupied unit
    OCCUPANCY = "occupancy"  # by max_occupants
    RENT = "rent"  # by monthly rent (area proxy)


class MeterSource(str, Enum):
    """Where a reading came from — useful for auditing caretaker entries."""

    WEB = "web"
    WHATSAPP = "whatsapp"
    IMPORT = "import"


class UtilityRate(Base, UUIDMixin, TimestampMixin):
    """
    A tariff and apportionment rule.

    Scope resolution: a rate with `unit_id` set wins over a property-wide
    rate for the same utility type (see `app.billing.utilities.resolve_rate`).
    """

    __tablename__ = "utility_rates"

    business_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    property_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("properties.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    unit_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("units.id", ondelete="CASCADE"),
        nullable=True, index=True,
        comment="NULL = property-wide default tariff",
    )
    utility_type: Mapped[str] = mapped_column(
        String(24), default=UtilityType.WATER.value, nullable=False, index=True
    )
    label: Mapped[str | None] = mapped_column(String(80), nullable=True)
    rate_per_unit: Mapped[Decimal] = mapped_column(
        Numeric(12, 4), default=Decimal("0"), nullable=False
    )
    fixed_charge: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0"), nullable=False
    )
    split_method: Mapped[str] = mapped_column(
        String(16), default=SplitMethod.METERED.value, nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)


class MeterReading(Base, UUIDMixin, TimestampMixin):
    """
    A meter reading, and the resulting charge if one was raised.

    `unit_id IS NULL` means a bulk/shared meter for the whole property —
    those are apportioned across units rather than billed to one tenant.
    """

    __tablename__ = "meter_readings"
    __table_args__ = (
        Index("ix_meter_readings_scope", "business_id", "property_id", "utility_type", "reading_date"),
    )

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
        comment="NULL = bulk/shared meter for the whole property",
    )
    utility_type: Mapped[str] = mapped_column(
        String(24), default=UtilityType.WATER.value, nullable=False, index=True
    )
    reading_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    previous_reading: Mapped[Decimal | None] = mapped_column(
        Numeric(14, 3), nullable=True, comment="NULL on the first (baseline) reading"
    )
    current_reading: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    units_consumed: Mapped[Decimal] = mapped_column(
        Numeric(14, 3), default=Decimal("0"), nullable=False
    )
    rate_per_unit: Mapped[Decimal] = mapped_column(
        Numeric(12, 4), default=Decimal("0"), nullable=False
    )
    fixed_charge: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0"), nullable=False
    )
    amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0"), nullable=False
    )
    invoice_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("invoices.id", ondelete="SET NULL"),
        nullable=True, index=True,
        comment="The invoice this reading produced, if it was billed",
    )
    source: Mapped[str] = mapped_column(
        String(16), default=MeterSource.WEB.value, nullable=False
    )
    recorded_by: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    @property
    def is_bulk(self) -> bool:
        """A shared meter reading covering more than one unit."""
        return self.unit_id is None
