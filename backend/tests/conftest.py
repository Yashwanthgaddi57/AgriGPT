"""Test fixtures: in-memory SQLite DB with pre-created schema, test client."""
import os

os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("SUPABASE_DB_URL", "sqlite+pysqlite:///:memory:")
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-test-key")
os.environ.setdefault("SCHEDULER_ENABLED", "false")
# Hermetic cache: point Redis at an unused port so the cache module falls back
# to its in-process store (the suite must never read/write a real Redis —
# a running local Redis would otherwise leak state across test processes).
os.environ["REDIS_URL"] = "redis://localhost:6390/15"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.main import app


@pytest.fixture(scope="session")
def engine():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(engine):
    Session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    session = Session()
    yield session
    session.rollback()
    session.close()


@pytest.fixture
def client(engine, db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def auth_headers():
    """Fake but structurally valid HS256 token; tests patch decoding via user override."""
    return {"Authorization": "Bearer test-token"}


@pytest.fixture
def sample_user(db_session):
    from tests.factories import make_user

    return make_user(db_session)
