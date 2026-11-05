"""Published site associations for cautious UPRN matching."""
from alembic import op
import sqlalchemy as sa

revision = "0006_public_site_references"
down_revision = "0005_lfb_incidents"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "public_site_references",
        sa.Column("source_record_id", sa.String(100), primary_key=True),
        sa.Column("uprn", sa.String(32), nullable=False),
        sa.Column("organisation_id", sa.String(80), nullable=False),
        sa.Column("organisation_name", sa.String(255), nullable=False),
        sa.Column("site_name", sa.String(255), nullable=False),
        sa.Column("postcode", sa.String(32), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("source_period", sa.String(40), nullable=False),
    )
    op.create_index("ix_public_site_references_uprn", "public_site_references", ["uprn"])


def downgrade():
    op.drop_index("ix_public_site_references_uprn", table_name="public_site_references")
    op.drop_table("public_site_references")
