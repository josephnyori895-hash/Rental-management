"""Rental OS platform subscription models.

These records are deliberately separate from landlord rent invoices and payments.
All monetary values use Decimal/Numeric; price and entitlement snapshots preserve
what a business actually subscribed to when catalogue prices later change.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, JSON, Numeric,
    String, Text, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDMixin, utcnow


SUBSCRIPTION_STATUSES = ("draft", "trialing", "active", "past_due", "cancelled", "expired")
CATALOG_ITEM_TYPES = ("package", "addon")
PRICING_MODELS = ("flat_recurring", "per_billable_unit", "one_time")
SUBSCRIPTION_INVOICE_STATUSES = ("draft", "open", "paid", "void", "past_due")
BILLING_INTERVALS = ("monthly", "quarterly", "annual", "one_time")
RECURRING_INTERVALS = ("monthly", "quarterly", "annual")
SUBSCRIPTION_PAYMENT_STATUSES = ("pending", "succeeded", "failed", "refunded")


def _sql_in(values: tuple[str, ...]) -> str:
    """Quote a fixed vocabulary for a CHECK constraint."""
    return ", ".join(f"'{value}'" for value in values)


class SubscriptionCatalogItem(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "subscription_catalog_items"
    __table_args__ = (
        # Names are bare: the metadata convention prefixes `ck_<table>_`.
        CheckConstraint(f"item_type IN ({_sql_in(CATALOG_ITEM_TYPES)})", name="item_type"),
        CheckConstraint(f"pricing_model IN ({_sql_in(PRICING_MODELS)})", name="pricing_model"),
        CheckConstraint("code ~ '^[a-z0-9][a-z0-9_-]*$'", name="code_format"),
    )

    code: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    item_type: Mapped[str] = mapped_column(String(16), nullable=False)  # package | addon
    pricing_model: Mapped[str] = mapped_column(String(32), nullable=False)
    features: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class SubscriptionPriceVersion(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "subscription_price_versions"
    __table_args__ = (
        Index("ix_subscription_price_item_effective", "catalog_item_id", "effective_from", "effective_to"),
        CheckConstraint("amount >= 0", name="amount_non_negative"),
        CheckConstraint("per_unit_amount >= 0", name="per_unit_non_negative"),
        CheckConstraint("included_units >= 0", name="included_units_non_negative"),
        CheckConstraint("currency ~ '^[A-Z]{3}$'", name="currency"),
        CheckConstraint(f"billing_interval IN ({_sql_in(BILLING_INTERVALS)})", name="billing_interval"),
        CheckConstraint(
            "effective_to IS NULL OR effective_to > effective_from",
            name="effective_window",
        ),
    )

    catalog_item_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("subscription_catalog_items.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="KES")
    billing_interval: Mapped[str] = mapped_column(String(16), nullable=False, default="monthly", server_default="monthly")
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    included_units: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    per_unit_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0"))
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    effective_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class BusinessSubscription(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "business_subscriptions"
    __table_args__ = (
        Index("ix_business_subscription_status", "business_id", "status"),
        CheckConstraint(f"status IN ({_sql_in(SUBSCRIPTION_STATUSES)})", name="status"),
        CheckConstraint("currency ~ '^[A-Z]{3}$'", name="currency"),
        CheckConstraint(f"billing_interval IN ({_sql_in(RECURRING_INTERVALS)})", name="billing_interval"),
    )

    business_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    billing_interval: Mapped[str] = mapped_column(String(16), nullable=False, default="monthly")
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="KES")
    billing_interval: Mapped[str] = mapped_column(String(16), nullable=False, default="monthly")
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    current_period_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    current_period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    trial_ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class BusinessSubscriptionItem(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "business_subscription_items"
    __table_args__ = (
        UniqueConstraint("subscription_id", "catalog_item_id", name="uq_subscription_item_catalog"),
        CheckConstraint("quantity > 0", name="quantity_positive"),
        CheckConstraint(f"billing_interval_snapshot IN ({_sql_in(BILLING_INTERVALS)})", name="billing_interval_snapshot"),
        CheckConstraint("unit_amount_snapshot >= 0", name="unit_amount"),
        CheckConstraint("total_amount_snapshot >= 0", name="total_amount"),
    )

    subscription_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("business_subscriptions.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    catalog_item_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("subscription_catalog_items.id", ondelete="RESTRICT"),
        nullable=False,
    )
    price_version_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("subscription_price_versions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    item_code_snapshot: Mapped[str] = mapped_column(String(80), nullable=False)
    item_name_snapshot: Mapped[str] = mapped_column(String(160), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    billing_interval_snapshot: Mapped[str] = mapped_column(String(16), nullable=False, default="monthly")
    unit_amount_snapshot: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    total_amount_snapshot: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    features_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)


class SubscriptionInvoice(Base, UUIDMixin, TimestampMixin):
    """Rental OS subscription billing only; never used for tenant rent."""
    __tablename__ = "subscription_invoices"
    __table_args__ = (
        UniqueConstraint("business_id", "invoice_number", name="uq_subscription_invoice_number"),
        CheckConstraint(f"status IN ({_sql_in(SUBSCRIPTION_INVOICE_STATUSES)})", name="status"),
        CheckConstraint("subtotal >= 0", name="subtotal"),
        CheckConstraint("total >= 0", name="total"),
        CheckConstraint("currency ~ '^[A-Z]{3}$'", name="currency"),
        CheckConstraint(f"billing_interval IN ({_sql_in(RECURRING_INTERVALS)})", name="billing_interval"),
    )

    business_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    subscription_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("business_subscriptions.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    invoice_number: Mapped[str] = mapped_column(String(40), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="KES")
    subtotal: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    total: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SubscriptionPayment(Base, UUIDMixin, TimestampMixin):
    """Platform subscription receipts; separate from landlord rent Payment."""
    __tablename__ = "subscription_payments"
    __table_args__ = (
        UniqueConstraint("provider", "provider_reference", name="uq_subscription_payment_provider_ref"),
        CheckConstraint(f"status IN ({_sql_in(SUBSCRIPTION_PAYMENT_STATUSES)})", name="status"),
        CheckConstraint("amount > 0", name="amount_positive"),
        CheckConstraint("currency ~ '^[A-Z]{3}$'", name="currency"),
    )

    business_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    invoice_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("subscription_invoices.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    provider_reference: Mapped[str] = mapped_column(String(160), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="KES")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
