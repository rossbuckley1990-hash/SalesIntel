"""Create source-backed corporate control relationships."""
from alembic import op
import sqlalchemy as sa
revision = '0013_market_relationships'
down_revision = '0012_market_network'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('market_relationships',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('subject_entity_id', sa.Integer, sa.ForeignKey('market_entities.id'), nullable=False),
        sa.Column('object_entity_id', sa.Integer, sa.ForeignKey('market_entities.id'), nullable=False),
        sa.Column('source_revision_id', sa.Integer, sa.ForeignKey('market_source_revisions.id'), nullable=False),
        sa.Column('relation_type', sa.String(80), nullable=False),
        sa.Column('effective_from', sa.DateTime(timezone=True)), sa.Column('effective_to', sa.DateTime(timezone=True)),
        sa.Column('observed_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('assertion_status', sa.String(40), nullable=False), sa.Column('evidence_excerpt', sa.Text, nullable=False),
        sa.UniqueConstraint('subject_entity_id','object_entity_id','relation_type','source_revision_id','effective_from', name='uq_market_relationship_assertion'))
    for col in ('subject_entity_id','object_entity_id','source_revision_id'):
        op.create_index('ix_market_relationships_'+col,'market_relationships',[col])

def downgrade():
    op.drop_table('market_relationships')
