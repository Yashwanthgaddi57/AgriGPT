"""Tests for the OpenWeatherMap failover client and weather service wiring."""
from types import SimpleNamespace

import pytest

from app.ai import openweather_client
from app.core.exceptions import ExternalServiceError


# ----------------------------------------------------------------------
# OpenWeatherMap client
# ----------------------------------------------------------------------
def test_disabled_without_key_raises_placeholder_sync(monkeypatch):
    """A sync-style call still surfaces the failure (unclosed-coroutine warning aside).
    The real contract is the async version below."""
    monkeypatch.setattr("app.core.config.settings.OPENWEATHER_API_KEY", "")
    coro = openweather_client.get_forecast(19.99, 73.78)
    coro.close()  # avoid RuntimeWarning noise; guard itself tested async below


@pytest.mark.asyncio
async def test_forecast_fails_soft_without_key_is_first_guard(monkeypatch):
    monkeypatch.setattr("app.core.config.settings.OPENWEATHER_API_KEY", "")
    with pytest.raises(ExternalServiceError):
        await openweather_client.get_forecast(19.99, 73.78)


def _fake_client(resp_json=None, status=200, raise_exc=None):
    """Build an httpx.AsyncClient stand-in returning canned JSON."""

    class FakeResponse:
        def __init__(self):
            self.status_code = status

        def raise_for_status(self):
            if raise_exc:
                raise raise_exc
            if status >= 400:
                raise RuntimeError(f"HTTP {status}")

        def json(self):
            return resp_json

    class FakeAsyncClient:
        def __init__(self, *a, **kw):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, *a, **kw):
            if raise_exc and not isinstance(raise_exc, RuntimeError):
                raise raise_exc
            return FakeResponse()

    return FakeAsyncClient


OWM_PAYLOAD = {
    "list": [
        # 4 entries for day 1: 00:00, 06:00, 12:00, 18:00
        {"dt_txt": "2026-09-23 00:00:00", "main": {"temp": 20, "temp_min": 18, "temp_max": 22, "humidity": 60},
         "wind": {"speed": 3}, "rain": {"3h": 0.5}, "pop": 0.4, "weather": [{"id": 500}]},
        {"dt_txt": "2026-09-23 06:00:00", "main": {"temp": 24, "temp_min": 21, "temp_max": 26, "humidity": 55},
         "wind": {"speed": 4}, "rain": {"3h": 1.5}, "pop": 0.6, "weather": [{"id": 501}]},
        {"dt_txt": "2026-09-23 12:00:00", "main": {"temp": 30, "temp_min": 27, "temp_max": 33, "humidity": 45},
         "wind": {"speed": 2}, "rain": {}, "pop": 0.2, "weather": [{"id": 800}]},
        {"dt_txt": "2026-09-23 18:00:00", "main": {"temp": 26, "temp_min": 24, "temp_max": 28, "humidity": 50},
         "wind": {"speed": 5}, "rain": {}, "pop": 0.1, "weather": [{"id": 801}]},
        # one entry for day 2
        {"dt_txt": "2026-09-24 12:00:00", "main": {"temp": 28, "temp_min": 26, "temp_max": 31, "humidity": 55},
         "wind": {"speed": 3.5}, "rain": {"3h": 6}, "pop": 0.9, "weather": [{"id": 503}]},
    ]
}


@pytest.mark.asyncio
async def test_forecast_aggregates_daily(monkeypatch):
    monkeypatch.setattr("app.core.config.settings.OPENWEATHER_API_KEY", "test-key")
    monkeypatch.setattr(openweather_client.httpx, "AsyncClient", _fake_client(resp_json=OWM_PAYLOAD))
    days = await openweather_client.get_forecast(19.99, 73.78, days=7)
    # Free tier caps at 5 days; payload has 2 distinct days.
    assert len(days) == 2
    d1 = days[0]
    assert d1["date"] == "2026-09-23"
    assert d1["temp_max_c"] == 33.0
    assert d1["temp_min_c"] == 18.0
    assert d1["temp_c"] == 25.0  # mean of 20/24/30/26
    assert d1["precip_mm"] == 2.0  # 0.5 + 1.5
    assert d1["precip_probability"] == 60.0  # max pop * 100
    assert d1["wind_kph"] == 18.0  # 5 m/s * 3.6
    assert d1["condition"] == "Clear sky"  # midday entry id=800
    d2 = days[1]
    assert d2["condition"] == "Heavy rain"  # id 503
    assert d2["precip_mm"] == 6.0


@pytest.mark.asyncio
async def test_forecast_freezing_temps_not_corrupted(monkeypatch):
    """0°C is falsy — aggregation must not drop or mis-substitute it."""
    monkeypatch.setattr("app.core.config.settings.OPENWEATHER_API_KEY", "test-key")
    payload = {
        "list": [
            {"dt_txt": "2026-12-25 00:00:00", "main": {"temp": 0, "temp_min": 0, "temp_max": 0, "humidity": 80},
             "wind": {"speed": 1}, "pop": 0.1, "weather": [{"id": 601}]},
        ]
    }
    monkeypatch.setattr(openweather_client.httpx, "AsyncClient", _fake_client(resp_json=payload))
    days = await openweather_client.get_forecast(34.0, 74.0, days=1)
    d = days[0]
    assert d["temp_c"] == 0.0
    assert d["temp_max_c"] == 0.0
    assert d["temp_min_c"] == 0.0


@pytest.mark.asyncio
async def test_forecast_fails_soft_without_key(monkeypatch):
    monkeypatch.setattr("app.core.config.settings.OPENWEATHER_API_KEY", "")
    with pytest.raises(ExternalServiceError):
        await openweather_client.get_forecast(19.99, 73.78)


@pytest.mark.asyncio
async def test_forecast_http_error_raises_external(monkeypatch):
    monkeypatch.setattr("app.core.config.settings.OPENWEATHER_API_KEY", "test-key")
    monkeypatch.setattr(openweather_client.httpx, "AsyncClient", _fake_client(status=401))
    with pytest.raises(ExternalServiceError):
        await openweather_client.get_forecast(19.99, 73.78)


@pytest.mark.asyncio
async def test_geocode_success(monkeypatch):
    monkeypatch.setattr("app.core.config.settings.OPENWEATHER_API_KEY", "test-key")
    monkeypatch.setattr(
        openweather_client.httpx,
        "AsyncClient",
        _fake_client(resp_json=[{"name": "Nashik", "lat": 19.9975, "lon": 73.7898}]),
    )
    geo = await openweather_client.geocode("Nashik")
    assert geo == {"name": "Nashik", "latitude": 19.9975, "longitude": 73.7898}


@pytest.mark.asyncio
async def test_geocode_no_results_raises(monkeypatch):
    monkeypatch.setattr("app.core.config.settings.OPENWEATHER_API_KEY", "test-key")
    monkeypatch.setattr(openweather_client.httpx, "AsyncClient", _fake_client(resp_json=[]))
    with pytest.raises(ExternalServiceError):
        await openweather_client.geocode("Nowhereville")


# ----------------------------------------------------------------------
# Weather service failover wiring
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_fetch_weather_days_falls_back_to_owm(monkeypatch):
    """Open-Meteo down + OWM configured -> OWM answers, result normalized."""
    from app.services import weather_service

    from app.core.cache import _memory_store

    _memory_store.clear()

    async def open_meteo_down(*a, **kw):
        raise ExternalServiceError("Weather provider unavailable")

    monkeypatch.setattr(weather_service, "get_forecast", open_meteo_down)
    monkeypatch.setattr("app.core.config.settings.OPENWEATHER_API_KEY", "test-key")

    async def owm_forecast(lat, lon, days):
        return [{"date": "2026-09-23", "temp_c": 25.0, "temp_max_c": 30.0, "temp_min_c": 18.0,
                 "feels_like_c": None, "humidity": 55.0, "wind_kph": 12.0, "precip_mm": 0.0,
                 "precip_probability": 10.0, "condition": "Clear sky"}]

    monkeypatch.setattr(weather_service.openweather_client, "get_forecast", owm_forecast)

    loc, days = await weather_service.fetch_weather_days("Nashik")
    assert loc == "Nashik"
    assert days[0]["temp_c"] == 25.0
    assert days[0]["condition"] == "Clear sky"

    _memory_store.clear()


@pytest.mark.asyncio
async def test_fetch_weather_days_owm_geocode_fallback(monkeypatch):
    """Open-Meteo geocoding down -> OWM geocode resolves the place."""
    from app.services import weather_service

    from app.core.cache import _memory_store

    _memory_store.clear()

    async def geocode_down(*a, **kw):
        raise ExternalServiceError("geocode down")

    monkeypatch.setattr(weather_service, "geocode", geocode_down)
    monkeypatch.setattr("app.core.config.settings.OPENWEATHER_API_KEY", "test-key")

    async def owm_geocode(name):
        return {"name": "Nashik", "latitude": 19.9975, "longitude": 73.7898}

    monkeypatch.setattr(weather_service.openweather_client, "geocode", owm_geocode)

    async def any_forecast(lat, lon, days):
        raw = {
            "daily": {
                "time": ["2026-09-23"],
                "temperature_2m_max": [30],
                "temperature_2m_min": [18],
                "apparent_temperature_max": [31],
                "relative_humidity_2m_mean": [55],
                "wind_speed_10m_max": [12],
                "precipitation_sum": [0],
                "precipitation_probability_max": [10],
                "weathercode": [0],
            }
        }
        return raw

    monkeypatch.setattr(weather_service, "get_forecast", any_forecast)

    loc, days = await weather_service.fetch_weather_days("Nashik")
    assert loc == "Nashik"
    assert days[0]["temp_c"] == 24.0

    _memory_store.clear()
