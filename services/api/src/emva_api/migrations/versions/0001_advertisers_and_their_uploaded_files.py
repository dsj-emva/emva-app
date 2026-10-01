"""Advertisers and their uploaded files

Revision ID: 0001
Revises:
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "advertiser",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column(
            "data_source",
            sa.Enum("hand_made_test", "simulated", "public", "private", name="data_source"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "uploaded_file",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("advertiser_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.Enum("leads", "stage-history", name="file_kind"), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("object_key", sa.String(length=255), nullable=False),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=False),
        sa.Column("column_names", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(
            ["advertiser_id"],
            ["advertiser.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("advertiser_id", "kind"),
    )


def downgrade() -> None:
    op.drop_table("uploaded_file")
    op.drop_table("advertiser")
    sa.Enum(name="file_kind").drop(op.get_bind())
    sa.Enum(name="data_source").drop(op.get_bind())
