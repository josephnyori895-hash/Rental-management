"""create utility_rates and meter_readings tables

Utility/service-charge billing: a tariff (with apportionment rule) per
property or unit, and the meter readings recorded against them.

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-09-30 10:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'e5f6a7b8c9d0'
down_revision: Union[str, None] = 'd4e5f6a7b8c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('utility_rates',
        sa.Column('business_id', sa.UUID(), nullable=False),
        sa.Column('property_id', sa.UUID(), nullable=False),
        sa.Column('unit_id', sa.UUID(), nullable=True, comment='NULL = property-wide default tariff'),
        sa.Column('utility_type', sa.String(length=24), nullable=False),
        sa.Column('label', sa.String(length=80), nullable=True),
        sa.Column('rate_per_unit', sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column('fixed_charge', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('split_method', sa.String(length=16), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['business_id'], ['businesses.id'], name=op.f('fk_utility_rates_business_id_businesses'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['property_id'], ['properties.id'], name=op.f('fk_utility_rates_property_id_properties'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['unit_id'], ['units.id'], name=op.f('fk_utility_rates_unit_id_units'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_utility_rates'))
    )
    op.create_index(op.f('ix_utility_rates_business_id'), 'utility_rates', ['business_id'], unique=False)
    op.create_index(op.f('ix_utility_rates_property_id'), 'utility_rates', ['property_id'], unique=False)
    op.create_index(op.f('ix_utility_rates_unit_id'), 'utility_rates', ['unit_id'], unique=False)
    op.create_index(op.f('ix_utility_rates_utility_type'), 'utility_rates', ['utility_type'], unique=False)
    op.create_index(op.f('ix_utility_rates_is_active'), 'utility_rates', ['is_active'], unique=False)

    op.create_table('meter_readings',
        sa.Column('business_id', sa.UUID(), nullable=False),
        sa.Column('property_id', sa.UUID(), nullable=False),
        sa.Column('unit_id', sa.UUID(), nullable=True, comment='NULL = bulk/shared meter for the whole property'),
        sa.Column('utility_type', sa.String(length=24), nullable=False),
        sa.Column('reading_date', sa.Date(), nullable=False),
        sa.Column('previous_reading', sa.Numeric(precision=14, scale=3), nullable=True, comment='NULL on the first (baseline) reading'),
        sa.Column('current_reading', sa.Numeric(precision=14, scale=3), nullable=False),
        sa.Column('units_consumed', sa.Numeric(precision=14, scale=3), nullable=False),
        sa.Column('rate_per_unit', sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column('fixed_charge', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('amount', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('invoice_id', sa.UUID(), nullable=True, comment='The invoice this reading produced, if it was billed'),
        sa.Column('source', sa.String(length=16), nullable=False),
        sa.Column('recorded_by', sa.UUID(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['business_id'], ['businesses.id'], name=op.f('fk_meter_readings_business_id_businesses'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['property_id'], ['properties.id'], name=op.f('fk_meter_readings_property_id_properties'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['unit_id'], ['units.id'], name=op.f('fk_meter_readings_unit_id_units'), ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['invoice_id'], ['invoices.id'], name=op.f('fk_meter_readings_invoice_id_invoices'), ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['recorded_by'], ['users.id'], name=op.f('fk_meter_readings_recorded_by_users'), ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_meter_readings'))
    )
    op.create_index(op.f('ix_meter_readings_business_id'), 'meter_readings', ['business_id'], unique=False)
    op.create_index(op.f('ix_meter_readings_property_id'), 'meter_readings', ['property_id'], unique=False)
    op.create_index(op.f('ix_meter_readings_unit_id'), 'meter_readings', ['unit_id'], unique=False)
    op.create_index(op.f('ix_meter_readings_utility_type'), 'meter_readings', ['utility_type'], unique=False)
    op.create_index(op.f('ix_meter_readings_reading_date'), 'meter_readings', ['reading_date'], unique=False)
    op.create_index(op.f('ix_meter_readings_invoice_id'), 'meter_readings', ['invoice_id'], unique=False)
    op.create_index('ix_meter_readings_scope', 'meter_readings', ['business_id', 'property_id', 'utility_type', 'reading_date'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_meter_readings_scope', table_name='meter_readings')
    op.drop_index(op.f('ix_meter_readings_invoice_id'), table_name='meter_readings')
    op.drop_index(op.f('ix_meter_readings_reading_date'), table_name='meter_readings')
    op.drop_index(op.f('ix_meter_readings_utility_type'), table_name='meter_readings')
    op.drop_index(op.f('ix_meter_readings_unit_id'), table_name='meter_readings')
    op.drop_index(op.f('ix_meter_readings_property_id'), table_name='meter_readings')
    op.drop_index(op.f('ix_meter_readings_business_id'), table_name='meter_readings')
    op.drop_table('meter_readings')

    op.drop_index(op.f('ix_utility_rates_is_active'), table_name='utility_rates')
    op.drop_index(op.f('ix_utility_rates_utility_type'), table_name='utility_rates')
    op.drop_index(op.f('ix_utility_rates_unit_id'), table_name='utility_rates')
    op.drop_index(op.f('ix_utility_rates_property_id'), table_name='utility_rates')
    op.drop_index(op.f('ix_utility_rates_business_id'), table_name='utility_rates')
    op.drop_table('utility_rates')
