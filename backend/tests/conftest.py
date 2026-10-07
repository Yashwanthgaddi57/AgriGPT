"""Test fixtures: in-memory SQLite DB with pre-created schema, test client."""
import os

os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("SUPABASE_DB_URL", "sqlite+pysqlite:///:memory:")
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-test-key")
os.environ.setdefault("SCHEDULER_ENABLED", "false")
# Hermetic payments: the developer's .env may hold real Razorpay test keys,
# which would flip payments_enabled and break the 501-contract tests.
os.environ["RAZORPAY_KEY_ID"] = ""
os.environ["RAZORPAY_KEY_SECRET"] = ""
# Hermetic cache: point Redis at an unused port so the cache module falls back
# to its in-process store (the suite must never read/write a real Redis —
# a running local Redis would otherwise leak state across test processes).
os.environ["REDIS_URL"] = "redis://localhost:6390/15"
# Hermetic auth: force local-auth mode regardless of backend/.env. A real
# SUPABASE_URL (the developer's actual project) flips auth out of local mode,
# so tests would hit — and create users in — a live Supabase project and the
# local-auth tests fail on Supabase-JWT verification. Assigned (not setdefault)
# so a stray exported var cannot leak a live project into the suite either.
os.environ["SUPABASE_URL"] = "https://YOUR_PROJECT_REF.supabase.co"
os.environ["SUPABASE_ANON_KEY"] = "your-anon-key"
os.environ["SUPABASE_SERVICE_KEY"] = "your-service-role-key"
os.environ["SUPABASE_JWT_SECRET"] = "your-supabase-jwt-secret"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.main import app, fastapi_app


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

    fastapi_app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    fastapi_app.dependency_overrides.clear()


@pytest.fixture
def auth_headers():
    """Fake but structurally valid HS256 token; tests patch decoding via user override."""
    return {"Authorization": "Bearer test-token"}


@pytest.fixture
def sample_user(db_session):
    from tests.factories import make_user

    return make_user(db_session)
