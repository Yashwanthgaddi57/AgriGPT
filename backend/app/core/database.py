"""SQLAlchemy engine and session management.

Production targets Supabase Postgres. For local no-Docker runs it also
supports SQLite (set SUPABASE_DB_URL=sqlite:///./agrisphere_local.db);
tables are then auto-created on startup.
"""
import logging
import uuid
from collections.abc import Generator
from typing import Any

from sqlalchemy import CHAR, JSON, create_engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.types import TypeDecorator

from app.core.config import settings

logger = logging.getLogger("app.db")


class Base(DeclarativeBase):
    """Shared declarative base for all ORM models."""


class GUID(TypeDecorator):
    """Platform-independent GUID: PG UUID on Postgres, CHAR(36) elsewhere."""

    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PG_UUID(as_uuid=True))
        return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        if dialect.name == "postgresql":
            return value
        if isinstance(value, uuid.UUID):
            return str(value)
        return str(uuid.UUID(str(value)))

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        if isinstance(value, uuid.UUID):
            return value
        return uuid.UUID(str(value))


class JSONType(TypeDecorator):
    """JSONB on Postgres, JSON elsewhere (tests/SQLite)."""

    impl = JSON
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(JSONB())
        return dialect.type_descriptor(JSON())


def _is_sqlite(url: str) -> bool:
    return url.startswith("sqlite")


_engine = None
_SessionLocal: sessionmaker | None = None


def get_engine():
    global _engine, _SessionLocal
    if _engine is None:
        url = settings.SUPABASE_DB_URL
        kwargs: dict[str, Any] = {"pool_pre_ping": True, "echo": False}
        if _is_sqlite(url):
            kwargs["connect_args"] = {"check_same_thread": False}
        else:
            kwargs.update(pool_size=5, max_overflow=10, pool_recycle=1800)
            # Supabase's transaction pooler (pgbouncer, port 6543) does not support
            # named prepared statements. psycopg3 auto-prepares after 5 executions
            # of a query, then dies with `prepared statement "_pgX_N" does not
            # exist` when pgbouncer routes the next execution elsewhere. Disabling
            # auto-prepare is required for every Supabase pooler connection.
            kwargs["connect_args"] = {"prepare_threshold": None}
        _engine = create_engine(url, **kwargs)
        _SessionLocal = sessionmaker(bind=_engine, autoflush=False, expire_on_commit=False)
    return _engine


def get_session_factory() -> sessionmaker:
    get_engine()
    assert _SessionLocal is not None
    return _SessionLocal


def is_local_db() -> bool:
    """True when running on SQLite (no Docker / no Postgres)."""
    return _is_sqlite(settings.SUPABASE_DB_URL)


def init_db() -> None:
    """Ensure the schema exists at startup, whatever the database.

    SQLite: full local mode (create all + auto-migrate). Postgres: normally a
    no-op because schema.sql/alembic provisioned everything — but if the
    database is completely empty (first deploy, schema.sql not run yet),
    create the tables from the models so the app works immediately instead of
    500-ing on every request. Safe: create_all only creates MISSING tables and
    never alters existing ones.
    """
    if is_local_db():
        init_local_db()
        return

    import sqlalchemy

    engine = get_engine()
    try:
        inspector = sqlalchemy.inspect(engine)
        tables = inspector.get_table_names()
    except Exception as e:
        logger.warning("Schema check failed (%s) — assuming provisioned", e)
        return
    if not tables:
        logger.warning("Database is empty — creating schema from models (run schema.sql/alembic for the canonical DDL)")
        from app.models import (  # noqa: F401  (register mappers)
            Activity,
            AgentLog,
            ChatMessage,
            ChatSession,
            DiseaseReport,
            Expense,
            Farm,
            Harvest,
            MarketPrediction,
            Notification,
            ProfitPrediction,
            Recommendation,
            User,
            WeatherRecord,
        )
        Base.metadata.create_all(bind=engine)
        logger.info("Created initial database schema")
        return

    # Schema exists: apply additive-only auto-migrations so deploys never
    # break auth on a schema drift (e.g. new users.plan column).
    _auto_migrate_postgres(engine, logger)


def init_local_db() -> None:
    """Create all tables + auto-migrate for SQLite local runs."""
    import logging

    logger = logging.getLogger("app.db")
    engine = get_engine()
    from app.models import (  # noqa: F401  (register mappers)
        Activity,
        AgentLog,
        ChatMessage,
        ChatSession,
        DiseaseReport,
        Expense,
        Farm,
        Harvest,
        MarketPrediction,
        Notification,
        ProfitPrediction,
        Recommendation,
        User,
        WeatherRecord,
    )

    Base.metadata.create_all(bind=engine)
    _auto_migrate_sqlite(engine, logger)
    logger.info("Local SQLite database initialized at %s", settings.SUPABASE_DB_URL)


def _auto_migrate_sqlite(engine, logger) -> None:
    """Add columns that exist on the models but not in an older SQLite file.

    SQLite's CREATE TABLE won't alter existing tables, so on schema changes we
    ALTER TABLE ADD COLUMN for any missing columns (safe + idempotent).
    """
    import sqlalchemy

    with engine.connect() as conn:
        inspector = sqlalchemy.inspect(engine)
        for table_name, table in Base.metadata.tables.items():
            if not inspector.has_table(table_name):
                continue
            existing = {c["name"] for c in inspector.get_columns(table_name)}
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
                logger.info("Auto-migrated: added %s.%s", table_name, col.name)
        conn.commit()


# ---------------------------------------------------------------------------
# Postgres additive auto-migrations (startup, idempotent)
# ---------------------------------------------------------------------------
# Only ever ADDs columns. Canonical DDL stays in alembic + supabase/schema.sql;
# this is a deploy-time safety net so a new build never 500s on a missing
# column (e.g. users.plan) before `alembic upgrade head` is run by hand.
_PG_ADDITIVE_COLUMNS: dict[str, dict[str, str]] = {
    "users": {
        # NOT NULL DEFAULT backfills existing rows instantly on PG 11+.
        "plan": "VARCHAR(20) NOT NULL DEFAULT 'free'",
    },
    "disease_reports": {
        "alternatives": "JSONB",
        "followup_status": "VARCHAR(30)",
        "notes": "TEXT",
    },
    "farms": {
        "planting_date": "DATE",
    },
}


def _auto_migrate_postgres(engine, logger) -> None:
    import sqlalchemy

    try:
        with engine.connect() as conn:
            inspector = sqlalchemy.inspect(engine)
            for table_name, cols in _PG_ADDITIVE_COLUMNS.items():
                if not inspector.has_table(table_name):
                    continue
                existing = {c["name"] for c in inspector.get_columns(table_name)
                            if c.get("name")}
                for col_name, ddl in _PG_ADDITIVE_COLUMNS[table_name].items():
                    if col_name in existing:
                        continue
                    conn.exec_driver_sql(
                        f'ALTER TABLE "{table_name}" ADD COLUMN "{col_name}" {ddl}'
                    )
                    logger.info("Auto-migrated: added %s.%s", table_name, col_name)
            conn.commit()
    except Exception as e:
        # Never block startup on migration failure — log loudly instead.
        logger.error("Postgres auto-migration failed: %s", e)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency yielding a DB session with rollback on error."""
    db = get_session_factory()()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
