"""Persist public observations and the hypotheses inferred from them.

Revision ID: 0016_market_inference
Revises: 0015_market_contracts
"""
from alembic import op
import sqlalchemy as sa

revision = '0016_market_inference'
down_revision = '0015_market_contracts'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('market_observations', sa.Column('id', sa.Integer(), primary_key=True), sa.Column('fingerprint', sa.String(64), nullable=False, unique=True),
        sa.Column('signal_type', sa.String(48), nullable=False), sa.Column('scope', sa.String(16), nullable=False), sa.Column('buyer', sa.Text()), sa.Column('buyer_key', sa.String(200)),
        sa.Column('supplier', sa.Text()), sa.Column('supplier_key', sa.String(200)), sa.Column('company_number', sa.String(16)), sa.Column('families', sa.JSON(), nullable=False),
        sa.Column('statement', sa.Text(), nullable=False), sa.Column('occurred_on', sa.Date(), nullable=False), sa.Column('available_on', sa.Date(), nullable=False),
        sa.Column('source_group', sa.String(32), nullable=False), sa.Column('reliability', sa.String(24), nullable=False), sa.Column('attribution', sa.String(16), nullable=False),
        sa.Column('capture', sa.String(24), nullable=False), sa.Column('source_url', sa.Text(), nullable=False),
        sa.Column('source_revision_id', sa.Integer(), sa.ForeignKey('market_source_revisions.id', ondelete='SET NULL')), sa.Column('detail', sa.JSON(), nullable=False),
        sa.Column('first_seen', sa.DateTime(timezone=True), nullable=False), sa.Column('last_seen', sa.DateTime(timezone=True), nullable=False), sa.Column('retracted_on', sa.Date()))
    for name in ('signal_type', 'buyer_key', 'supplier_key', 'occurred_on', 'available_on'):
        op.create_index(f'ix_market_observations_{name}', 'market_observations', [name])
    op.create_table('market_hypotheses', sa.Column('id', sa.Integer(), primary_key=True), sa.Column('dedup_key', sa.String(320), nullable=False, unique=True), sa.Column('kind', sa.String(40), nullable=False),
        sa.Column('contract_id', sa.Integer(), sa.ForeignKey('market_contracts.id', ondelete='SET NULL')), sa.Column('buyer', sa.Text()), sa.Column('supplier', sa.Text()),
        sa.Column('decision', sa.String(16), nullable=False), sa.Column('evidence_state', sa.String(32), nullable=False), sa.Column('state', sa.String(16), nullable=False),
        sa.Column('current_revision_id', sa.Integer()), sa.Column('first_seen', sa.DateTime(timezone=True), nullable=False), sa.Column('last_evaluated', sa.DateTime(timezone=True), nullable=False))
    for name in ('kind', 'contract_id', 'decision', 'state'):
        op.create_index(f'ix_market_hypotheses_{name}', 'market_hypotheses', [name])
    op.create_table('market_hypothesis_revisions', sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('hypothesis_id', sa.Integer(), sa.ForeignKey('market_hypotheses.id', ondelete='CASCADE'), nullable=False), sa.Column('fingerprint', sa.String(64), nullable=False),
        sa.Column('assessment', sa.JSON(), nullable=False), sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('hypothesis_id', 'fingerprint', name='uq_market_hypothesis_fingerprint'))
    op.create_index('ix_market_hypothesis_revisions_hypothesis_id', 'market_hypothesis_revisions', ['hypothesis_id'])


def downgrade():
    op.drop_table('market_hypothesis_revisions')
    op.drop_table('market_hypotheses')
    op.drop_table('market_observations')
