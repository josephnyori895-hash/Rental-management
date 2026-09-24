"""
RENTAL OS — Expense Model

Module:
    Expense — operational costs recorded against properties.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import Enum
from uuid import UUID

from sqlalchemy import (
    Date,
    ForeignKey,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDMixin


class ExpenseCategory(str, Enum):
    REPAIRS = "repairs"
    UTILITIES = "utilities"
    WATER = "water"
    ELECTRICITY = "electricity"
    WIFI = "wifi"
    CLEANING = "cleaning"
    SECURITY = "security"
    GARBAGE = "garbage"
    SUPPLIES = "supplies"
    SALARY = "salary"
    TAX = "tax"
    INSURANCE = "insurance"
    MARKETING = "marketing"
    LEGAL = "legal"
    MISC = "misc"


class Expense(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "expenses"

    business_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    property_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("properties.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    category: Mapped[str] = mapped_column(String(30), default=ExpenseCategory.MISC.value, nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    vendor: Mapped[str | None] = mapped_column(String(200), nullable=True)
    receipt_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    paid_at: Mapped[date] = mapped_column(Date, nullable=False)
    recurring: Mapped[bool] = mapped_column(default=False, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
