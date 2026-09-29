"""Password reset tokens table (app-issued reset links).

Revision ID: 0007
Revises: 0006
Create Date: 2026-09-28
"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op
from app.core.database import GUID

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "password_reset_tokens",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("token_hash", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("consumed_at", sa.DateTime(timezone=True)),
    )
    op.create_index("idx_password_reset_tokens_email", "password_reset_tokens", ["email"])


def downgrade() -> None:
    op.drop_index("idx_password_reset_tokens_email", table_name="password_reset_tokens")
    op.drop_table("password_reset_tokens")
