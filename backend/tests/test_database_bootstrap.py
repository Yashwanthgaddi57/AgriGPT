import logging

from sqlalchemy import create_engine, inspect

from app.core.database import _create_missing_tables
from app.models.user import User


def test_create_missing_tables_repairs_existing_partial_schema():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    User.__table__.create(engine)

    created = _create_missing_tables(engine, logging.getLogger("test.db.bootstrap"))
    tables = set(inspect(engine).get_table_names())

    assert "users" in tables
    assert "email_verification_codes" in tables
    assert "password_reset_tokens" in tables
    assert {"email_verification_codes", "password_reset_tokens"} <= created

    engine.dispose()
