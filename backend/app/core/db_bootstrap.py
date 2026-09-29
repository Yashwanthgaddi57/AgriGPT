"""Idempotent database bootstrap for container boots (Render, Docker).

Replaces a blind `alembic upgrade head` at boot, which crash-loops when the
database was provisioned by supabase/schema.sql (or an older deploy) and has
tables but no alembic_version stamp. Strategy, in order:

  1. Base.metadata.create_all — creates ONLY missing tables. The models are
     the same source of truth schema.sql and the ORM share, so a database in
     any state converges to the full schema.
  2. Additive ALTER TABLE for missing columns on existing tables — covers
     drift the models gained since the DB was first provisioned (users.plan,
     farms.planting_date, the payments columns, ...).
  3. Stamp alembic_version to head so future hand-runs of `alembic upgrade
     head` are clean no-ops instead of colliding with existing tables.

Safe to run on every boot: every step is checked-then-act, never destructive.
"""
import logging

from sqlalchemy import inspect, text

from app.core.database import Base, get_engine

logger = logging.getLogger("app.db.bootstrap")


def _existing_columns(conn, table: str) -> set[str]:
    insp = inspect(conn)
    if not insp.has_table(table):
        return set()
    return {c["name"] for c in insp.get_columns(table) if c.get("name")}


def bootstrap_database() -> None:
    engine = get_engine()
    with engine.connect() as conn:
        insp = inspect(conn)

        # 1. Missing tables — created directly from the models.
        before = set(insp.get_table_names())
        Base.metadata.create_all(bind=conn)
        created = set(insp.get_table_names()) - before
        if created:
            logger.info("bootstrap: created missing tables: %s", sorted(created))

        # 2. Missing columns on existing tables — additive ALTERs from the models.
        for table_name, table in Base.metadata.tables.items():
            if table_name not in ("users", "payments", "email_verification_codes", "password_reset_tokens", "expenses", "harvests"):
                # Only patch tables a schema.sql baseline could plausibly lack.
                continue
            existing = _existing_columns(conn, table_name)
            for col in table.columns:
                if col.name in existing:
                    continue
                col_type = col.type.compile(engine.dialect)
                default = ""
                if col.server_default is not None and col.server_default.arg is not None:
                    default = f" DEFAULT '{col.server_default.arg}'"
                elif col.nullable is False:
                    default = " DEFAULT ''"
                conn.exec_driver_sql(
                    f'ALTER TABLE "{table_name}" ADD COLUMN "{col.name}" {col_type}{default}'
                )
                logger.info("bootstrap: added %s.%s", table_name, col.name)

        # 3. Stamp alembic to head if missing or behind, so later manual
        #    `alembic upgrade head` runs do not collide with existing tables.
        conn.exec_driver_sql(
            "create table if not exists alembic_version (version_num varchar(32) not null)"
        )
        conn.commit()
        insp = inspect(conn)
        current = None
        if insp.has_table("alembic_version"):
            row = conn.execute(text("select version_num from alembic_version")).first()
            current = row[0] if row else None
        if current != "0008":
            conn.execute(text("delete from alembic_version"))
            conn.execute(text("insert into alembic_version (version_num) values ('0008')"))
            conn.commit()
            logger.info("bootstrap: stamped alembic_version to 0008 (was %s)", current)
