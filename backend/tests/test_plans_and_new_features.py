"""Tests for plan limits, subscription, disease follow-up, analytics events.

Runs fully offline: SQLite in-memory DB, AI/auth patched, no external calls.
"""
import uuid

import pytest

from app.models.chat import ChatSession
from tests.factories import make_disease_report, make_user


# ---------------------------------------------------------------------------
# Plan limits
# ---------------------------------------------------------------------------
@pytest.fixture
def auth_client(client, sample_user):
    from app.core.deps import get_current_user
    from app.main import app

    app.dependency_overrides[get_current_user] = lambda: sample_user
    yield client
    app.dependency_overrides.pop(get_current_user, None)


def test_plan_limit_blocks_free_crop_recommendation(auth_client, sample_user, db_session):
    """Free plan: 6th crop recommendation this month -> 429 (server-side)."""
    from datetime import datetime, timedelta, timezone

    from app.models.recommendation import Recommendation

    for _ in range(5):
        db_session.add(
            Recommendation(
                user_id=sample_user.id,
                location="Nashik",
                season="kharif",
                farm_size_acres=5,
                crops=[],
                created_at=datetime.now(timezone.utc) - timedelta(hours=1),
            )
        )
    db_session.flush()

    resp = auth_client.post(
        "/api/v1/crops/recommend",
        json={
            "location": "Nashik",
            "farm_size_acres": 5,
            "soil_type": "black",
            "water_source": "borewell",
            "budget_inr": 50000,
            "season": "kharif",
        },
    )
    assert resp.status_code == 429
    assert "limit" in resp.json()["error"]["detail"].lower()


def test_pro_plan_has_no_crop_limit(auth_client, sample_user, db_session):
    """Pro plan bypasses the monthly quota (no AI call happens: 429 never raised)."""
    from datetime import datetime, timedelta, timezone

    from app.models.recommendation import Recommendation

    sample_user.plan = "pro"
    db_session.flush()
    for _ in range(6):
        db_session.add(
            Recommendation(
                user_id=sample_user.id,
                location="Nashik",
                season="kharif",
                farm_size_acres=5,
                crops=[],
                created_at=datetime.now(timezone.utc) - timedelta(hours=1),
            )
        )
    db_session.flush()

    resp = auth_client.post(
        "/api/v1/crops/recommend",
        json={
            "location": "Nashik",
            "farm_size_acres": 5,
            "soil_type": "black",
            "water_source": "borewell",
            "budget_inr": 50000,
            "season": "kharif",
        },
    )
    # Quota passes (429 would mean the limit leaked); the endpoint then calls the
    # AI which is unconfigured in tests -> AIError (502), not 429.
    assert resp.status_code != 429


def test_plan_limit_blocks_free_disease_scan(auth_client, sample_user, db_session):
    from datetime import datetime, timedelta, timezone

    from app.models.disease_report import DiseaseReport

    for _ in range(10):
        db_session.add(
            DiseaseReport(
                user_id=sample_user.id,
                crop="cotton",
                disease_name="x",
                created_at=datetime.now(timezone.utc) - timedelta(hours=1),
            )
        )
    db_session.flush()

    resp = auth_client.post(
        "/api/v1/disease/analyze",
        files={"image": ("leaf.jpg", b"\xff\xd8\xff\xe0fake", "image/jpeg")},
        data={"crop": "cotton"},
    )
    assert resp.status_code == 429


# ---------------------------------------------------------------------------
# Subscription endpoints
# ---------------------------------------------------------------------------
def test_subscription_plans_catalog(auth_client):
    resp = auth_client.get("/api/v1/subscription/plans")
    assert resp.status_code == 200
    body = resp.json()
    ids = [p["id"] for p in body["plans"]]
    assert ids == ["free", "pro", "cooperative"]
    assert body["payments_enabled"] is False
    free = next(p for p in body["plans"] if p["id"] == "free")
    assert free["price_inr"] == 0


def test_subscription_usage_summary(auth_client, sample_user, db_session):
    make_disease_report(db_session, sample_user)
    db_session.flush()
    resp = auth_client.get("/api/v1/subscription")
    assert resp.status_code == 200
    body = resp.json()
    assert body["plan"] == "free"
    assert body["usage"]["disease_scans"]["used"] >= 1
    assert body["usage"]["disease_scans"]["limit"] == 10


def test_checkout_returns_501_not_fake_success(auth_client):
    """No fake payment success: checkout must 501 until a provider is wired."""
    resp = auth_client.post("/api/v1/subscription/checkout", json={"plan": "pro"})
    assert resp.status_code == 501


# ---------------------------------------------------------------------------
# Disease follow-up
# ---------------------------------------------------------------------------
def test_disease_followup_update(auth_client, sample_user, db_session):
    report = make_disease_report(db_session, sample_user)
    db_session.flush()

    resp = auth_client.patch(
        f"/api/v1/disease/reports/{report.id}",
        json={"followup_status": "treated", "notes": "Sprayed neem oil"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["followup_status"] == "treated"
    assert body["notes"] == "Sprayed neem oil"


def test_disease_followup_cannot_touch_other_users_report(client, sample_user, db_session):
    """IDOR check: User B's report is invisible to User A."""
    other = make_user(db_session, email="other@example.com")
    report = make_disease_report(db_session, other)
    db_session.flush()

    from app.core.deps import get_current_user
    from app.main import app

    app.dependency_overrides[get_current_user] = lambda: sample_user
    try:
        resp = client.patch(
            f"/api/v1/disease/reports/{report.id}",
            json={"followup_status": "resolved"},
        )
        assert resp.status_code == 404
        resp2 = client.get(f"/api/v1/disease/reports/{report.id}")
        assert resp2.status_code == 404
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_disease_report_includes_alternatives(auth_client, sample_user, db_session):
    report = make_disease_report(db_session, sample_user)
    report.alternatives = ["Nutrient deficiency", "Water stress"]
    report.followup_status = "monitoring"
    db_session.flush()

    resp = auth_client.get(f"/api/v1/disease/reports/{report.id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["alternatives"] == ["Nutrient deficiency", "Water stress"]
    assert body["followup_status"] == "monitoring"


# ---------------------------------------------------------------------------
# Analytics events
# ---------------------------------------------------------------------------
def test_analytics_event_tracked(auth_client):
    resp = auth_client.post(
        "/api/v1/analytics/events",
        json={"event": "crop_plan_started", "metadata": {"source": "dashboard"}},
    )
    assert resp.status_code == 200
    assert resp.json()["tracked"] is True


def test_analytics_event_allowlist(auth_client):
    resp = auth_client.post(
        "/api/v1/analytics/events",
        json={"event": "arbitrary_malware_event"},
    )
    assert resp.status_code == 200
    assert resp.json()["tracked"] is False


# ---------------------------------------------------------------------------
# Dashboard extras
# ---------------------------------------------------------------------------
def test_dashboard_includes_farm_and_crop_health(auth_client, sample_user, db_session):
    make_disease_report(db_session, sample_user)
    db_session.flush()
    resp = auth_client.get("/api/v1/dashboard")
    assert resp.status_code == 200
    body = resp.json()
    assert "farm" in body
    assert body["farm"]["farm_size_acres"] == 5
    assert "crop_health" in body
    assert body["crop_health"]["open_issues"] >= 1


# ---------------------------------------------------------------------------
# Rate limiting: group limits exist and general limiter still works
# ---------------------------------------------------------------------------
def test_rate_limit_group_config_exists():
    from app.core.middleware import GROUP_LIMITS, RATE_LIMIT_REQUESTS

    paths = [p for p, _, _ in GROUP_LIMITS]
    assert "/api/v1/auth/login" in paths
    assert "/api/v1/auth/register" in paths
    assert "/api/v1/disease/analyze" in paths
    # Every group limit is stricter than the general budget
    assert all(gmax < RATE_LIMIT_REQUESTS for _, _, gmax in GROUP_LIMITS)


def test_rate_limit_blocks_flood(client):
    """General per-IP limiter kicks in on a flood (memory fallback in tests)."""
    from app.core import middleware

    old = middleware.RATE_LIMIT_REQUESTS
    try:
        middleware.RATE_LIMIT_REQUESTS = 5
        codes = [client.get("/api/v1/profile").status_code for _ in range(10)]
        assert 429 in codes
    finally:
        middleware.RATE_LIMIT_REQUESTS = old


# ---------------------------------------------------------------------------
# Plans config sanity
# ---------------------------------------------------------------------------
def test_plan_limits_shape():
    from app.core.plans import PLAN_LIMITS

    for plan, limits in PLAN_LIMITS.items():
        assert isinstance(limits, dict)
        assert all(isinstance(v, int) and (v == -1 or v >= 0) for v in limits.values())


# ---------------------------------------------------------------------------
# Chat quota counts farmer messages only
# ---------------------------------------------------------------------------
def test_chat_quota_counts_only_user_messages(auth_client, sample_user, db_session):
    """20/day limit must count farmer turns, not assistant replies too."""
    from datetime import datetime, timedelta, timezone

    from app.core.plans_service import check_chat_quota
    from app.models.chat import ChatMessage

    session = ChatSession(user_id=sample_user.id, title="t")
    db_session.add(session)
    db_session.flush()
    hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
    for _ in range(19):
        db_session.add(ChatMessage(session_id=session.id, user_id=sample_user.id,
                                   role="user", content="hi", created_at=hour_ago))
        db_session.add(ChatMessage(session_id=session.id, user_id=sample_user.id,
                                   role="assistant", content="hello", created_at=hour_ago))
    db_session.flush()

    # 19 user messages -> under the 20 limit, must not raise
    check_chat_quota(db_session, sample_user)

    # 20th user message hits the limit
    db_session.add(ChatMessage(session_id=session.id, user_id=sample_user.id,
                               role="user", content="again", created_at=hour_ago))
    db_session.flush()
    from app.core.plans_service import PlanLimitExceeded

    with pytest.raises(PlanLimitExceeded):
        check_chat_quota(db_session, sample_user)


# ---------------------------------------------------------------------------
# Market comparison endpoint
# ---------------------------------------------------------------------------
def test_market_compare_returns_flagged_snapshots(auth_client, sample_user):
    """Compare endpoint returns per-mandi rows with source/live flags."""
    resp = auth_client.get("/api/v1/market/compare", params={"crop": "wheat"})
    assert resp.status_code in (200, 502)  # 502 only if geo resolution fails offline
    if resp.status_code == 200:
        body = resp.json()
        assert "items" in body and "note" in body
        for item in body["items"]:
            assert "mandi" in item and "price" in item
            assert "is_live" in item and "source" in item
