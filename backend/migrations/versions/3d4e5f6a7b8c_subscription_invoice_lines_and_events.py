"""Add subscription invoice lines and lifecycle events.

Revision ID: 3d4e5f6a7b8c
Revises: 2c3d4e5f6a7b
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "3d4e5f6a7b8c"
down_revision: Union[str, None] = "2c3d4e5f6a7b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "subscription_invoice_lines",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("invoice_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("subscription_invoices.id", ondelete="CASCADE"), nullable=False),
        sa.Column("line_number", sa.Integer(), nullable=False),
        sa.Column("item_code_snapshot", sa.String(80), nullable=False),
        sa.Column("item_name_snapshot", sa.String(160), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("billing_interval_snapshot", sa.String(16), nullable=False),
        sa.Column("billable_units_snapshot", sa.Integer(), nullable=False),
        sa.Column("included_units_snapshot", sa.Integer(), nullable=False),
        sa.Column("per_unit_amount_snapshot", sa.Numeric(12, 2), nullable=False),
        sa.Column("unit_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("total_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("features_snapshot", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("invoice_id", "line_number", name="uq_subscription_invoice_line_number"),
        # Inline so the rendered names match the model's `ck_<table>_<name>` output.
        sa.CheckConstraint("line_number >= 1", name="line_number_positive"),
        sa.CheckConstraint("quantity >= 1", name="quantity_positive"),
        sa.CheckConstraint("unit_amount >= 0 AND total_amount >= 0", name="amounts_nonnegative"),
        sa.CheckConstraint("billing_interval_snapshot IN ('monthly', 'quarterly', 'annual', 'one_time')", name="billing_interval_snapshot"),
        sa.CheckConstraint(
            "billable_units_snapshot >= 0 AND included_units_snapshot >= 0 "
            "AND per_unit_amount_snapshot >= 0",
            name="snapshot_non_negative",
        ),
    )
    op.create_index("ix_subscription_invoice_lines_created_at", "subscription_invoice_lines", ["created_at"])
    op.create_index("ix_subscription_invoice_lines_invoice_id", "subscription_invoice_lines", ["invoice_id"])
    op.create_index("ix_subscription_invoice_lines_id", "subscription_invoice_lines", ["id"])
    op.execute("""
        CREATE FUNCTION prevent_subscription_invoice_line_mutation()
        RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'subscription invoice lines are immutable';
        END;
        $$ LANGUAGE plpgsql;
    """)
    op.execute("""
        CREATE TRIGGER subscription_invoice_lines_immutable
        BEFORE UPDATE OR DELETE ON subscription_invoice_lines
        FOR EACH ROW EXECUTE FUNCTION prevent_subscription_invoice_line_mutation();
    """)

    op.create_table(
        "business_subscription_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("business_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("subscription_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("business_subscriptions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("event_metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_business_subscription_events_business_id", "business_subscription_events", ["business_id"])
    op.create_index("ix_business_subscription_events_subscription_id", "business_subscription_events", ["subscription_id"])
    op.create_index("ix_business_subscription_events_id", "business_subscription_events", ["id"])
    op.create_index("ix_business_subscription_event_subscription", "business_subscription_events", ["subscription_id", "created_at"])
    op.create_index("ix_business_subscription_event_business", "business_subscription_events", ["business_id", "created_at"])
    op.execute("""
        CREATE FUNCTION prevent_business_subscription_event_mutation()
        RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'subscription lifecycle events are append-only';
        END;
        $$ LANGUAGE plpgsql;
    """)
    op.execute("""
        CREATE TRIGGER business_subscription_events_append_only
        BEFORE UPDATE OR DELETE ON business_subscription_events
        FOR EACH ROW EXECUTE FUNCTION prevent_business_subscription_event_mutation();
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS subscription_invoice_lines_immutable ON subscription_invoice_lines")
    op.execute("DROP FUNCTION IF EXISTS prevent_subscription_invoice_line_mutation()")
    op.execute("DROP TRIGGER IF EXISTS business_subscription_events_append_only ON business_subscription_events")
    op.execute("DROP FUNCTION IF EXISTS prevent_business_subscription_event_mutation()")
    op.drop_table("business_subscription_events")
    op.drop_table("subscription_invoice_lines")
