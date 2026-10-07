"""Nearby agri-services directory: extra vendor fields, dedup key and indexes.

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-06
"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels = None
depends_on = None

# column name -> DDL type. Ratings stay NULL unless a real provider supplies one.
_NEW_COLUMNS: dict[str, str] = {
    "subcategory": "VARCHAR(60)",
    "website": "TEXT",
    "pincode": "VARCHAR(12)",
    "rating": "NUMERIC(3, 1)",
    "review_count": "INTEGER",
    "opening_hours": "TEXT",
    "source": "VARCHAR(40)",
    "source_id": "VARCHAR(80)",
    "last_updated": "TIMESTAMP",
    "updated_at": "TIMESTAMP",
}

_INDEXES: list[tuple[str, list[str], bool]] = [
    ("ix_vendors_category", ["category"], False),
    ("ix_vendors_district", ["district"], False),
    ("ix_vendors_state", ["state"], False),
    ("ix_vendors_latitude", ["latitude"], False),
    ("ix_vendors_longitude", ["longitude"], False),
    # Stable identity so re-importing the same source record updates in place.
    ("uq_vendors_source", ["source", "source_id"], True),
]


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = {c["name"] for c in inspector.get_columns("vendors")}

    # Additive only — a fresh database built by Base.metadata.create_all already
    # has these columns, so this converges either way.
    for name, ddl_type in _NEW_COLUMNS.items():
        if name not in existing:
            op.execute(f'ALTER TABLE "vendors" ADD COLUMN "{name}" {ddl_type}')

    existing_indexes = {ix["name"] for ix in inspector.get_indexes("vendors")}
    for name, cols, unique in _INDEXES:
        if name in existing_indexes:
            continue
        op.create_index(
            name,
            "vendors",
            cols,
            unique=unique,
            postgresql_using="btree",
        )


def downgrade() -> None:
    for name, _cols, _unique in reversed(_INDEXES):
        op.execute(f'DROP INDEX IF EXISTS "{name}"')
    for name in reversed(list(_NEW_COLUMNS)):
        op.execute(f'ALTER TABLE "vendors" DROP COLUMN IF EXISTS "{name}"')
