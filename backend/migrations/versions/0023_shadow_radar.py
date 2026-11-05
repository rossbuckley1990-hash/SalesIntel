"""Shadow Radar: observation provenance, shared hypotheses with immutable revisions, and per-workspace
dossiers and lead feedback (with row-level security on PostgreSQL). Additive only.

Revision ID: 0023_shadow_radar
Revises: 0022_row_level_security
"""
from alembic import op
import sqlalchemy as sa

from app.rls import statements

revision = '0023_shadow_radar'
down_revision = '0022_row_level_security'
branch_labels = None
depends_on = None

TS = lambda name, nullable=False: sa.Column(name, sa.DateTime(timezone=True), nullable=nullable)  # noqa: E731
ORG = lambda: sa.Column('organisation_id', sa.Integer(), sa.ForeignKey('organisations.id', ondelete='CASCADE'), nullable=False, index=True)  # noqa: E731


def upgrade():
    with op.batch_alter_table('market_observations') as batch:
        batch.add_column(sa.Column('retrieved_at', sa.DateTime(timezone=True)))
        batch.add_column(sa.Column('origin_key', sa.String(200)))
        batch.create_index('ix_market_observations_origin_key', ['origin_key'])
    op.create_table('shadow_hypotheses', sa.Column('id', sa.Integer(), primary_key=True), sa.Column('key', sa.String(320), nullable=False, unique=True),
                    sa.Column('sensor', sa.String(40), nullable=False, index=True), sa.Column('entity_name', sa.String(255), nullable=False),
                    sa.Column('entity_key', sa.String(200), nullable=False, index=True), sa.Column('company_number', sa.String(16)),
                    sa.Column('state', sa.String(16), nullable=False, index=True), sa.Column('first_published_on', sa.Date(), nullable=False),
                    TS('first_seen_at'), TS('formed_at'), sa.Column('window_start', sa.Date()), sa.Column('window_end', sa.Date()),
                    sa.Column('rule_version', sa.String(40), nullable=False), sa.Column('current_revision_id', sa.Integer()),
                    sa.Column('active', sa.Boolean(), nullable=False), TS('last_evaluated'))
    op.create_table('shadow_hypothesis_revisions', sa.Column('id', sa.Integer(), primary_key=True),
                    sa.Column('hypothesis_id', sa.Integer(), sa.ForeignKey('shadow_hypotheses.id', ondelete='CASCADE'), nullable=False, index=True),
                    sa.Column('fingerprint', sa.String(64), nullable=False), sa.Column('as_of', sa.Date(), nullable=False),
                    sa.Column('assessment', sa.JSON(), nullable=False), TS('created_at'), sa.UniqueConstraint('hypothesis_id', 'fingerprint', name='uq_shadow_revision'))
    op.create_table('si_dossiers', sa.Column('id', sa.Integer(), primary_key=True), ORG(),
                    sa.Column('account_id', sa.Integer(), sa.ForeignKey('si_accounts.id', ondelete='CASCADE'), nullable=False, index=True),
                    sa.Column('hypothesis_key', sa.String(320)), sa.Column('job_id', sa.Integer()), sa.Column('version', sa.Integer(), nullable=False),
                    sa.Column('plan', sa.JSON(), nullable=False), sa.Column('sections', sa.JSON(), nullable=False), sa.Column('challenge', sa.JSON(), nullable=False),
                    sa.Column('verdict', sa.String(16), nullable=False), sa.Column('sources', sa.JSON(), nullable=False), sa.Column('rejected', sa.JSON(), nullable=False),
                    sa.Column('cost_cents', sa.Integer(), nullable=False), TS('created_at'))
    op.create_table('si_lead_feedback', sa.Column('id', sa.Integer(), primary_key=True), ORG(), sa.Column('lead_key', sa.String(40), nullable=False, index=True),
                    sa.Column('sensor', sa.String(40), nullable=False), sa.Column('decision', sa.String(20), nullable=False), sa.Column('reason', sa.String(32), nullable=False),
                    sa.Column('note', sa.Text(), nullable=False), sa.Column('created_by', sa.Integer()), TS('created_at'))
    if op.get_bind().dialect.name == 'postgresql':
        for sql in statements(('si_dossiers', 'si_lead_feedback')):
            op.execute(sql)


def downgrade():
    if op.get_bind().dialect.name == 'postgresql':
        for table in ('si_dossiers', 'si_lead_feedback'):
            op.execute(f'DROP POLICY IF EXISTS si_workspace ON {table}')
    for table in ('si_lead_feedback', 'si_dossiers', 'shadow_hypothesis_revisions', 'shadow_hypotheses'):
        op.drop_table(table)
    with op.batch_alter_table('market_observations') as batch:
        batch.drop_index('ix_market_observations_origin_key')
        batch.drop_column('origin_key')
        batch.drop_column('retrieved_at')
