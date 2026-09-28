"""Expenses + harvests tables (farm economics ground truth).

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-25
"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op
from app.core.database import GUID

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "expenses",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("user_id", GUID(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("farm_id", GUID(), sa.ForeignKey("farms.id", ondelete="SET NULL")),
        sa.Column("category", sa.Text(), nullable=False),
        sa.Column("amount_inr", sa.Numeric(12, 2), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("spent_on", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_expenses_user_date", "expenses", ["user_id", "spent_on"])

    op.create_table(
        "harvests",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("user_id", GUID(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("farm_id", GUID(), sa.ForeignKey("farms.id", ondelete="SET NULL")),
        sa.Column("crop", sa.Text(), nullable=False),
        sa.Column("harvest_date", sa.Date()),
        sa.Column("actual_yield_quintals", sa.Numeric(12, 2)),
        sa.Column("selling_price_per_quintal", sa.Numeric(12, 2)),
        sa.Column("market_name", sa.Text()),
        sa.Column("revenue_inr", sa.Numeric(14, 2)),
        sa.Column("notes", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_harvests_user_date", "harvests", ["user_id", "harvest_date"])


def downgrade() -> None:
    op.drop_index("ix_harvests_user_date", table_name="harvests")
    op.drop_table("harvests")
    op.drop_index("ix_expenses_user_date", table_name="expenses")
    op.drop_table("expenses")
