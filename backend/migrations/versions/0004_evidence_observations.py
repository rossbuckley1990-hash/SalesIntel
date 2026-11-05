"""Store importer-supplied, source-attributed observations."""
from alembic import op
import sqlalchemy as sa

revision = "0004_evidence_observations"
down_revision = "0003_action_details"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "evidence_observations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("fingerprint", sa.String(64), nullable=False, unique=True),
        sa.Column("organisation_id", sa.String(160), nullable=False),
        sa.Column("organisation_name", sa.String(255), nullable=False),
        sa.Column("site", sa.String(255), nullable=False),
        sa.Column("category", sa.String(40), nullable=False),
        sa.Column("observed_statement", sa.Text(), nullable=False),
        sa.Column("source_title", sa.String(255), nullable=False),
        sa.Column("source_reference", sa.String(512), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("published_at", sa.Date(), nullable=True),
        sa.Column("observed_at", sa.Date(), nullable=True),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_evidence_observations_org_id_id", "evidence_observations", ["organisation_id", "id"])


def downgrade():
    op.drop_index("ix_evidence_observations_org_id_id", table_name="evidence_observations")
    op.drop_table("evidence_observations")
