"""create notification_log table

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-07-24 20:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('notification_log',
        sa.Column('business_id', sa.UUID(), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=True),
        sa.Column('channel', sa.String(length=20), nullable=False),
        sa.Column('recipient', sa.String(length=40), nullable=False),
        sa.Column('template_name', sa.String(length=80), nullable=True),
        sa.Column('subject', sa.String(length=200), nullable=True),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('provider', sa.String(length=30), nullable=False),
        sa.Column('provider_message_id', sa.String(length=120), nullable=True),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['business_id'], ['businesses.id'], name=op.f('fk_notification_log_business_id_businesses'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], name=op.f('fk_notification_log_tenant_id_tenants'), ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_notification_log'))
    )
    op.create_index(op.f('ix_notification_log_business_id'), 'notification_log', ['business_id'], unique=False)
    op.create_index(op.f('ix_notification_log_tenant_id'), 'notification_log', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_notification_log_status'), 'notification_log', ['status'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_notification_log_status'), table_name='notification_log')
    op.drop_index(op.f('ix_notification_log_tenant_id'), table_name='notification_log')
    op.drop_index(op.f('ix_notification_log_business_id'), table_name='notification_log')
    op.drop_table('notification_log')
