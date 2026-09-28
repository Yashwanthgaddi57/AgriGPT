"""Add users.plan (free|pro|cooperative) and disease follow-up fields.

Idempotent: every ADD COLUMN is guarded by a catalog check, so it can be
applied twice or on a database the startup auto-migration already patched.

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-25
"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels = None
depends_on = None

_TABLE = "users"
_COLUMNS = {
    "users": [
        ("plan", "VARCHAR(20) NOT NULL DEFAULT 'free'"),
    ],
    "disease_reports": [
        ("alternatives", "JSONB"),
        ("followup_status", "VARCHAR(30)"),
        ("notes", "TEXT"),
    ],
}


def _existing_columns(conn, table: str) -> set[str]:
    from sqlalchemy import inspect

    return {c["name"] for c in inspect(conn).get_columns(table)}


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    for table, cols in _COLUMNS.items():
        if not inspector.has_table(table):
            continue
        existing = _existing_columns(conn, table)
        for name, ddl in cols:
            if name in existing:
                continue
            conn.exec_driver_sql(f'ALTER TABLE "{table}" ADD COLUMN "{name}" {ddl}')


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    for table, cols in _COLUMNS.items():
        if not inspector.has_table(table):
            continue
        existing = _existing_columns(conn, table)
        for name, _ddl in cols:
            if name in existing:
                conn.exec_driver_sql(f'ALTER TABLE "{table}" DROP COLUMN "{name}"')
