"""Column facts and Backtest keys required, now no data from before them is kept

Revision ID: 0006
Revises: 0005
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Null only for a file uploaded before 0003, or a run trained before 0005; that data was
    # wiped when phase 1 was approved (2026-10-01), so every row has them.
    op.alter_column("uploaded_file", "column_facts", existing_type=sa.JSON(), nullable=False)
    op.alter_column("training_run", "backtest_key", existing_type=sa.String(255), nullable=False)


def downgrade() -> None:
    op.alter_column("training_run", "backtest_key", existing_type=sa.String(255), nullable=True)
    op.alter_column("uploaded_file", "column_facts", existing_type=sa.JSON(), nullable=True)
