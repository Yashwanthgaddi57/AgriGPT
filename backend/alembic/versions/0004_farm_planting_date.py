"""Add farms.planting_date (crop-age personalization).

Idempotent, like 0003.

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-25
"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels = None
depends_on = None

_COLUMNS = {
    "farms": [
        ("planting_date", "DATE"),
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
