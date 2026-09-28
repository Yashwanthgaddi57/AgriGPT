"""API tests. Auth and AI are patched so tests run without external services."""
import uuid

import pytest


@pytest.fixture
def auth_client(client, sample_user):
    """Client with get_current_user overridden to return the sample user."""
    from app.core.deps import get_current_user
    from app.main import app

    app.dependency_overrides[get_current_user] = lambda: sample_user
    yield client
    app.dependency_overrides.pop(get_current_user, None)


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_profile_requires_auth(client):
    resp = client.get("/api/v1/profile")
    assert resp.status_code in (401, 403)


def test_get_profile(auth_client):
    resp = auth_client.get("/api/v1/profile")
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "Test Farmer"
    assert body["district"] == "Nashik"


def test_update_profile(auth_client):
    resp = auth_client.patch(
        "/api/v1/profile",
        json={"name": "Updated Farmer", "farm_size_acres": 7.5, "soil_type": "loamy"},
    )
    assert resp.status_code == 200
    assert resp.json()["farm_size_acres"] == 7.5


def test_farm_crud(auth_client):
    # create
    resp = auth_client.post(
        "/api/v1/farms",
        json={"name": "East Plot", "area_acres": 3.5, "soil_type": "alluvial", "water_source": "canal"},
    )
    assert resp.status_code == 201
    farm_id = resp.json()["id"]

    # list
    resp = auth_client.get("/api/v1/farms")
    assert resp.status_code == 200
    assert any(f["id"] == farm_id for f in resp.json())

    # update
    resp = auth_client.patch(f"/api/v1/farms/{farm_id}", json={"current_crop": "wheat"})
    assert resp.status_code == 200
    assert resp.json()["current_crop"] == "wheat"

    # delete
    resp = auth_client.delete(f"/api/v1/farms/{farm_id}")
    assert resp.status_code == 204


def test_recommendation_validation(auth_client):
    # missing required fields -> 422
    resp = auth_client.post("/api/v1/crops/recommend", json={"location": "Nashik"})
    assert resp.status_code == 422


def test_profit_validation(auth_client):
    resp = auth_client.post("/api/v1/profit/predict", json={"crop": "w"})
    assert resp.status_code == 422


def test_notifications_empty(auth_client):
    resp = auth_client.get("/api/v1/notifications")
    assert resp.status_code == 200
    assert resp.json()["unread_count"] == 0


def test_analytics_kpis(auth_client, db_session, sample_user):
    from tests.factories import make_profit_prediction

    make_profit_prediction(db_session, sample_user)
    resp = auth_client.get("/api/v1/analytics/kpis")
    assert resp.status_code == 200
    body = resp.json()
    assert body["expected_revenue"] == 350000
    assert "profit_growth" in body


def test_chat_sessions_list(auth_client):
    resp = auth_client.get("/api/v1/chat/sessions")
    assert resp.status_code == 200
    assert resp.json() == []
