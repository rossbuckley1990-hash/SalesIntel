"""Research on demand (gap requests) and acquisition-to-revenue attribution on the funnel record. Additive only.

Revision ID: 0024_gaps_and_attribution
Revises: 0023_shadow_radar
"""
from alembic import op
import sqlalchemy as sa

from app.rls import statements

revision = '0024_gaps_and_attribution'
down_revision = '0023_shadow_radar'
branch_labels = None
depends_on = None

TS = lambda name, nullable=False: sa.Column(name, sa.DateTime(timezone=True), nullable=nullable)  # noqa: E731


def upgrade():
    with op.batch_alter_table('si_funnel_events') as batch:
        batch.add_column(sa.Column('at', sa.DateTime(timezone=True)))
        batch.add_column(sa.Column('account_id', sa.Integer()))
        batch.add_column(sa.Column('deal_id', sa.Integer()))
        batch.add_column(sa.Column('ref', sa.String(48)))
        batch.add_column(sa.Column('origin', sa.String(48)))
        batch.add_column(sa.Column('source_type', sa.String(16)))
        batch.add_column(sa.Column('amount', sa.Float()))
        batch.add_column(sa.Column('amount_basis', sa.String(32)))
        batch.create_index('ix_si_funnel_events_account_id', ['account_id'])
    op.create_table('si_gap_requests', sa.Column('id', sa.Integer(), primary_key=True),
                    sa.Column('organisation_id', sa.Integer(), sa.ForeignKey('organisations.id', ondelete='CASCADE'), nullable=False, index=True),
                    sa.Column('account_id', sa.Integer(), sa.ForeignKey('si_accounts.id', ondelete='CASCADE'), nullable=False, index=True),
                    sa.Column('gap', sa.String(32), nullable=False), sa.Column('subject', sa.String(160), nullable=False), sa.Column('question', sa.Text(), nullable=False),
                    sa.Column('lead_key', sa.String(40)), sa.Column('status', sa.String(24), nullable=False), sa.Column('summary', sa.Text(), nullable=False),
                    sa.Column('findings', sa.JSON(), nullable=False), sa.Column('rejected', sa.JSON(), nullable=False), sa.Column('sources', sa.Integer(), nullable=False),
                    sa.Column('job_id', sa.Integer()), sa.Column('cost_cents', sa.Integer(), nullable=False), sa.Column('created_by', sa.Integer()),
                    TS('created_at'), TS('resolved_at', True))
    if op.get_bind().dialect.name == 'postgresql':
        for sql in statements(('si_gap_requests',)):
            op.execute(sql)


def downgrade():
    if op.get_bind().dialect.name == 'postgresql':
        op.execute('DROP POLICY IF EXISTS si_workspace ON si_gap_requests')
    op.drop_table('si_gap_requests')
    with op.batch_alter_table('si_funnel_events') as batch:
        batch.drop_index('ix_si_funnel_events_account_id')
        for column in ('amount_basis', 'amount', 'source_type', 'origin', 'ref', 'deal_id', 'account_id', 'at'):
            batch.drop_column(column)
