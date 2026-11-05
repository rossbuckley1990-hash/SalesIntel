"""Blind human review decisions for the opportunity-quality evaluation. Additive only.

Revision ID: 0025_blind_review
Revises: 0024_gaps_and_attribution
"""
from alembic import op
import sqlalchemy as sa

from app.rls import statements

revision = '0025_blind_review'
down_revision = '0024_gaps_and_attribution'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('si_review_decisions', sa.Column('id', sa.Integer(), primary_key=True),
                    sa.Column('organisation_id', sa.Integer(), sa.ForeignKey('organisations.id', ondelete='CASCADE'), nullable=False, index=True),
                    sa.Column('set_key', sa.String(64), nullable=False, index=True), sa.Column('item_id', sa.String(16), nullable=False),
                    sa.Column('reviewer', sa.Integer(), nullable=False), sa.Column('answers', sa.JSON(), nullable=False), sa.Column('minutes', sa.Integer()),
                    sa.Column('note', sa.Text(), nullable=False), sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
                    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
                    sa.UniqueConstraint('organisation_id', 'set_key', 'item_id', 'reviewer', name='uq_si_review_decision'))
    if op.get_bind().dialect.name == 'postgresql':
        for sql in statements(('si_review_decisions',)):
            op.execute(sql)


def downgrade():
    if op.get_bind().dialect.name == 'postgresql':
        op.execute('DROP POLICY IF EXISTS si_workspace ON si_review_decisions')
    op.drop_table('si_review_decisions')
