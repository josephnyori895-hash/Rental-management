"""add mpesa_raw jsonb column to payments

Revision ID: a1b2c3d4e5f6
Revises: 8f53e6620282
Create Date: 2026-07-24 19:45:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '8f53e6620282'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('payments',
        sa.Column('mpesa_raw', postgresql.JSONB(astext_type=sa.Text()), nullable=True,
                  comment='Full M-Pesa callback metadata')
    )


def downgrade() -> None:
    op.drop_column('payments', 'mpesa_raw')
