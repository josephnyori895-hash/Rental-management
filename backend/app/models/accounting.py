"""
RENTAL OS — Accounting Models

Module:
    Account (chart of accounts) and JournalEntry (double-entry postings).

Purpose:
    Every rent payment, deposit and expense posts here so the operator gets
    a real P&L and trial balance — not just a list of invoices.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from uuid import UUID

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Numeric,
    String,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDMixin, utcnow


class AccountType(str, Enum):
    ASSET = "asset"
    LIABILITY = "liability"
    EQUITY = "equity"
    REVENUE = "revenue"
    INCOME = "income"
    EXPENSE = "expense"
    CONTRA_ASSET = "contra_asset"
    CONTRA_LIABILITY = "contra_liability"


# Default chart-of-accounts seeded per business on registration.
SYSTEM_ACCOUNTS = [
    ("1000", "Cash", AccountType.ASSET),
    ("1100", "M-Pesa Float", AccountType.ASSET),
    ("1200", "Bank", AccountType.ASSET),
    ("2000", "Security Deposits (Liability)", AccountType.LIABILITY),
    ("4000", "Rental Income", AccountType.REVENUE),
    ("4100", "Late Fee Income", AccountType.REVENUE),
    ("4200", "Utility Reimbursement", AccountType.REVENUE),
    ("5000", "Property Expenses", AccountType.EXPENSE),
]


class Account(Base, UUIDMixin, TimestampMixin):
    """A ledger account within a business chart of accounts."""

    __tablename__ = "accounts"

    business_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    code: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    account_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class JournalEntry(Base, UUIDMixin, TimestampMixin):
    """A single debit or credit line in the ledger."""

    __tablename__ = "journal_entries"

    business_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    property_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("properties.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    account_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("chart_of_accounts.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    entry_date: Mapped[date] = mapped_column(Date, default=date.today, nullable=False, index=True)
    debit: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0"), nullable=False)
    credit: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0"), nullable=False)
    currency: Mapped[str] = mapped_column(String(4), default="KES", nullable=False)
    entry_type: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    reference: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_type: Mapped[str | None] = mapped_column(String(30), nullable=True, index=True,
        comment="e.g. invoice, payment, expense, manual")
    source_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True, index=True)

    # account resolved via ChartOfAccount query in service layer
