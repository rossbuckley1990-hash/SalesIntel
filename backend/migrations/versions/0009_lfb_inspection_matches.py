"""Candidate public inspection-to-site links."""
from alembic import op
import sqlalchemy as sa

revision = "0009_lfb_inspection_matches"
down_revision = "0008_research_contact_snapshots"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("lfb_inspection_matches",
        sa.Column("fingerprint", sa.String(64), primary_key=True),
        sa.Column("uprn", sa.String(32), nullable=False),
        sa.Column("organisation_name", sa.String(255), nullable=False),
        sa.Column("site_name", sa.String(255), nullable=False),
        sa.Column("site_reference_url", sa.Text(), nullable=False),
        sa.Column("site_reference_period", sa.String(40), nullable=False),
        sa.Column("postcode", sa.String(32), nullable=False),
        sa.Column("inspection_address", sa.Text(), nullable=False),
        sa.Column("property_use", sa.String(255), nullable=False),
        sa.Column("reason_or_outcome", sa.String(255), nullable=False),
        sa.Column("completed_on", sa.Date(), nullable=False),
        sa.Column("source_file", sa.String(255), nullable=False),
        sa.Column("source_sha256", sa.String(64), nullable=False),
        sa.Column("imported_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_index("ix_lfb_inspection_matches_uprn", "lfb_inspection_matches", ["uprn"])

def downgrade():
    op.drop_index("ix_lfb_inspection_matches_uprn", table_name="lfb_inspection_matches")
    op.drop_table("lfb_inspection_matches")
