"""Add validated action dependencies and durable completion references."""

from alembic import op
import sqlalchemy as sa

revision = "0003_action_details"
down_revision = "0002_living"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "living_action_details",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "action_id",
            sa.Integer(),
            sa.ForeignKey("executive_actions.id"),
            nullable=False,
            unique=True,
        ),
        sa.Column("depends_on", sa.JSON(), nullable=False),
        sa.Column("completion_evidence", sa.Text(), nullable=False),
    )


def downgrade():
    op.drop_table("living_action_details")
