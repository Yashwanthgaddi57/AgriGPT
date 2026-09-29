"""Payments table for Razorpay checkout records.

Revision ID: 0008
Revises: 0007
Create Date: 2026-09-29
"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op
from app.core.database import GUID

revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "payments",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("user_id", GUID(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("plan", sa.String(length=20), nullable=False),
        sa.Column("amount_inr", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=10), nullable=False, server_default="INR"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="created"),
        sa.Column("razorpay_order_id", sa.Text(), nullable=False, unique=True),
        sa.Column("razorpay_payment_id", sa.Text(), unique=True),
        sa.Column("razorpay_signature", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("paid_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_payments_user_id", "payments", ["user_id"])
    op.create_index("idx_payments_status", "payments", ["status"])


def downgrade() -> None:
    op.drop_index("idx_payments_status", table_name="payments")
    op.drop_index("idx_payments_user_id", table_name="payments")
    op.drop_table("payments")
