"""create application tables and business columns missing from fresh installs

Revision ID: 4e5f6a7b8c9d
Revises: 3d4e5f6a7b8c
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '4e5f6a7b8c9d'
down_revision: Union[str, None] = '3d4e5f6a7b8c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TRACKER = "_rental_os_schema_repair_objects"


def _inspector():
    return sa.inspect(op.get_bind())


def _record(kind: str, name: str) -> None:
    op.get_bind().execute(
        sa.text(f"INSERT INTO {TRACKER} (object_type, object_name) VALUES (:kind, :name)"),
        {"kind": kind, "name": name},
    )


def upgrade() -> None:
    bind = op.get_bind()
    op.create_table(
        TRACKER,
        sa.Column("object_type", sa.String(16), primary_key=True),
        sa.Column("object_name", sa.String(128), primary_key=True),
    )

    existing = set(_inspector().get_table_names())

    # Chart of accounts must exist before journal_entries can reference it.
    if "chart_of_accounts" not in existing:
        op.create_table(
            "chart_of_accounts",
            sa.Column("business_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("code", sa.String(10), nullable=False),
            sa.Column("name", sa.String(200), nullable=False),
            sa.Column("account_type", sa.String(20), nullable=False),
            sa.Column("category", sa.String(30), nullable=True),
            sa.Column("is_system", sa.Boolean(), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("parent_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("sort_order", sa.Integer(), nullable=True),
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["parent_id"], ["chart_of_accounts.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_chart_of_accounts_business_id", "chart_of_accounts", ["business_id"])
        op.create_index("ix_chart_of_accounts_id", "chart_of_accounts", ["id"])
        op.create_index("ix_chart_of_accounts_created_at", "chart_of_accounts", ["created_at"])
        _record("table", "chart_of_accounts")

    existing = set(_inspector().get_table_names())
    if "expenses" not in existing:
        op.create_table(
            "expenses",
            sa.Column("business_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("property_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("category", sa.String(30), nullable=False),
            sa.Column("amount", sa.Numeric(12, 2), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("vendor", sa.String(200), nullable=True),
            sa.Column("receipt_url", sa.String(500), nullable=True),
            sa.Column("paid_at", sa.Date(), nullable=False),
            sa.Column("recurring", sa.Boolean(), nullable=False),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["property_id"], ["properties.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_expenses_business_id", "expenses", ["business_id"])
        op.create_index("ix_expenses_property_id", "expenses", ["property_id"])
        op.create_index("ix_expenses_category", "expenses", ["category"])
        op.create_index("ix_expenses_id", "expenses", ["id"])
        op.create_index("ix_expenses_created_at", "expenses", ["created_at"])
        _record("table", "expenses")

    existing = set(_inspector().get_table_names())
    if "maintenance_tickets" not in existing:
        op.create_table(
            "maintenance_tickets",
            sa.Column("business_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("property_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("unit_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("reported_by", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("assigned_to", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("title", sa.String(200), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("category", sa.String(30), nullable=False),
            sa.Column("priority", sa.String(10), nullable=False),
            sa.Column("status", sa.String(20), nullable=False),
            sa.Column("estimated_cost", sa.Numeric(12, 2), nullable=True),
            sa.Column("actual_cost", sa.Numeric(12, 2), nullable=True),
            sa.Column("vendor_name", sa.String(120), nullable=True),
            sa.Column("vendor_phone", sa.String(20), nullable=True),
            sa.Column("resolution_notes", sa.Text(), nullable=True),
            sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("tenant_visible", sa.Boolean(), nullable=False),
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["property_id"], ["properties.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["unit_id"], ["units.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["reported_by"], ["users.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["assigned_to"], ["users.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
        for column in ("business_id", "property_id", "unit_id", "assigned_to", "category", "status", "id", "created_at"):
            op.create_index(f"ix_maintenance_tickets_{column}", "maintenance_tickets", [column])
        _record("table", "maintenance_tickets")

    existing = set(_inspector().get_table_names())
    if "journal_entries" not in existing:
        op.create_table(
            "journal_entries",
            sa.Column("business_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("property_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("entry_date", sa.Date(), nullable=False),
            sa.Column("debit", sa.Numeric(14, 2), nullable=False),
            sa.Column("credit", sa.Numeric(14, 2), nullable=False),
            sa.Column("currency", sa.String(4), nullable=False),
            sa.Column("entry_type", sa.String(40), nullable=True),
            sa.Column("reference", sa.String(80), nullable=True),
            sa.Column("description", sa.String(255), nullable=True),
            sa.Column("source_type", sa.String(30), nullable=True),
            sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["property_id"], ["properties.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["account_id"], ["chart_of_accounts.id"], ondelete="RESTRICT"),
            sa.PrimaryKeyConstraint("id"),
        )
        for column in ("business_id", "property_id", "account_id", "entry_date", "entry_type", "reference", "source_type", "source_id", "id", "created_at"):
            op.create_index(f"ix_journal_entries_{column}", "journal_entries", [column])
        _record("table", "journal_entries")

    # A business may have at most one live subscription. Fail with a clear
    # remediation message instead of silently choosing which plan wins.
    subscription_indexes = {
        index["name"] for index in _inspector().get_indexes("business_subscriptions")
    }
    live_duplicates = bind.execute(sa.text("""
        SELECT business_id
        FROM business_subscriptions
        WHERE status IN ('active', 'trialing', 'past_due')
        GROUP BY business_id
        HAVING COUNT(*) > 1
        LIMIT 1
    """)).first()
    if live_duplicates:
        raise RuntimeError(
            "Cannot enforce one live subscription per business: duplicate live "
            "subscriptions exist. Resolve them before applying this migration."
        )
    live_index = "uq_business_subscriptions_one_live_per_business"
    if live_index not in subscription_indexes:
        op.create_index(
            live_index,
            "business_subscriptions",
            ["business_id"],
            unique=True,
            postgresql_where=sa.text("status IN ('active', 'trialing', 'past_due')"),
        )
        _record("index", live_index)

    # Existing installations may have these columns from an out-of-band
    # bootstrap. Add only what is missing and remember exactly what we add.
    business_columns = {c["name"] for c in _inspector().get_columns("businesses")}
    definitions = {
        "mpesa_consumer_key": sa.Text(),
        "mpesa_consumer_secret": sa.Text(),
        "mpesa_passkey": sa.Text(),
        "mpesa_shortcode": sa.String(20),
        "mpesa_callback_url": sa.Text(),
        "mpesa_env": sa.String(10),
    }
    for name, column_type in definitions.items():
        if name not in business_columns:
            nullable = name != "mpesa_env"
            server_default = sa.text("'sandbox'") if name == "mpesa_env" else None
            op.add_column(
                "businesses",
                sa.Column(name, column_type, nullable=nullable, server_default=server_default),
            )
            if name == "mpesa_env":
                op.alter_column("businesses", name, server_default=None)
            _record("column", f"businesses.{name}")
    # The temporary server default is removed after backfilling existing rows,
    # matching the model metadata and avoiding Alembic default drift.


def downgrade() -> None:
    bind = op.get_bind()
    rows = bind.execute(sa.text(f"SELECT object_type, object_name FROM {TRACKER}")).all()

    for kind, name in rows:
        if kind == "column":
            table, column = name.split(".", 1)
            op.drop_column(table, column)
        elif kind == "index":
            op.drop_index(name, table_name="business_subscriptions")

    # Drop in dependency order; only objects created by this migration are
    # removed. Tables present before the migration are never dropped.
    for table in ("journal_entries", "maintenance_tickets", "expenses", "chart_of_accounts"):
        if ("table", table) in rows:
            op.drop_table(table)

    op.drop_table(TRACKER)
