from app.core.database import _normalize_database_url


def test_normalize_postgres_url_uses_psycopg_v3():
    assert (
        _normalize_database_url("postgresql://user:pass@db.example.com:5432/app")
        == "postgresql+psycopg://user:pass@db.example.com:5432/app"
    )


def test_normalize_legacy_postgres_url_uses_psycopg_v3():
    assert (
        _normalize_database_url("postgres://user:pass@db.example.com:5432/app")
        == "postgresql+psycopg://user:pass@db.example.com:5432/app"
    )


def test_normalize_preserves_explicit_driver_and_sqlite_urls():
    psycopg_url = "postgresql+psycopg://user:pass@db.example.com:5432/app"
    sqlite_url = "sqlite:///./agrigpt.db"

    assert _normalize_database_url(psycopg_url) == psycopg_url
    assert _normalize_database_url(sqlite_url) == sqlite_url
