"""Tests for the Agmarknet market data integration and the production guard."""
from datetime import date, timedelta

import pytest

from app.services import agmarknet_client
from app.services.agmarknet_client import (
    _parse_rows,
    latest_fresh_price,
    market_data_points,
    parse_arrival_date,
)


@pytest.fixture(autouse=True)
def _isolated_cache():
    """Start every test with an empty in-process cache."""
    from app.core.cache import _memory_store

    _memory_store.clear()
    yield
    _memory_store.clear()


# ----------------------------------------------------------------------
# Agmarknet client
# ----------------------------------------------------------------------
def test_parse_arrival_date_formats():
    assert parse_arrival_date("23/09/2026") == date(2026, 9, 23)
    assert parse_arrival_date("23-09-2026") == date(2026, 9, 23)
    assert parse_arrival_date("2026-09-23") == date(2026, 9, 23)
    assert parse_arrival_date("") is None
    assert parse_arrival_date(None) is None
    assert parse_arrival_date("garbage") is None


def test_parse_rows_averages_varieties_per_day_and_sorts():
    records = [
        {"arrival_date": "23/09/2026", "modal_price": "2400", "min_price": "2200", "max_price": "2600"},
        {"arrival_date": "23/09/2026", "modal_price": "2600", "min_price": "2400", "max_price": "2800"},
        {"arrival_date": "22/09/2026", "modal_price": "2300", "min_price": "2100", "max_price": "2500"},
    ]
    rows = _parse_rows(records)
    assert rows == [
        {"date": "2026-09-22", "price": 2300.0},
        {"date": "2026-09-23", "price": 2500.0},
    ]


def test_parse_rows_quarantines_bad_rows():
    records = [
        {"arrival_date": "23/09/2026", "modal_price": "abc", "min_price": "", "max_price": None},
        {"arrival_date": "bad-date", "modal_price": "1000"},
        {"arrival_date": "24/09/2026", "modal_price": "0"},  # zero price -> rejected
        {"arrival_date": "24/09/2026", "modal_price": "1500", "min_price": "1400", "max_price": "1600"},
    ]
    rows = _parse_rows(records)
    assert rows == [{"date": "2026-09-24", "price": 1500.0}]


def test_latest_fresh_price_respects_freshness_window():
    fresh = [{"date": date.today().isoformat(), "price": 100}]
    stale = [{"date": (date.today() - timedelta(days=agmarknet_client.FRESHNESS_DAYS + 2)).isoformat(), "price": 100}]
    assert latest_fresh_price(fresh) == 100
    assert latest_fresh_price(stale) is None
    assert latest_fresh_price([]) is None


def test_market_data_points_keeps_newest_per_mandi():
    records = [
        {"market": "Lasalgaon", "district": "Nashik", "state": "Maharashtra",
         "modal_price": "1500", "arrival_date": "20/09/2026"},
        {"market": "Lasalgaon", "district": "Nashik", "state": "Maharashtra",
         "modal_price": "1600", "arrival_date": "21/09/2026"},
        {"market": "Pimpalgaon", "district": "Nashik", "state": "Maharashtra",
         "modal_price": "1550", "arrival_date": "21/09/2026"},
        {"market": "", "modal_price": "999", "arrival_date": "21/09/2026"},  # no market -> skipped
    ]
    points = market_data_points(records)
    assert set(points) == {"Lasalgaon", "Pimpalgaon"}
    assert points["Lasalgaon"]["modal_price"] == 1600
    assert points["Lasalgaon"]["arrival_date"] == "2026-09-21"
    assert points["Lasalgaon"]["district"] == "Nashik"


@pytest.mark.asyncio
async def test_fetch_returns_empty_without_key(monkeypatch):
    monkeypatch.setattr("app.core.config.settings.DATA_GOV_API_KEY", "")
    assert agmarknet_client.fetch_mandi_prices("onion") == []


@pytest.mark.asyncio
async def test_fetch_returns_empty_for_unknown_crop(monkeypatch):
    monkeypatch.setattr("app.core.config.settings.DATA_GOV_API_KEY", "test-key")
    assert agmarknet_client.fetch_mandi_prices("dragonfruit") == []


@pytest.mark.asyncio
async def test_fetch_failsoft_on_http_error(monkeypatch):
    monkeypatch.setattr("app.core.config.settings.DATA_GOV_API_KEY", "test-key")

    class FakeResponse:
        status_code = 500

        def raise_for_status(self):
            raise RuntimeError("boom")

        def json(self):
            return {}

    class FakeClient:
        def __init__(self, *a, **kw):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def get(self, *a, **kw):
            return FakeResponse()

    monkeypatch.setattr(agmarknet_client.httpx, "Client", FakeClient)
    assert agmarknet_client.fetch_mandi_prices("onion") == []


@pytest.mark.asyncio
async def test_fetch_parses_and_caches(monkeypatch):
    monkeypatch.setattr("app.core.config.settings.DATA_GOV_API_KEY", "test-key")
    payload = {
        "records": [
            {"state": "Maharashtra", "district": "Nashik", "market": "Lasalgaon",
             "commodity": "Onion", "arrival_date": date.today().strftime("%d/%m/%Y"),
             "min_price": "1400", "max_price": "1800", "modal_price": "1600"},
        ]
    }

    class FakeResponse:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return payload

    class FakeClient:
        def __init__(self, *a, **kw):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def get(self, *a, **kw):
            return FakeResponse()

    monkeypatch.setattr(agmarknet_client.httpx, "Client", FakeClient)
    # Isolate cache between tests
    from app.core.cache import _memory_store

    _memory_store.clear()

    points = agmarknet_client.fetch_mandi_prices("onion")
    assert len(points) == 1
    assert points[0]["price"] == 1600.0
    assert points[0]["date"] == date.today().isoformat()


# ----------------------------------------------------------------------
# Market service fallback chain
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_analyze_uses_baseline_when_feed_down(db_session, sample_user, monkeypatch):
    """No API key -> synthetic baseline + source stays 'baseline'."""
    from app.schemas.ai_features import MarketPredictionRequest
    from app.services.market_service import MarketService

    monkeypatch.setattr("app.core.config.settings.DATA_GOV_API_KEY", "")
    # Force AI to fail so the deterministic heuristic path runs
    from app.core.exceptions import AIError

    def _raise(*a, **kw):
        raise AIError("no ai in tests")

    monkeypatch.setattr("app.services.market_service.get_claude", lambda: type("C", (), {"complete_json": staticmethod(_raise)})())

    from app.core.cache import _memory_store

    _memory_store.clear()

    pred = await MarketService(db_session).analyze(
        str(sample_user.id), MarketPredictionRequest(crop="wheat")
    )
    assert pred.data_source == "baseline"
    assert pred.current_price > 0
    assert len(pred.price_history) == 91  # 90 days back through today


@pytest.mark.asyncio
async def test_analyze_uses_agmarknet_when_fresh(db_session, sample_user, monkeypatch):
    """Fresh feed data wins over the baseline and is recorded as the source."""
    from app.schemas.ai_features import MarketPredictionRequest
    from app.services.market_service import MarketService

    real_points = [
        {"date": (date.today() - timedelta(days=2)).isoformat(), "price": 2000},
        {"date": (date.today() - timedelta(days=1)).isoformat(), "price": 2050},
        {"date": date.today().isoformat(), "price": 2100},
    ]
    monkeypatch.setattr(
        "app.services.market_service.agmarknet_client.fetch_mandi_prices",
        lambda crop, **kw: real_points,
    )

    def _fake_complete_json(self=None, **kw):
        return {"current_price": 2100, "recommendation": "hold", "confidence": 60}

    monkeypatch.setattr(
        "app.services.market_service.get_claude",
        lambda: type("C", (), {"complete_json": staticmethod(_fake_complete_json)})(),
    )

    from app.core.cache import _memory_store

    _memory_store.clear()

    pred = await MarketService(db_session).analyze(
        str(sample_user.id), MarketPredictionRequest(crop="wheat")
    )
    assert pred.data_source == "agmarknet_national"
    assert pred.current_price == 2100
    assert len(pred.price_history) == 3


# ----------------------------------------------------------------------
# Production readiness guard
# ----------------------------------------------------------------------
def _prod_settings(**overrides):
    from app.core.config import Settings

    base = dict(
        ENVIRONMENT="production",
        SUPABASE_URL="https://realproject.supabase.co",
        SUPABASE_JWT_SECRET="a-real-secret",
        SUPABASE_DB_URL="postgresql+psycopg://u:p@db.real.supabase.co:5432/postgres",
        AI_PROVIDER="anthropic",
        ANTHROPIC_API_KEY="sk-ant-real-key",
        BACKEND_CORS_ORIGINS=["https://app.example.com"],
        SCHEDULER_ENABLED=False,
    )
    base.update(overrides)
    return Settings(**base)


def test_prod_guard_passes_with_real_config():
    s = _prod_settings()
    s.assert_production_ready()  # should not raise


def test_prod_guard_blocks_placeholder_supabase():
    s = _prod_settings(SUPABASE_URL="https://YOUR_PROJECT_REF.supabase.co")
    with pytest.raises(RuntimeError, match="SUPABASE_URL"):
        s.assert_production_ready()


def test_prod_guard_blocks_sqlite():
    s = _prod_settings(SUPABASE_DB_URL="sqlite:///./agrigpt_local.db")
    with pytest.raises(RuntimeError, match="SQLite"):
        s.assert_production_ready()


def test_prod_guard_blocks_test_ai_key():
    s = _prod_settings(AI_PROVIDER="anthropic", ANTHROPIC_API_KEY="sk-ant-test-key")
    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        s.assert_production_ready()


def test_prod_guard_allows_bedrock_without_anthropic_key():
    # BEDROCK_API_KEY must be passed explicitly: Settings() silently reads the
    # developer's gitignored .env, which masked this test on dev machines — on
    # a clean checkout/CI (no .env) the guard correctly requires a Bedrock key.
    s = _prod_settings(AI_PROVIDER="bedrock", ANTHROPIC_API_KEY="", BEDROCK_API_KEY="real-bedrock-key")
    s.assert_production_ready()  # Bedrock authenticates differently — no error


def test_prod_guard_warns_but_does_not_block_default_cors():
    # CORS misconfig blocks browsers but is not a security/data risk, and the
    # frontend domain may not exist yet at first deploy — warn, don't crash.
    s = _prod_settings(BACKEND_CORS_ORIGINS=["http://localhost:3000"])
    s.assert_production_ready()  # must NOT raise


def test_prod_guard_blocks_placeholder_jwt_secret():
    s = _prod_settings(SUPABASE_JWT_SECRET="your-supabase-jwt-secret")
    with pytest.raises(RuntimeError, match="JWT_SECRET"):
        s.assert_production_ready()
