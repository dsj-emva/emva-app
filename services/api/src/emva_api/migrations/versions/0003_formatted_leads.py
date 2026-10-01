"""Formatted leads, their stage events and the summary; raw uploads deleted; column facts

Revision ID: 0003
Revises: 0002
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

STAGE_OR_LOST = sa.Enum(
    "submitted",
    "contact_attempted",
    "engaged",
    "qualified",
    "proposal",
    "won",
    "lost",
    name="stage_or_lost",
)


def upgrade() -> None:
    op.alter_column("uploaded_file", "object_key", existing_type=sa.String(255), nullable=True)
    op.add_column("uploaded_file", sa.Column("column_facts", sa.JSON(), nullable=True))
    op.create_table(
        "lead",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("advertiser_id", sa.Uuid(), nullable=False),
        sa.Column("identifier_hash", sa.String(length=64), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("email_hash", sa.String(length=64), nullable=True),
        sa.Column("phone_hash", sa.String(length=64), nullable=True),
        sa.Column("number_inputs", sa.JSON(), nullable=False),
        sa.Column("category_inputs", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["advertiser_id"], ["advertiser.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("advertiser_id", "identifier_hash"),
    )
    op.create_table(
        "stage_event",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("lead_id", sa.Uuid(), nullable=False),
        sa.Column("stage", STAGE_OR_LOST, nullable=False),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deal_value", sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(["lead_id"], ["lead.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("stage_event_lead_id", "stage_event", ["lead_id"])
    op.create_table(
        "formatting",
        sa.Column("advertiser_id", sa.Uuid(), nullable=False),
        sa.Column("formatted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("summary", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["advertiser_id"], ["advertiser.id"]),
        sa.PrimaryKeyConstraint("advertiser_id"),
    )


def downgrade() -> None:
    op.drop_table("formatting")
    op.drop_index("stage_event_lead_id", table_name="stage_event")
    op.drop_table("stage_event")
    op.drop_table("lead")
    STAGE_OR_LOST.drop(op.get_bind())
    op.drop_column("uploaded_file", "column_facts")
    op.alter_column("uploaded_file", "object_key", existing_type=sa.String(255), nullable=False)
