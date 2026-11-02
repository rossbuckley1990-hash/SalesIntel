"""Create a source-revisioned, conservative public market memory."""
from alembic import op
import sqlalchemy as sa

revision = '0012_market_network'
down_revision = '0011_research_investigations'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('market_source_states',
        sa.Column('source_key', sa.String(80), primary_key=True),
        sa.Column('last_checked_at', sa.DateTime(timezone=True)), sa.Column('last_success_at', sa.DateTime(timezone=True)),
        sa.Column('last_new_at', sa.DateTime(timezone=True)), sa.Column('lease_token', sa.String(64)),
        sa.Column('lease_until', sa.DateTime(timezone=True)), sa.Column('cursor', sa.Text()),
        sa.Column('watermark', sa.DateTime(timezone=True)), sa.Column('window_from', sa.DateTime(timezone=True)),
        sa.Column('window_to', sa.DateTime(timezone=True)), sa.Column('last_error', sa.Text()),
        sa.Column('failure_count', sa.Integer(), nullable=False, server_default='0'))
    op.create_table('market_source_revisions',
        sa.Column('id', sa.Integer(), primary_key=True), sa.Column('source_key', sa.String(80), nullable=False),
        sa.Column('record_key', sa.String(256), nullable=False), sa.Column('ocid', sa.String(256)),
        sa.Column('source_url', sa.Text(), nullable=False), sa.Column('content_hash', sa.String(64), nullable=False),
        sa.Column('raw', sa.JSON(), nullable=False), sa.Column('published_at', sa.DateTime(timezone=True)),
        sa.Column('retrieved_at', sa.DateTime(timezone=True), nullable=False), sa.Column('last_seen', sa.DateTime(timezone=True), nullable=False),
        sa.Column('superseded_at', sa.DateTime(timezone=True)))
    op.create_index('uq_market_source_current', 'market_source_revisions', ['source_key', 'record_key'],
                    unique=True, sqlite_where=sa.text('superseded_at IS NULL'),
                    postgresql_where=sa.text('superseded_at IS NULL'))
    for field in ('source_key','record_key','ocid'):
        op.create_index('ix_market_source_revisions_'+field, 'market_source_revisions', [field])
    op.create_table('market_entities',
        sa.Column('id', sa.Integer(), primary_key=True), sa.Column('name', sa.Text(), nullable=False),
        sa.Column('identifier_scheme', sa.String(128), nullable=False), sa.Column('identifier_value', sa.String(256), nullable=False),
        sa.Column('identity_status', sa.String(48), nullable=False), sa.Column('first_seen', sa.DateTime(timezone=True), nullable=False),
        sa.Column('last_seen', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('identifier_scheme', 'identifier_value', name='uq_market_entity_identifier'))
    op.create_table('market_awards',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('source_revision_id', sa.Integer(), sa.ForeignKey('market_source_revisions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('supplier_id', sa.Integer(), sa.ForeignKey('market_entities.id')),
        sa.Column('award_id', sa.String(256)), sa.Column('title', sa.Text(), nullable=False), sa.Column('buyer', sa.Text()),
        sa.Column('supplier', sa.Text()), sa.Column('status', sa.String(64)), sa.Column('award_date', sa.String(64)),
        sa.Column('amount', sa.String(64)), sa.Column('currency', sa.String(16)),
        sa.Column('classification', sa.String(32), nullable=False, server_default='unknown'))
    for field in ('source_revision_id','supplier_id'):
        op.create_index('ix_market_awards_'+field, 'market_awards', [field])
    op.create_table('market_entity_evidence',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('entity_id', sa.Integer(), sa.ForeignKey('market_entities.id'), nullable=False),
        sa.Column('source_revision_id', sa.Integer(), sa.ForeignKey('market_source_revisions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('assertion', sa.String(64), nullable=False),
        sa.UniqueConstraint('entity_id', 'source_revision_id', name='uq_market_entity_evidence'))
    for field in ('entity_id','source_revision_id'):
        op.create_index('ix_market_entity_evidence_'+field, 'market_entity_evidence', [field])


def downgrade():
    for name in ('market_entity_evidence','market_awards','market_entities','market_source_revisions','market_source_states'):
        op.drop_table(name)
