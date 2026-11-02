"""Store user-selected research follow-ups independently of CRM pursuits."""
from alembic import op
import sqlalchemy as sa

revision = "0010_research_lead_actions"
down_revision = "0009_lfb_inspection_matches"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("research_lead_actions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("lead_id", sa.Integer(), sa.ForeignKey("research_leads.id", ondelete="CASCADE"), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="open"),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
    op.create_index("ix_research_lead_actions_lead_id", "research_lead_actions", ["lead_id"])


def downgrade():
    op.drop_index("ix_research_lead_actions_lead_id", table_name="research_lead_actions")
    op.drop_table("research_lead_actions")
