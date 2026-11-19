"""Create append-only platform administrator audit events.

Revision ID: 2c3d4e5f6a7b
Revises: 1b2c3d4e5f6a
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "2c3d4e5f6a7b"
down_revision: Union[str, None] = "1b2c3d4e5f6a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "platform_admin_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("admin_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("platform_admins.id", ondelete="SET NULL"), nullable=True),
        sa.Column("email_snapshot", sa.String(255), nullable=False),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("target_type", sa.String(100), nullable=True),
        sa.Column("target_id", sa.String(160), nullable=True),
        sa.Column("event_metadata", sa.JSON(), nullable=False),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.String(512), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_platform_admin_events_admin_id", "platform_admin_events", ["admin_id"])
    op.create_index("ix_platform_admin_event_actor_created", "platform_admin_events", ["admin_id", "created_at"])
    op.create_index("ix_platform_admin_event_action_created", "platform_admin_events", ["action", "created_at"])
    op.execute("""
        CREATE FUNCTION prevent_platform_admin_event_mutation()
        RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'platform admin audit events are append-only';
        END;
        $$ LANGUAGE plpgsql;
    """)
    op.execute("""
        CREATE TRIGGER platform_admin_events_append_only
        BEFORE UPDATE OR DELETE ON platform_admin_events
        FOR EACH ROW EXECUTE FUNCTION prevent_platform_admin_event_mutation();
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS platform_admin_events_append_only ON platform_admin_events")
    op.execute("DROP FUNCTION IF EXISTS prevent_platform_admin_event_mutation()")
    op.drop_table("platform_admin_events")
