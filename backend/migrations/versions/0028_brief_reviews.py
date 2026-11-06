"""When someone last reviewed an opportunity (for "new since your last review"). One workspace each, with row-level
security. Additive only.

Revision ID: 0028_brief_reviews
Revises: 0027_contract_atlas
"""
from alembic import op
import sqlalchemy as sa

from app.rls import statements

revision = '0028_brief_reviews'
down_revision = '0027_contract_atlas'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('si_brief_reviews', sa.Column('id', sa.Integer(), primary_key=True),
                    sa.Column('organisation_id', sa.Integer(), sa.ForeignKey('organisations.id', ondelete='CASCADE'), nullable=False, index=True),
                    sa.Column('key', sa.String(40), nullable=False, index=True), sa.Column('user_id', sa.Integer()),
                    sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=False),
                    sa.UniqueConstraint('organisation_id', 'key', 'user_id', name='uq_si_brief_review'))
    if op.get_bind().dialect.name == 'postgresql':
        for sql in statements(('si_brief_reviews',)):
            op.execute(sql)


def downgrade():
    if op.get_bind().dialect.name == 'postgresql':
        op.execute('DROP POLICY IF EXISTS si_workspace ON si_brief_reviews')
    op.drop_table('si_brief_reviews')
