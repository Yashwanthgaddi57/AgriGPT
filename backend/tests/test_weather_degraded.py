"""Regression: /weather must degrade gracefully instead of returning 502.

Production hit this on Render free tier: the Open-Meteo request blew its 6s
httpx timeout under CPU throttling, the unconfigured OpenWeatherMap fallback
raised ExternalServiceError, and the farmer's dashboard went down with it.
"""
import pytest

from app.core.exceptions import ExternalServiceError


@pytest.fixture
def auth_client(client, sample_user):
    """Client with get_current_user overridden to return the sample user."""
    from app.core.deps import get_current_user
    from app.main import fastapi_app

    fastapi_app.dependency_overrides[get_current_user] = lambda: sample_user
    yield client
    fastapi_app.dependency_overrides.pop(get_current_user, None)


def test_weather_degrades_when_all_providers_fail(auth_client, monkeypatch):
    """Both providers down -> 200 with a degraded payload, never a 502."""
    from app.core.cache import _memory_store
    from app.services import weather_service

    _memory_store.clear()

    async def open_meteo_down(location, days=7, coordinates=None):
        raise ExternalServiceError("Geocoding unavailable for 'Nashik'")

    monkeypatch.setattr(weather_service, "fetch_weather_days", open_meteo_down)

    resp = auth_client.get("/api/v1/weather")
    assert resp.status_code == 200
    body = resp.json()
    assert body["source"] == "unavailable"
    assert body["days"][0]["condition"] == "Data unavailable"
    assert body["action"] == "none"
    assert body["alerts"]
    _memory_store.clear()


def test_weather_normal_path_unchanged(auth_client, monkeypatch):
    """When providers answer, the endpoint returns the real payload."""
    from app.core.cache import _memory_store
    from app.services import weather_service

    _memory_store.clear()

    async def ok_fetch(location, days=7, coordinates=None):
        return location, [
            {
                "date": "2026-10-08", "temp_c": 25.0, "temp_max_c": 30.0, "temp_min_c": 18.0,
                "feels_like_c": 31.0, "humidity": 55.0, "wind_kph": 12.0, "precip_mm": 0.0,
                "precip_probability": 10.0, "condition": "Clear sky",
            }
        ]

    monkeypatch.setattr(weather_service, "fetch_weather_days", ok_fetch)
    monkeypatch.setattr(weather_service, "_ai_advice", _ok_ai)

    resp = auth_client.get("/api/v1/weather")
    assert resp.status_code == 200
    body = resp.json()
    assert body["days"][0]["temp_c"] == 25.0
    assert body["days"][0]["condition"] == "Clear sky"
    assert "source" not in body or body.get("source") != "unavailable"
    _memory_store.clear()


async def _ok_ai(loc, days):
    return {"ai_recommendation": None, "action": "none", "alerts": [], "source": "heuristic"}


def test_weather_with_location_param_still_labels(auth_client, monkeypatch):
    """The ?location= override keeps labeling the degraded payload."""
    from app.core.cache import _memory_store
    from app.services import weather_service

    _memory_store.clear()

    async def open_meteo_down(location, days=7, coordinates=None):
        raise ExternalServiceError("Weather provider unavailable")

    monkeypatch.setattr(weather_service, "fetch_weather_days", open_meteo_down)

    resp = auth_client.get("/api/v1/weather", params={"location": "Pune City Subdistrict"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["location"] == "Pune City Subdistrict"
    assert body["source"] == "unavailable"
    _memory_store.clear()
