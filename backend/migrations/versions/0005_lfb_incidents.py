"""Record imported public LFB incident snapshots."""
from alembic import op
import sqlalchemy as sa

revision = "0005_lfb_incidents"
down_revision = "0004_evidence_observations"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("lfb_import_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("imported_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("source_url", sa.String(512), nullable=False),
        sa.Column("source_file", sa.String(255), nullable=False),
        sa.Column("acquisition_method", sa.String(30), nullable=False, server_default="local_file"),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("rows_seen", sa.Integer(), nullable=False),
        sa.Column("records_imported", sa.Integer(), nullable=False),
        sa.Column("rows_excluded", sa.Integer(), nullable=False),
        sa.Column("min_date", sa.Date(), nullable=True),
        sa.Column("max_date", sa.Date(), nullable=True),
    )
    op.create_table("lfb_incidents",
        sa.Column("incident_number", sa.String(80), primary_key=True),
        sa.Column("incident_date", sa.Date(), nullable=False),
        sa.Column("incident_group", sa.String(80), nullable=False),
        sa.Column("stop_code_description", sa.String(100), nullable=False),
        sa.Column("property_category", sa.String(100), nullable=False),
        sa.Column("property_type", sa.String(255), nullable=False),
        sa.Column("address_qualifier", sa.String(100), nullable=False),
        sa.Column("uprn", sa.String(20), nullable=False),
        sa.Column("postcode_district", sa.String(20), nullable=False),
        sa.Column("import_run_id", sa.Integer(), sa.ForeignKey("lfb_import_runs.id"), nullable=False),
    )
    op.create_index("ix_lfb_incidents_uprn_date", "lfb_incidents", ["uprn", "incident_date"])


def downgrade():
    op.drop_index("ix_lfb_incidents_uprn_date", table_name="lfb_incidents")
    op.drop_table("lfb_incidents")
    op.drop_table("lfb_import_runs")
