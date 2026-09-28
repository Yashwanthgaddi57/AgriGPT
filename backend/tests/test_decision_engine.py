"""Decision engine + farm economics tests (offline: SQLite, no AI/network)."""
from datetime import date, datetime, timedelta, timezone

import pytest

from app.models.chat import ChatMessage, ChatSession
from app.models.expense import Expense
from app.models.farm import Farm
from app.models.harvest import Harvest
from app.models.profit_prediction import ProfitPrediction
from tests.factories import make_user


@pytest.fixture(autouse=True)
def _isolated_market_cache():
    """Empty cache + closed Agmarknet circuit for every test.

    Decision-engine tests exercise price_snapshot(), which may attempt real
    network calls; without this, the module-level circuit breaker opens and
    leaks into the mock-based agmarknet tests that run later.
    """
    from app.core.cache import _memory_store
    from app.services import agmarknet_client

    _memory_store.clear()
    agmarknet_client._api_dead_until = 0.0
    agmarknet_client._failure_streak = 0
    yield
    _memory_store.clear()
    agmarknet_client._api_dead_until = 0.0
    agmarknet_client._failure_streak = 0


@pytest.fixture
def auth_client(client, sample_user):
    from app.core.deps import get_current_user
    from app.main import app

    app.dependency_overrides[get_current_user] = lambda: sample_user
    yield client
    app.dependency_overrides.pop(get_current_user, None)


# ---------------------------------------------------------------------------
# Expenses
# ---------------------------------------------------------------------------
def test_expense_crud_and_summary(auth_client):
    resp = auth_client.post(
        "/api/v1/farm/expenses",
        json={"category": "fertilizer", "amount_inr": 2500, "spent_on": "2026-09-20", "description": "urea"},
    )
    assert resp.status_code == 201

    resp = auth_client.post(
        "/api/v1/farm/expenses",
        json={"category": "seed", "amount_inr": 1500, "spent_on": "2026-09-21"},
    )
    assert resp.status_code == 201

    resp = auth_client.get("/api/v1/farm/expenses")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 4000
    assert body["by_category"]["fertilizer"] == 2500
    assert len(body["items"]) == 2

    # delete (items are ordered by spent_on desc -> items[0] is the seed/1500 row)
    eid = body["items"][0]["id"]
    assert auth_client.delete(f"/api/v1/farm/expenses/{eid}").status_code == 204
    resp = auth_client.get("/api/v1/farm/expenses")
    assert resp.json()["total"] == 2500


def test_expense_invalid_category_rejected(auth_client):
    resp = auth_client.post(
        "/api/v1/farm/expenses",
        json={"category": "yacht", "amount_inr": 100, "spent_on": "2026-09-20"},
    )
    assert resp.status_code == 422


def test_expense_isolation_user_a_cannot_delete_user_b(client, sample_user, db_session):
    other = make_user(db_session, email="expense-other@example.com")
    e = Expense(user_id=other.id, category="seed", amount_inr=100, spent_on=date.today())
    db_session.add(e)
    db_session.flush()

    from app.core.deps import get_current_user
    from app.main import app

    app.dependency_overrides[get_current_user] = lambda: sample_user
    try:
        resp = client.delete(f"/api/v1/farm/expenses/{e.id}")
        assert resp.status_code == 404
    finally:
        app.dependency_overrides.pop(get_current_user, None)


# ---------------------------------------------------------------------------
# Harvest
# ---------------------------------------------------------------------------
def test_harvest_derives_revenue(auth_client):
    resp = auth_client.post(
        "/api/v1/farm/harvests",
        json={
            "crop": "groundnut",
            "harvest_date": "2026-09-15",
            "actual_yield_quintals": 20,
            "selling_price_per_quintal": 5800,
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert float(body["revenue_inr"]) == 116000  # 20 * 5800 derived, not asked

    resp = auth_client.get("/api/v1/farm/harvests")
    assert resp.status_code == 200
    assert len(resp.json()["items"]) == 1


# ---------------------------------------------------------------------------
# Estimated vs actual
# ---------------------------------------------------------------------------
def test_estimated_vs_actual_deltas(auth_client, sample_user, db_session):
    db_session.add(
        ProfitPrediction(
            user_id=sample_user.id,
            crop="groundnut",
            farm_size_acres=2.5,
            total_cost=37500,
            expected_yield_quintals=24,
            expected_price_per_quintal=6000,
            expected_revenue=144000,
            expected_profit=106500,
        )
    )
    db_session.add(
        Harvest(
            user_id=sample_user.id,
            crop="groundnut",
            actual_yield_quintals=20,
            selling_price_per_quintal=5800,
            revenue_inr=116000,
        )
    )
    db_session.add(Expense(user_id=sample_user.id, category="seed", amount_inr=6000, spent_on=date.today()))
    db_session.flush()

    resp = auth_client.get("/api/v1/farm/estimated-vs-actual")
    assert resp.status_code == 200
    body = resp.json()
    assert body["has_comparison"] is True
    assert body["estimated"]["revenue"] == 144000
    assert body["actual"]["revenue"] == 116000
    assert body["difference"]["revenue"] == -28000
    assert body["actual"]["cost"] == 6000
    assert body["actual"]["profit"] == 110000  # 116000 - 6000


# ---------------------------------------------------------------------------
# Timeline
# ---------------------------------------------------------------------------
def test_timeline_includes_harvest_scan_estimate(auth_client, sample_user, db_session):
    from app.models.disease_report import DiseaseReport

    db_session.add(Harvest(user_id=sample_user.id, crop="wheat", revenue_inr=50000))
    db_session.add(
        DiseaseReport(user_id=sample_user.id, crop="wheat", disease_name="Rust", confidence=80)
    )
    db_session.add(
        ProfitPrediction(user_id=sample_user.id, crop="wheat", farm_size_acres=2, total_cost=20000)
    )
    db_session.flush()

    resp = auth_client.get("/api/v1/farm/timeline")
    assert resp.status_code == 200
    types = {e["type"] for e in resp.json()["items"]}
    assert {"harvest", "scan", "estimate"} <= types


# ---------------------------------------------------------------------------
# Today plan (decision engine)
# ---------------------------------------------------------------------------
def test_today_plan_structure_and_basis(auth_client, sample_user, db_session):
    db_session.add(
        Farm(
            user_id=sample_user.id,
            name="North Plot",
            area_acres=2.5,
            current_crop="chilli",
            planting_date=date.today() - timedelta(days=42),
        )
    )
    db_session.flush()

    resp = auth_client.get("/api/v1/farm/today")
    assert resp.status_code == 200
    body = resp.json()
    assert body["farm"]["crop"] == "chilli"
    assert body["farm"]["crop_age_days"] == 42
    assert body["farm"]["crop_stage"] == "vegetative"
    # priorities always exist, carry basis + disclaimer, max 4
    assert 1 <= len(body["priorities"]) <= 4
    for p in body["priorities"]:
        assert p["basis"]
        assert p["title"]
    assert "not guarantees" in body["disclaimer"]


def test_today_plan_no_farm_still_works(auth_client):
    resp = auth_client.get("/api/v1/farm/today")
    assert resp.status_code == 200
    body = resp.json()
    assert body["farm"]["crop"] is None
    assert len(body["priorities"]) >= 1


# ---------------------------------------------------------------------------
# Copilot farm-records block
# ---------------------------------------------------------------------------
def test_copilot_context_includes_real_records(db_session, sample_user):
    from app.services.chat_service import build_farmer_context

    db_session.add(Expense(user_id=sample_user.id, category="fertilizer", amount_inr=8000, spent_on=date.today()))
    db_session.flush()

    ctx = build_farmer_context(sample_user, db_session)
    assert "RECORDED EXPENSES" in ctx
    assert "fertilizer" in ctx


def test_crop_age_line_only_with_real_planting_date(db_session, sample_user):
    from app.services.chat_service import _crop_age_line

    # No farm -> None (never guessed)
    assert _crop_age_line(db_session, sample_user) is None  # noqa: (db, user) order

    db_session.add(
        Farm(user_id=sample_user.id, name="F", area_acres=1, current_crop="chilli", planting_date=date.today() - timedelta(days=10))
    )
    db_session.flush()
    line = _crop_age_line(db_session, sample_user)
    assert line and "10 days" in line
