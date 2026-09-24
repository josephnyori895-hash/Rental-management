"""create documents table + lease e-sign columns

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-07-24 20:30:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Documents table
    op.create_table('documents',
        sa.Column('business_id', sa.UUID(), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=True),
        sa.Column('lease_id', sa.UUID(), nullable=True),
        sa.Column('category', sa.String(length=30), nullable=False),
        sa.Column('original_name', sa.String(length=255), nullable=False),
        sa.Column('stored_name', sa.String(length=255), nullable=False),
        sa.Column('mime_type', sa.String(length=80), nullable=False),
        sa.Column('file_size', sa.Integer(), nullable=False),
        sa.Column('file_path', sa.Text(), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['business_id'], ['businesses.id'], name=op.f('fk_documents_business_id_businesses'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], name=op.f('fk_documents_tenant_id_tenants'), ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['lease_id'], ['leases.id'], name=op.f('fk_documents_lease_id_leases'), ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_documents'))
    )
    op.create_index(op.f('ix_documents_business_id'), 'documents', ['business_id'], unique=False)
    op.create_index(op.f('ix_documents_tenant_id'), 'documents', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_documents_lease_id'), 'documents', ['lease_id'], unique=False)

    # Lease e-sign columns
    op.add_column('leases',
        sa.Column('tenant_signed_at', sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column('leases',
        sa.Column('owner_signed_at', sa.DateTime(timezone=True), nullable=True)
    )


def downgrade() -> None:
    op.drop_column('leases', 'owner_signed_at')
    op.drop_column('leases', 'tenant_signed_at')
    op.drop_index(op.f('ix_documents_lease_id'), table_name='documents')
    op.drop_index(op.f('ix_documents_tenant_id'), table_name='documents')
    op.drop_index(op.f('ix_documents_business_id'), table_name='documents')
    op.drop_table('documents')
