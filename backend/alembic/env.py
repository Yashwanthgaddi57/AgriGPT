"""Alembic environment wired to app settings and metadata."""
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.core.config import settings
from app.core.database import Base
from app.models import *  # noqa: F401,F403 - register all models

config = context.config

# NOTE: we do NOT call config.set_main_option("sqlalchemy.url", ...) here.
# Python's configparser uses BasicInterpolation by default, which rejects '%'
# in values — and the Supabase transaction pooler URL contains %40 (the
# URL-encoded '@'). That raised
#   ValueError: invalid interpolation syntax in '...%40...' at position 61
# and crashed the build. Inject the URL directly into both migration modes
# instead of writing it through the .ini parser.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=settings.SUPABASE_DB_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        {"sqlalchemy.url": settings.SUPABASE_DB_URL},
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
