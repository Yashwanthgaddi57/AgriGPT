"""Add market_predictions.data_source and source_meta

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-23
"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("market_predictions", sa.Column("data_source", sa.Text(), nullable=True))
    op.add_column(
        "market_predictions",
        sa.Column("source_meta", postgresql.JSONB, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("market_predictions", "source_meta")
    op.drop_column("market_predictions", "data_source")
