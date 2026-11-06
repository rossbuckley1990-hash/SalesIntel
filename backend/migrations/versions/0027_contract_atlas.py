"""Contract Atlas: contractor identities, the names they appear under, their links to canonical contracts, identity
conflicts for review (shared public facts), and relationships reported by public sources (one workspace each, with
row-level security). Additive only.

Revision ID: 0027_contract_atlas
Revises: 0026_review_integrity
"""
from alembic import op
import sqlalchemy as sa

from app.rls import statements

revision = '0027_contract_atlas'
down_revision = '0026_review_integrity'
branch_labels = None
depends_on = None

TENANT = ('atlas_relationships',)


def upgrade():
    op.create_table('atlas_contractors', sa.Column('id', sa.Integer(), primary_key=True),
                    sa.Column('key', sa.String(320), nullable=False, unique=True), sa.Column('display_name', sa.String(255), nullable=False),
                    sa.Column('company_number', sa.String(16), index=True), sa.Column('identity_basis', sa.String(32), nullable=False),
                    sa.Column('group', sa.JSON(), nullable=False), sa.Column('disciplines', sa.JSON(), nullable=False),
                    sa.Column('nations', sa.JSON(), nullable=False), sa.Column('contract_count', sa.Integer(), nullable=False, server_default='0'),
                    sa.Column('first_seen', sa.DateTime(timezone=True), nullable=False), sa.Column('built_at', sa.DateTime(timezone=True), nullable=False))
    op.create_table('atlas_aliases', sa.Column('id', sa.Integer(), primary_key=True),
                    sa.Column('contractor_id', sa.Integer(), sa.ForeignKey('atlas_contractors.id', ondelete='CASCADE'), nullable=False, index=True),
                    sa.Column('alias', sa.String(255), nullable=False), sa.Column('normalised', sa.String(255), nullable=False, index=True),
                    sa.Column('source', sa.String(32), nullable=False), sa.Column('source_revision_id', sa.Integer()),
                    sa.UniqueConstraint('contractor_id', 'normalised', name='uq_atlas_alias'))
    op.create_table('atlas_contract_parties', sa.Column('id', sa.Integer(), primary_key=True),
                    sa.Column('contractor_id', sa.Integer(), sa.ForeignKey('atlas_contractors.id', ondelete='CASCADE'), nullable=False, index=True),
                    sa.Column('contract_id', sa.Integer(), sa.ForeignKey('market_contracts.id', ondelete='CASCADE'), nullable=False, index=True),
                    sa.Column('supplier_name_seen', sa.String(255), nullable=False), sa.Column('match_basis', sa.String(32), nullable=False),
                    sa.Column('customer_key', sa.String(255), nullable=False, index=True), sa.Column('region', sa.String(48), nullable=False, server_default=''),
                    sa.Column('disciplines', sa.JSON(), nullable=False), sa.Column('scope', sa.String(32), nullable=False),
                    sa.Column('route', sa.String(32), nullable=False),
                    sa.UniqueConstraint('contractor_id', 'contract_id', name='uq_atlas_contract_party'))
    op.create_table('atlas_identity_conflicts', sa.Column('id', sa.Integer(), primary_key=True),
                    sa.Column('normalised', sa.String(255), nullable=False, unique=True), sa.Column('kind', sa.String(24), nullable=False, server_default='two_numbers'),
                    sa.Column('names', sa.JSON(), nullable=False),
                    sa.Column('company_numbers', sa.JSON(), nullable=False), sa.Column('contractor_ids', sa.JSON(), nullable=False),
                    sa.Column('status', sa.String(16), nullable=False, server_default='unresolved'))
    op.create_table('atlas_relationships', sa.Column('id', sa.Integer(), primary_key=True),
                    sa.Column('organisation_id', sa.Integer(), sa.ForeignKey('organisations.id', ondelete='CASCADE'), nullable=False, index=True),
                    sa.Column('kind', sa.String(24), nullable=False), sa.Column('supplier_name', sa.String(255), nullable=False),
                    sa.Column('supplier_key', sa.String(255), nullable=False, index=True), sa.Column('contractor_id', sa.Integer(), index=True),
                    sa.Column('customer_name', sa.String(255), nullable=False), sa.Column('customer_key', sa.String(255), nullable=False, index=True),
                    sa.Column('intermediary', sa.String(255), nullable=False, server_default=''), sa.Column('services', sa.JSON(), nullable=False),
                    sa.Column('sites_mentioned', sa.Text(), nullable=False, server_default=''), sa.Column('published_on', sa.String(10), nullable=False, server_default=''),
                    sa.Column('duration_stated', sa.String(160), nullable=False, server_default=''), sa.Column('currency', sa.String(16), nullable=False),
                    sa.Column('source_url', sa.String(2048), nullable=False), sa.Column('source_title', sa.String(255), nullable=False, server_default=''),
                    sa.Column('source_type', sa.String(24), nullable=False), sa.Column('quote', sa.Text(), nullable=False),
                    sa.Column('quote_verified', sa.Boolean(), nullable=False, server_default=sa.false()), sa.Column('checks', sa.JSON(), nullable=False),
                    sa.Column('status', sa.String(16), nullable=False), sa.Column('unknowns', sa.JSON(), nullable=False), sa.Column('job_id', sa.Integer()),
                    sa.Column('first_seen', sa.DateTime(timezone=True), nullable=False), sa.Column('retrieved_at', sa.DateTime(timezone=True), nullable=False),
                    sa.UniqueConstraint('organisation_id', 'supplier_key', 'customer_key', 'source_url', name='uq_atlas_relationship'))
    if op.get_bind().dialect.name == 'postgresql':
        for sql in statements(TENANT):
            op.execute(sql)


def downgrade():
    if op.get_bind().dialect.name == 'postgresql':
        for t in TENANT:
            op.execute(f'DROP POLICY IF EXISTS si_workspace ON {t}')
    op.drop_table('atlas_relationships')
    op.drop_table('atlas_identity_conflicts')
    op.drop_table('atlas_contract_parties')
    op.drop_table('atlas_aliases')
    op.drop_table('atlas_contractors')
