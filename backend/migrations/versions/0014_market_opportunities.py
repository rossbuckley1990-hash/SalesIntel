"""Persist reviewable, source-linked market opportunity suggestions.

Revision ID: 0014_market_opportunities
Revises: 0013_market_relationships
"""
from alembic import op
import sqlalchemy as sa

revision = '0014_market_opportunities'
down_revision = '0013_market_relationships'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('market_opportunities', sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('dedup_key', sa.String(256), nullable=False, unique=True),
        sa.Column('state', sa.String(32), nullable=False), sa.Column('review_state', sa.String(32), nullable=False),
        # A deferred FK would make SQLite table creation and teardown cyclic.
        sa.Column('current_revision_id', sa.Integer(), nullable=True),
        sa.Column('first_seen', sa.DateTime(timezone=True), nullable=False),
        sa.Column('last_evaluated', sa.DateTime(timezone=True), nullable=False),
        sa.Column('withdrawal_reason', sa.Text()))
    op.create_table('market_opportunity_revisions', sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('opportunity_id', sa.Integer(), sa.ForeignKey('market_opportunities.id', ondelete='CASCADE'), nullable=False),
        sa.Column('fingerprint', sa.String(64), nullable=False), sa.Column('result', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('opportunity_id', 'fingerprint', name='uq_market_opportunity_fingerprint'))
    op.create_index('ix_market_opportunity_revisions_opportunity_id', 'market_opportunity_revisions', ['opportunity_id'])


def downgrade():
    op.drop_index('ix_market_opportunity_revisions_opportunity_id', table_name='market_opportunity_revisions')
    op.drop_table('market_opportunity_revisions')
    op.drop_table('market_opportunities')
