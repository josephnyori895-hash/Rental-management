"""
RENTAL OS — Property & Unit Models

Module:
    Property (hostel / apartment block / building / house) and Unit
    (room / bedspace / studio / shop) — the physical assets being rented.
"""

from __future__ import annotations

from decimal import Decimal
from enum import Enum
from uuid import UUID

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import SoftDeleteMixin, TimestampMixin, UUIDMixin


class PropertyType(str, Enum):
    HOSTEL = "hostel"
    APARTMENT = "apartment"
    BUILDING = "building"
    HOUSE = "house"
    COMMERCIAL = "commercial"


class UnitType(str, Enum):
    ROOM = "room"
    BEDSPACE = "bedspace"
    STUDIO = "studio"
    ONE_BED = "1_bedroom"
    TWO_BED = "2_bedroom"
    SHOP = "shop"


class UnitStatus(str, Enum):
    AVAILABLE = "available"
    OCCUPIED = "occupied"
    MAINTENANCE = "maintenance"
    RESERVED = "reserved"


class Property(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    """A building or site that contains rentable units."""

    __tablename__ = "properties"

    business_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    property_type: Mapped[str] = mapped_column(
        String(20), default=PropertyType.HOSTEL.value, nullable=False, index=True
    )
    manager_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    units = relationship("Unit", back_populates="property", lazy="selectin")


class Unit(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    """A rentable space within a property."""

    __tablename__ = "units"

    business_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    property_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("properties.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    unit_number: Mapped[str] = mapped_column(String(40), nullable=False)
    unit_type: Mapped[str] = mapped_column(
        String(20), default=UnitType.ROOM.value, nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(
        String(20), default=UnitStatus.AVAILABLE.value, nullable=False, index=True
    )
    monthly_rent: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"), nullable=False)
    deposit_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"), nullable=False)
    max_occupants: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    amenities: Mapped[dict] = mapped_column(JSON, default=list)
    current_lease_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True
    )

    property = relationship("Property", back_populates="units")
