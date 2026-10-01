"""Training runs

Revision ID: 0004
Revises: 0003
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "training_run",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("advertiser_id", sa.Uuid(), nullable=False),
        sa.Column("trained_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("model_key", sa.String(length=255), nullable=False),
        sa.ForeignKeyConstraint(["advertiser_id"], ["advertiser.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("training_run_advertiser_id", "training_run", ["advertiser_id", "trained_at"])


def downgrade() -> None:
    op.drop_index("training_run_advertiser_id", table_name="training_run")
    op.drop_table("training_run")
