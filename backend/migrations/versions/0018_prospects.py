"""Store private-sector prospects and the searches that found them.

Revision ID: 0018_prospects
Revises: 0017_market_dossiers
"""
from alembic import op
import sqlalchemy as sa

revision = '0018_prospects'
down_revision = '0017_market_dossiers'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('prospect_searches', sa.Column('id', sa.Integer(), primary_key=True), sa.Column('query', sa.Text(), nullable=False),
        sa.Column('mode', sa.String(16), nullable=False), sa.Column('status', sa.String(16), nullable=False), sa.Column('error', sa.Text()),
        sa.Column('model', sa.String(80), nullable=False), sa.Column('prospect_ids', sa.JSON(), nullable=False), sa.Column('sources_reviewed', sa.Integer(), nullable=False), sa.Column('target_prospect_id', sa.Integer()),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False), sa.Column('finished_at', sa.DateTime(timezone=True)))
    op.create_table('prospects', sa.Column('id', sa.Integer(), primary_key=True), sa.Column('dedup_key', sa.String(200), nullable=False, unique=True),
        sa.Column('name', sa.String(255), nullable=False), sa.Column('status', sa.String(16), nullable=False), sa.Column('data', sa.JSON(), nullable=False),
        sa.Column('search_id', sa.Integer()), sa.Column('opportunity_id', sa.Integer()),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False), sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False))


def downgrade():
    op.drop_table('prospects')
    op.drop_table('prospect_searches')
