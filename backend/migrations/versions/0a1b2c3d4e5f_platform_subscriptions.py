"""create separate Rental OS platform subscription foundation

Revision ID: 0a1b2c3d4e5f
Revises: f6a7b8c9d0e1
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0a1b2c3d4e5f"
down_revision: Union[str, None] = "f6a7b8c9d0e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "subscription_catalog_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("code", sa.String(80), nullable=False, unique=True),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("item_type", sa.String(16), nullable=False),
        sa.Column("pricing_model", sa.String(32), nullable=False),
        sa.Column("features", sa.JSON(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("display_order", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "subscription_price_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("catalog_item_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("subscription_catalog_items.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("included_units", sa.Integer(), nullable=False),
        sa.Column("per_unit_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("effective_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_subscription_price_versions_catalog_item_id", "subscription_price_versions", ["catalog_item_id"])
    op.create_index("ix_subscription_price_item_effective", "subscription_price_versions", ["catalog_item_id", "effective_from", "effective_to"])
    op.create_table(
        "business_subscriptions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("business_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("current_period_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("trial_ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_business_subscriptions_business_id", "business_subscriptions", ["business_id"])
    op.create_index("ix_business_subscription_status", "business_subscriptions", ["business_id", "status"])
    op.create_table(
        "business_subscription_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("subscription_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("business_subscriptions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("catalog_item_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("subscription_catalog_items.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("price_version_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("subscription_price_versions.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("item_code_snapshot", sa.String(80), nullable=False),
        sa.Column("item_name_snapshot", sa.String(160), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_amount_snapshot", sa.Numeric(12, 2), nullable=False),
        sa.Column("total_amount_snapshot", sa.Numeric(12, 2), nullable=False),
        sa.Column("features_snapshot", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("subscription_id", "catalog_item_id", name="uq_subscription_item_catalog"),
    )
    op.create_index("ix_business_subscription_items_subscription_id", "business_subscription_items", ["subscription_id"])
    op.create_table(
        "subscription_invoices",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("business_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("subscription_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("business_subscriptions.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("invoice_number", sa.String(40), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("subtotal", sa.Numeric(12, 2), nullable=False),
        sa.Column("total", sa.Numeric(12, 2), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("business_id", "invoice_number", name="uq_subscription_invoice_number"),
    )
    op.create_index("ix_subscription_invoices_business_id", "subscription_invoices", ["business_id"])
    op.create_index("ix_subscription_invoices_subscription_id", "subscription_invoices", ["subscription_id"])
    op.create_table(
        "subscription_payments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("business_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("invoice_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("subscription_invoices.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("provider", sa.String(40), nullable=False),
        sa.Column("provider_reference", sa.String(160), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("provider", "provider_reference", name="uq_subscription_payment_provider_ref"),
    )
    op.create_index("ix_subscription_payments_business_id", "subscription_payments", ["business_id"])
    op.create_index("ix_subscription_payments_invoice_id", "subscription_payments", ["invoice_id"])


def downgrade() -> None:
    op.drop_table("subscription_payments")
    op.drop_table("subscription_invoices")
    op.drop_table("business_subscription_items")
    op.drop_table("business_subscriptions")
    op.drop_table("subscription_price_versions")
    op.drop_table("subscription_catalog_items")
