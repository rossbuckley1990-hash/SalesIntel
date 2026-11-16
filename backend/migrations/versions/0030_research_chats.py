"""Research chats: a rep's conversation with the research model. One workspace each, with row-level security.
Additive only: one new table.

Revision ID: 0030_research_chats
Revises: 0029_deal_owner_rep
"""
from alembic import op
import sqlalchemy as sa

from app.rls import statements

revision = '0030_research_chats'
down_revision = '0029_deal_owner_rep'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('si_research_chats', sa.Column('id', sa.Integer(), primary_key=True),
                    sa.Column('organisation_id', sa.Integer(), sa.ForeignKey('organisations.id', ondelete='CASCADE'), nullable=False, index=True),
                    sa.Column('title', sa.String(200), nullable=False), sa.Column('requested_by', sa.Integer()),
                    sa.Column('model', sa.String(80), nullable=False), sa.Column('system', sa.Text(), nullable=False),
                    sa.Column('tools', sa.JSON(), nullable=False), sa.Column('messages', sa.JSON(), nullable=False),
                    sa.Column('turns', sa.JSON(), nullable=False), sa.Column('cards', sa.JSON(), nullable=False),
                    sa.Column('sources', sa.JSON(), nullable=False), sa.Column('cost_cents', sa.Integer(), nullable=False),
                    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False), sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False))
    if op.get_bind().dialect.name == 'postgresql':
        for sql in statements(('si_research_chats',)):
            op.execute(sql)


def downgrade():
    if op.get_bind().dialect.name == 'postgresql':
        op.execute('DROP POLICY IF EXISTS si_workspace ON si_research_chats')
    op.drop_table('si_research_chats')
