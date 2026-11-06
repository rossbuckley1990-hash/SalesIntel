"""Evaluation integrity: reviewer identity and channel on decisions, adjudicated disagreements, and the open, locked or
revealed state of each review set. Additive only.

Revision ID: 0026_review_integrity
Revises: 0025_blind_review
"""
from alembic import op
import sqlalchemy as sa

from app.rls import statements

revision = '0026_review_integrity'
down_revision = '0025_blind_review'
branch_labels = None
depends_on = None

NEW = ('si_review_adjudications', 'si_review_states')


def _org():
    return sa.Column('organisation_id', sa.Integer(), sa.ForeignKey('organisations.id', ondelete='CASCADE'), nullable=False, index=True)


def upgrade():
    with op.batch_alter_table('si_review_decisions') as t:
        t.add_column(sa.Column('reviewer_name', sa.String(120), nullable=False, server_default=''))
        t.add_column(sa.Column('channel', sa.String(8), nullable=False, server_default='app'))
        t.add_column(sa.Column('submission_sha256', sa.String(64)))
    op.create_table('si_review_adjudications', sa.Column('id', sa.Integer(), primary_key=True), _org(),
                    sa.Column('set_key', sa.String(64), nullable=False, index=True), sa.Column('item_id', sa.String(16), nullable=False),
                    sa.Column('question', sa.String(16), nullable=False), sa.Column('answer', sa.String(24), nullable=False),
                    sa.Column('method', sa.String(16), nullable=False), sa.Column('adjudicator', sa.String(120), nullable=False),
                    sa.Column('rationale', sa.Text(), nullable=False), sa.Column('recorded_by', sa.Integer()),
                    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
                    sa.UniqueConstraint('organisation_id', 'set_key', 'item_id', 'question', name='uq_si_review_adjudication'))
    op.create_table('si_review_states', sa.Column('id', sa.Integer(), primary_key=True), _org(),
                    sa.Column('set_key', sa.String(64), nullable=False), sa.Column('status', sa.String(12), nullable=False, server_default='open'),
                    sa.Column('locked_at', sa.DateTime(timezone=True)), sa.Column('locked_by', sa.Integer()),
                    sa.Column('revealed_at', sa.DateTime(timezone=True)), sa.Column('revealed_by', sa.Integer()),
                    sa.Column('key', sa.JSON()), sa.Column('key_sha256', sa.String(64)),
                    sa.UniqueConstraint('organisation_id', 'set_key', name='uq_si_review_state'))
    if op.get_bind().dialect.name == 'postgresql':
        for sql in statements(NEW):
            op.execute(sql)


def downgrade():
    if op.get_bind().dialect.name == 'postgresql':
        for t in NEW:
            op.execute(f'DROP POLICY IF EXISTS si_workspace ON {t}')
    op.drop_table('si_review_states')
    op.drop_table('si_review_adjudications')
    with op.batch_alter_table('si_review_decisions') as t:
        t.drop_column('submission_sha256')
        t.drop_column('channel')
        t.drop_column('reviewer_name')
