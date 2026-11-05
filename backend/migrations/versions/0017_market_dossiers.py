"""Store deep-research dossiers for market opportunities.

Revision ID: 0017_market_dossiers
Revises: 0016_market_inference
"""
from alembic import op
import sqlalchemy as sa

revision = '0017_market_dossiers'
down_revision = '0016_market_inference'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('market_opportunity_dossiers', sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('opportunity_id', sa.Integer(), sa.ForeignKey('market_opportunities.id', ondelete='CASCADE'), nullable=False),
        sa.Column('revision_id', sa.Integer()), sa.Column('model', sa.String(80), nullable=False),
        sa.Column('result', sa.JSON(), nullable=False), sa.Column('created_at', sa.DateTime(timezone=True), nullable=False))
    op.create_index('ix_market_opportunity_dossiers_opportunity_id', 'market_opportunity_dossiers', ['opportunity_id'])


def downgrade():
    op.drop_index('ix_market_opportunity_dossiers_opportunity_id', 'market_opportunity_dossiers')
    op.drop_table('market_opportunity_dossiers')
