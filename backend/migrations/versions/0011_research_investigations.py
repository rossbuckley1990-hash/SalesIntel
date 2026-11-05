"""Persist questions linking a saved lead to follow-up research."""
from alembic import op
import sqlalchemy as sa

revision = "0011_research_investigations"
down_revision = "0010_research_lead_actions"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("research_investigations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("lead_id", sa.Integer(), sa.ForeignKey("research_leads.id", ondelete="CASCADE"), nullable=False),
        sa.Column("job_id", sa.String(64), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
    op.create_index("ix_research_investigations_lead_id", "research_investigations", ["lead_id"])
    op.create_index("ix_research_investigations_job_id", "research_investigations", ["job_id"], unique=True)


def downgrade():
    op.drop_index("ix_research_investigations_job_id", table_name="research_investigations")
    op.drop_index("ix_research_investigations_lead_id", table_name="research_investigations")
    op.drop_table("research_investigations")
