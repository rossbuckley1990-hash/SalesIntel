"""Persist canonical contracts and how each source record links to them.

Revision ID: 0015_market_contracts
Revises: 0014_market_opportunities
"""
from alembic import op
import sqlalchemy as sa

revision = '0015_market_contracts'
down_revision = '0014_market_opportunities'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('market_contracts', sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('canonical_key', sa.String(300), nullable=False, unique=True), sa.Column('ocid', sa.String(256)),
        sa.Column('buyer', sa.Text(), nullable=False), sa.Column('supplier', sa.Text()), sa.Column('title', sa.Text(), nullable=False),
        sa.Column('fit', sa.String(16), nullable=False), sa.Column('nation', sa.String(32), nullable=False),
        sa.Column('lifecycle_status', sa.String(32), nullable=False), sa.Column('category', sa.String(32)),
        sa.Column('end_date', sa.String(10)), sa.Column('end_estimated', sa.Boolean(), nullable=False), sa.Column('facts', sa.JSON(), nullable=False),
        sa.Column('first_seen', sa.DateTime(timezone=True), nullable=False), sa.Column('last_evaluated', sa.DateTime(timezone=True), nullable=False),
        sa.Column('last_verified', sa.DateTime(timezone=True)))
    for name in ('ocid', 'nation', 'lifecycle_status', 'category', 'end_date'):
        op.create_index(f'ix_market_contracts_{name}', 'market_contracts', [name])
    op.create_table('market_contract_links', sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('contract_id', sa.Integer(), sa.ForeignKey('market_contracts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('member_key', sa.String(300), nullable=False, unique=True), sa.Column('source_key', sa.String(80), nullable=False),
        sa.Column('ocid', sa.String(256)), sa.Column('lot', sa.String(120), nullable=False), sa.Column('method', sa.Text(), nullable=False),
        sa.Column('confidence', sa.String(16), nullable=False), sa.Column('first_seen', sa.DateTime(timezone=True), nullable=False))
    op.create_index('ix_market_contract_links_contract_id', 'market_contract_links', ['contract_id'])
    op.create_index('ix_market_contract_links_ocid', 'market_contract_links', ['ocid'])


def downgrade():
    op.drop_table('market_contract_links')
    op.drop_table('market_contracts')
