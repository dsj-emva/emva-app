"""Each Training run's Backtest, kept in object storage

Revision ID: 0005
Revises: 0004
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Nullable: a run trained before Backtests were kept has none.
    op.add_column("training_run", sa.Column("backtest_key", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("training_run", "backtest_key")
