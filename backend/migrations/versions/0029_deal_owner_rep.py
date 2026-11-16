"""Which rep owns a deal, by the name used for their patch brief and target. Local workspaces have no sign-in, so a deal's
owner is a rep's name; hosted workspaces keep using owner_user_id. Additive only: one nullable column.

Revision ID: 0029_deal_owner_rep
Revises: 0028_brief_reviews
"""
from alembic import op
import sqlalchemy as sa

revision = '0029_deal_owner_rep'
down_revision = '0028_brief_reviews'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('si_deals', sa.Column('owner_rep', sa.String(60), nullable=True))


def downgrade():
    with op.batch_alter_table('si_deals') as batch:
        batch.drop_column('owner_rep')
