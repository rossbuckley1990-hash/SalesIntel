"""Persist public research snapshots and salesperson feedback."""
from alembic import op
import sqlalchemy as sa

revision = "0007_research_dossiers"
down_revision = "0006_public_site_references"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("saved_research_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("job_id", sa.String(64), nullable=False),
        sa.Column("brief", sa.Text(), nullable=False),
        sa.Column("model", sa.Text(), nullable=False),
        sa.Column("result", sa.JSON(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
    op.create_index("ix_saved_research_runs_job_id", "saved_research_runs", ["job_id"], unique=True)
    op.create_table("research_leads",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("run_id", sa.Integer(), sa.ForeignKey("saved_research_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("organisation", sa.Text(), nullable=False),
        sa.Column("location", sa.Text(), nullable=False),
        sa.Column("headline", sa.Text(), nullable=False),
        sa.Column("opportunity", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="new"),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("run_id", "position", name="uq_research_lead_run_position"))
    op.create_index("ix_research_leads_run_id", "research_leads", ["run_id"])
    op.create_index("ix_research_leads_status_id", "research_leads", ["status", "id"])
    op.create_table("research_lead_feedback",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("lead_id", sa.Integer(), sa.ForeignKey("research_leads.id", ondelete="CASCADE"), nullable=False),
        sa.Column("previous_status", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("feedback", sa.String(32), nullable=True),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
    op.create_index("ix_research_lead_feedback_lead_id", "research_lead_feedback", ["lead_id"])


def downgrade():
    op.drop_index("ix_research_lead_feedback_lead_id", table_name="research_lead_feedback")
    op.drop_table("research_lead_feedback")
    op.drop_index("ix_research_leads_status_id", table_name="research_leads")
    op.drop_index("ix_research_leads_run_id", table_name="research_leads")
    op.drop_table("research_leads")
    op.drop_index("ix_saved_research_runs_job_id", table_name="saved_research_runs")
    op.drop_table("saved_research_runs")
