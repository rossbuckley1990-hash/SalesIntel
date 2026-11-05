"""Durable research jobs, AI spending limits, idempotent writes, the suppression list and
Contact Navigator evidence on contacts. Additive only.

Revision ID: 0021_acquisition_engine
Revises: 0020_workspaces_and_tenancy
"""
from alembic import op
import sqlalchemy as sa

revision = '0021_acquisition_engine'
down_revision = '0020_workspaces_and_tenancy'
branch_labels = None
depends_on = None

TS = lambda name, nullable=False: sa.Column(name, sa.DateTime(timezone=True), nullable=nullable)  # noqa: E731
ORG = lambda: sa.Column('organisation_id', sa.Integer(), sa.ForeignKey('organisations.id', ondelete='CASCADE'), nullable=False, index=True)  # noqa: E731
CONTACT_COLUMNS = [('role_category', sa.String(16), ''), ('route_kind', sa.String(24), ''), ('quality', sa.String(20), ''), ('verification_method', sa.Text(), ''),
                   ('provider', sa.String(40), ''), ('use_restriction', sa.Text(), '')]


def upgrade():
    op.create_table('si_research_jobs', sa.Column('id', sa.Integer(), primary_key=True), ORG(), sa.Column('requested_by', sa.Integer(), index=True),
                    sa.Column('kind', sa.String(32), nullable=False), sa.Column('account_id', sa.Integer(), index=True), sa.Column('params', sa.JSON(), nullable=False),
                    sa.Column('status', sa.String(16), nullable=False, index=True), sa.Column('stage', sa.String(120), nullable=False),
                    sa.Column('attempts', sa.Integer(), nullable=False), sa.Column('max_attempts', sa.Integer(), nullable=False), TS('next_run_at'),
                    sa.Column('lease_token', sa.String(40)), TS('lease_until', True), sa.Column('cancel_requested', sa.Boolean(), nullable=False),
                    sa.Column('estimated_cents', sa.Integer(), nullable=False), sa.Column('reserved_cents', sa.Integer(), nullable=False),
                    sa.Column('actual_cents', sa.Integer(), nullable=False), sa.Column('usage', sa.JSON(), nullable=False), sa.Column('result', sa.JSON(), nullable=False),
                    sa.Column('error', sa.Text(), nullable=False), TS('created_at'), TS('started_at', True), TS('finished_at', True), TS('updated_at'))
    op.create_table('si_spend_budgets', sa.Column('id', sa.Integer(), primary_key=True), ORG(), sa.Column('user_id', sa.Integer(), nullable=False),
                    sa.Column('day', sa.Date(), nullable=False), sa.Column('limit_cents', sa.Integer(), nullable=False), sa.Column('reserved_cents', sa.Integer(), nullable=False),
                    sa.Column('spent_cents', sa.Integer(), nullable=False), sa.UniqueConstraint('organisation_id', 'user_id', 'day', name='uq_si_spend_day'))
    op.create_table('si_idempotency', sa.Column('id', sa.Integer(), primary_key=True), ORG(), sa.Column('key', sa.String(80), nullable=False),
                    sa.Column('endpoint', sa.String(160), nullable=False), sa.Column('request_hash', sa.String(64), nullable=False), sa.Column('status', sa.String(12), nullable=False),
                    sa.Column('status_code', sa.Integer()), sa.Column('response', sa.JSON()), TS('created_at'),
                    sa.UniqueConstraint('organisation_id', 'key', name='uq_si_idempotency_key'))
    op.create_table('si_suppressions', sa.Column('id', sa.Integer(), primary_key=True), ORG(), sa.Column('kind', sa.String(12), nullable=False),
                    sa.Column('value_hash', sa.String(64), nullable=False), sa.Column('reason', sa.String(120), nullable=False), sa.Column('created_by', sa.Integer()),
                    TS('created_at'), sa.UniqueConstraint('organisation_id', 'kind', 'value_hash', name='uq_si_suppression'))
    with op.batch_alter_table('si_contacts') as batch:
        for name, kind, default in CONTACT_COLUMNS:
            batch.add_column(sa.Column(name, kind, nullable=False, server_default=default))
        batch.add_column(sa.Column('verified_at', sa.DateTime(timezone=True)))
        batch.add_column(sa.Column('source_date', sa.String(10)))
        batch.add_column(sa.Column('flags', sa.JSON(), nullable=False, server_default='[]'))
    # Keep the database defaults out of the schema the models describe: the application sets these values.
    with op.batch_alter_table('si_contacts') as batch:
        for name, kind, _ in CONTACT_COLUMNS:
            batch.alter_column(name, existing_type=kind, server_default=None)
        batch.alter_column('flags', existing_type=sa.JSON(), server_default=None)


def downgrade():
    with op.batch_alter_table('si_contacts') as batch:
        for name in [c[0] for c in CONTACT_COLUMNS] + ['verified_at', 'source_date', 'flags']:
            batch.drop_column(name)
    for table in ('si_suppressions', 'si_idempotency', 'si_spend_budgets', 'si_research_jobs'):
        op.drop_table(table)
