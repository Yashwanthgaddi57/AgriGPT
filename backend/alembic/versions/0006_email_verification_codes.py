"""Email verification codes (app-issued signup codes).

Holds only SHA-256 hashes of the 6-digit codes, so the table itself cannot be
used to confirm an account.

Revision ID: 0006
Revises: 0005
Create Date: 2026-09-28
"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op
from app.core.database import GUID

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "email_verification_codes",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("code_hash", sa.Text(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("consumed_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_email_verification_codes_email", "email_verification_codes", ["email"])


def downgrade() -> None:
    op.drop_index("ix_email_verification_codes_email", table_name="email_verification_codes")
    op.drop_table("email_verification_codes")
