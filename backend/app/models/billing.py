"""
RENTAL OS — Billing Models

Module:
    Invoice (rent / deposit / late-fee / utility charge), Payment
    (cash / M-Pesa / bank) and DepositRefund.

Purpose:
    The money layer. Invoices are generated per lease period; payments
    settle invoices and post to the double-entry ledger.
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
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDMixin, utcnow


class InvoiceType(str, Enum):
    RENT = "rent"
    DEPOSIT = "deposit"
    LATE_FEE = "late_fee"
    UTILITY = "utility"
    OTHER = "other"


class InvoiceStatus(str, Enum):
    DRAFT = "draft"
    PENDING = "pending"
    PARTIAL = "partial"
    PAID = "paid"
    OVERDUE = "overdue"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"


class PaymentMethod(str, Enum):
    MPESA = "mpesa"
    CASH = "cash"
    BANK = "bank"
    CARD = "card"


class Invoice(Base, UUIDMixin, TimestampMixin):
    """A charge raised against a lease."""

    __tablename__ = "invoices"

    business_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    lease_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("leases.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    unit_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("units.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    property_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("properties.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    invoice_number: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    invoice_type: Mapped[str] = mapped_column(
        String(20), default=InvoiceType.RENT.value, nullable=False, index=True
    )
    period_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    period_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    paid_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"), nullable=False)
    balance: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), default=InvoiceStatus.PENDING.value, nullable=False, index=True
    )
    mpesa_checkout_request_id: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)

    lease = relationship("Lease", back_populates="invoices")
    payments = relationship("Payment", back_populates="invoice", lazy="selectin")


class Payment(Base, UUIDMixin, TimestampMixin):
    """A payment settling one or more invoices (or a deposit)."""

    __tablename__ = "payments"

    business_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    invoice_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("invoices.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    lease_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("leases.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    method: Mapped[str] = mapped_column(String(20), default=PaymentMethod.MPESA.value, nullable=False)
    reference: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(20), default="completed", nullable=False)
    paid_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    recorded_by: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    mpesa_raw: Mapped[dict | None] = mapped_column(JSONB, nullable=True, comment="Full M-Pesa callback metadata")

    invoice = relationship("Invoice", back_populates="payments")


class DepositRefund(Base, UUIDMixin, TimestampMixin):
    """Refund of a tenant's deposit at end of lease."""

    __tablename__ = "deposit_refunds"

    business_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    lease_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("leases.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    method: Mapped[str] = mapped_column(String(20), default=PaymentMethod.CASH.value, nullable=False)
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    refunded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    recorded_by: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
