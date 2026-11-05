"""Store attributed, unverified public contact research for a lead."""
from alembic import op
import sqlalchemy as sa

revision = "0008_research_contact_snapshots"
down_revision = "0007_research_dossiers"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("research_contact_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("lead_id", sa.Integer(), sa.ForeignKey("research_leads.id", ondelete="CASCADE"), nullable=False),
        sa.Column("result", sa.JSON(), nullable=False),
        sa.Column("researched_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
    op.create_index("ix_research_contact_snapshots_lead_id", "research_contact_snapshots", ["lead_id"])


def downgrade():
    op.drop_index("ix_research_contact_snapshots_lead_id", table_name="research_contact_snapshots")
    op.drop_table("research_contact_snapshots")
