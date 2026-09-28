"""OpenWeatherMap client: automatic failover for forecast + geocoding.

Open-Meteo (keyless) stays the primary provider. When it fails — rate
limits, outages, regional blocks — these functions answer with the same
normalized shapes so weather_service needs no per-call branching:

  get_forecast(lat, lon, days) -> list[day-dict]   (already normalized)
  geocode(name)                -> {"name", "latitude", "longitude"}

Fail-soft: raises ExternalServiceError on any failure so callers can fall
back to their own degradation paths. Enabled only when OPENWEATHER_API_KEY
is set; otherwise functions raise immediately (cheap no-op failover).
"""
import logging
from collections import defaultdict
from datetime import datetime
from typing import Any

import httpx

from app.core.config import settings
from app.core.exceptions import ExternalServiceError

logger = logging.getLogger("app.weather.openweather")

FORECAST_URL = "https://api.openweathermap.org/data/2.5/forecast"
GEOCODE_URL = "https://api.openweathermap.org/geo/1.0/direct"
_UA = {"User-Agent": "AgriGPT/1.0 (support@agrigpt.app)"}

# OWM condition-id ranges -> human labels (aligned with the WMO vocabulary
# used by the Open-Meteo parser so downstream text stays consistent).
def _condition(code: int) -> str:
    if 200 <= code < 300:
        return "Thunderstorm"
    if 300 <= code < 400:
        return "Light drizzle"
    if 500 <= code < 600:
        return "Heavy rain" if code in (502, 503, 504, 522, 531) else "Slight rain"
    if 600 <= code < 700:
        return "Heavy snow" if code in (602, 622) else "Slight snow"
    if 700 <= code < 800:
        return "Fog" if code in (701, 741, 748) else "Haze"
    if code == 800:
        return "Clear sky"
    if code == 801:
        return "Mainly clear"
    if code == 802:
        return "Partly cloudy"
    return "Overcast"


def _enabled() -> bool:
    return bool(settings.OPENWEATHER_API_KEY)


async def geocode(name: str) -> dict[str, Any]:
    """Resolve a place name to lat/lon via OWM geocoding."""
    if not _enabled():
        raise ExternalServiceError("OpenWeatherMap not configured")
    try:
        async with httpx.AsyncClient(timeout=6, headers=_UA) as client:
            resp = await client.get(
                GEOCODE_URL,
                params={"q": name, "limit": 1, "appid": settings.OPENWEATHER_API_KEY},
            )
            resp.raise_for_status()
            results = resp.json() or []
            if not results:
                raise ExternalServiceError(f"No geocode result for {name!r}")
            r = results[0]
            return {
                "name": r.get("name") or r.get("local_names", {}).get("en", name),
                "latitude": r["lat"],
                "longitude": r["lon"],
            }
    except ExternalServiceError:
        raise
    except Exception as e:
        logger.warning("OWM geocode failed: %s", e)
        raise ExternalServiceError("OpenWeatherMap geocoding unavailable") from e


async def get_forecast(lat: float, lon: float, days: int = 7) -> list[dict[str, Any]]:
    """5-day/3-hour forecast aggregated into daily WeatherDay-shaped dicts.

    OWM's free tier serves 5 days; callers asking for more simply get 5.
    """
    if not _enabled():
        raise ExternalServiceError("OpenWeatherMap not configured")
    try:
        async with httpx.AsyncClient(timeout=8, headers=_UA) as client:
            resp = await client.get(
                FORECAST_URL,
                params={
                    "lat": lat,
                    "lon": lon,
                    "units": "metric",
                    "appid": settings.OPENWEATHER_API_KEY,
                },
            )
            if resp.status_code >= 400:
                raise ExternalServiceError(f"OpenWeatherMap forecast unavailable ({resp.status_code})")
            payload = resp.json()
    except ExternalServiceError:
        raise
    except Exception as e:
        logger.warning("OWM forecast failed: %s", e)
        raise ExternalServiceError("OpenWeatherMap forecast unavailable") from e

    buckets: dict[str, list[dict]] = defaultdict(list)
    for entry in payload.get("list", []):
        day = (entry.get("dt_txt") or "")[:10]
        if day:
            buckets[day].append(entry)

    out: list[dict[str, Any]] = []
    for day in sorted(buckets)[: min(days, 5)]:
        entries = buckets[day]
        mains = [e.get("main", {}) for e in entries]
        temps = [m.get("temp") for m in mains if m.get("temp") is not None]
        # Note: `or`-fallbacks would break at 0°C (falsy) — use explicit None checks.
        tmaxes = [m.get("temp_max") for m in mains if m.get("temp_max") is not None] or temps
        tmins = [m.get("temp_min") for m in mains if m.get("temp_min") is not None] or temps
        tmax = max(tmaxes) if tmaxes else None
        tmin = min(tmins) if tmins else None
        humidity = [m.get("humidity") for m in mains if m.get("humidity") is not None]
        wind_kph = max((e.get("wind", {}).get("speed") or 0) * 3.6 for e in entries)
        precip = sum(
            (e.get("rain", {}) or {}).get("3h", 0) + (e.get("snow", {}) or {}).get("3h", 0)
            for e in entries
        )
        pop = max((e.get("pop") or 0) for e in entries) * 100  # probability 0-1 -> %
        code = (entries[len(entries) // 2].get("weather") or [{}])[0].get("id", 800)
        out.append(
            {
                "date": day,
                "temp_c": round(sum(temps) / len(temps), 1) if temps else None,
                "temp_max_c": round(tmax, 1) if tmax is not None else None,
                "temp_min_c": round(tmin, 1) if tmin is not None else None,
                "feels_like_c": None,  # daily aggregation of feels-like is misleading; OWM path leaves it unset
                "humidity": round(sum(humidity) / len(humidity), 0) if humidity else None,
                "wind_kph": round(wind_kph, 1),
                "precip_mm": round(precip, 1),
                "precip_probability": round(pop, 0),
                "condition": _condition(int(code)),
            }
        )
    if not out:
        raise ExternalServiceError("OpenWeatherMap returned no forecast days")
    return out
