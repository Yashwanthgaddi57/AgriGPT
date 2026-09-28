"""Weather intelligence service: Open-Meteo data + Claude agro-advice (cached).

Provider failover: Open-Meteo (keyless) is primary. If it fails and
OPENWEATHER_API_KEY is set, the OpenWeatherMap client answers with
already-normalized day dicts (no parse step needed).
"""
import asyncio
import logging
import uuid
from datetime import date

from sqlalchemy.orm import Session

from app.ai.claude_client import get_claude
from app.ai.prompts import WEATHER_AGENT_SYSTEM
from app.ai import openweather_client
from app.ai.weather_client import geocode, get_forecast, parse_forecast
from app.core.cache import cache_get, cache_set
from app.core.config import settings
from app.core.exceptions import ExternalServiceError
from app.models.weather_record import WeatherRecord

logger = logging.getLogger("app.services.weather")

# Compact prompt payload: the raw JSON dump was ~3x the tokens needed.
COMPACT_FIELDS = ("date", "temp_c", "temp_max_c", "temp_min_c", "humidity", "wind_kph", "precip_mm", "precip_probability", "condition")

# Hard cap on the AI advisory round-trip. Heuristics answer instantly when
# Claude is slow/unavailable, and a background refresh backfills real AI advice.
AI_ADVICE_TIMEOUT_S = 6.0

# Fire-and-forget tasks need a strong reference or the event loop may GC them.
_bg_tasks: set[asyncio.Task] = set()


def _spawn(coro) -> None:
    task = asyncio.create_task(coro)
    _bg_tasks.add(task)
    task.add_done_callback(_bg_tasks.discard)


async def fetch_weather_days(
    location: str, days: int = 7, coordinates: tuple[float, float] | None = None
) -> tuple[str, list[dict]]:
    """Geocode + fetch + normalize. Cached 30 min.

    When `coordinates` are given (farmer's saved pin) they take precedence over
    geocoding the location text — the forecast is for the exact farm spot.
    """
    coord_tag = f"@{coordinates[0]:.4f},{coordinates[1]:.4f}" if coordinates else ""
    cache_key = f"weather:{location.lower()}{coord_tag}:{days}"
    cached = cache_get(cache_key)
    if cached:
        return cached["location"], cached["days"]

    if coordinates:
        lat, lon = coordinates
        place_name = location.split(",")[0].strip() or f"{lat:.2f}, {lon:.2f}"
    else:
        try:
            geo = await geocode(location)
        except Exception as e:
            geo = await openweather_client.geocode(location) if openweather_client._enabled() else None
            if geo is None:
                raise ExternalServiceError(f"Geocoding unavailable for {location!r}") from e
        lat, lon = geo["latitude"], geo["longitude"]
        place_name = geo["name"]

    # Forecast with provider failover: Open-Meteo -> OpenWeatherMap.
    try:
        raw = await get_forecast(lat, lon, days)
        days_out = parse_forecast(raw)
    except Exception as e:
        logger.warning("Open-Meteo forecast failed (%s); trying OpenWeatherMap", e)
        days_out = await openweather_client.get_forecast(lat, lon, days)

    result = {"location": place_name, "days": days_out}
    cache_set(cache_key, result, ttl_seconds=1800)
    return place_name, days_out


def _compact_days(days: list[dict]) -> list[dict]:
    return [{k: d.get(k) for k in COMPACT_FIELDS} for d in days]


async def get_weather_summary_for_agent(user_id: str, location: str) -> str:
    """Compact weather brief consumed by the weather agent in chat."""
    try:
        loc, days = await fetch_weather_days(location or "Nashik", 7)
        lines = [
            f"{d['date']}: {d['condition']}, {d['temp_c']}°C, humidity {d['humidity']}%, "
            f"wind {d['wind_kph']} km/h, rain {d['precip_mm']}mm"
            for d in days
        ]
        return f"Location: {loc}\n" + "\n".join(lines)
    except Exception as e:
        logger.warning("Weather brief unavailable: %s", e)
        return "Weather data unavailable."


def _heuristic_alerts(days: list[dict]) -> list[str]:
    """Instant rule-based alerts — no AI call needed."""
    alerts: list[str] = []
    for d in days[:5]:
        rain = d.get("precip_mm") or 0
        tmax = d.get("temp_max_c")
        wind = d.get("wind_kph") or 0
        if rain >= 50:
            alerts.append(f"Heavy rain ({rain:.0f} mm) expected on {d['date']} — delay spraying and field work.")
        if tmax is not None and tmax >= 40:
            alerts.append(f"Heat wave risk: {tmax:.0f}°C on {d['date']} — irrigate early morning.")
        if wind >= 30:
            alerts.append(f"Strong winds ({wind:.0f} km/h) on {d['date']} — risk of lodging for tall crops.")
    return alerts


def _heuristic_action(days: list[dict]) -> str:
    rain_48h = sum((d.get("precip_mm") or 0) for d in days[:2])
    if rain_48h >= 40:
        return "delay_planting"
    if rain_48h >= 15:
        return "irrigate"
    tmax_avg = sum((d.get("temp_max_c") or 25) for d in days[:3]) / 3
    if tmax_avg >= 38:
        return "irrigate"
    return "none"


async def _ai_advice(loc: str, days: list[dict]) -> dict:
    """Claude agro-advisory, cached 3h per location."""
    cache_key = f"weather-ai:{loc.lower()}"
    cached = cache_get(cache_key)
    if cached:
        return cached

    try:
        claude = get_claude()
        prompt = (
            f"Location: {loc}\n"
            f"7-day forecast:\n{ _compact_days(days) }\n\n"
            "Assess farm actions for the coming week. Be concise."
        )
        ai = await asyncio.wait_for(
            claude.acomplete_json(
                system=WEATHER_AGENT_SYSTEM,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=700,
            ),
            timeout=AI_ADVICE_TIMEOUT_S,
        )
        result = {
            "ai_recommendation": ai.get("ai_recommendation"),
            "action": ai.get("action", "none"),
            "alerts": ai.get("alerts", []),
            "source": "ai",
        }
        cache_set(cache_key, result, ttl_seconds=3 * 3600)
        return result
    except Exception as e:
        logger.warning("Weather AI advice unavailable/slow, using heuristics: %s", e)
        heuristic = {
            "ai_recommendation": None,
            "action": _heuristic_action(days),
            "alerts": _heuristic_alerts(days),
            "source": "heuristic",
        }
        # Give the next request the real AI advice: retry in the background so
        # a slow model never blocks the farmer, it just arrives a moment later.
        if loc:
            _spawn(_ai_advice_refresh(loc, days))
        return heuristic


async def _ai_advice_refresh(loc: str, days: list[dict]) -> None:
    """Background: fetch AI advice and populate the cache (best-effort)."""
    try:
        claude = get_claude()
        prompt = (
            f"Location: {loc}\n"
            f"7-day forecast:\n{ _compact_days(days) }\n\n"
            "Assess farm actions for the coming week. Be concise."
        )
        ai = await claude.acomplete_json(
            system=WEATHER_AGENT_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=700,
        )
        cache_set(
            f"weather-ai:{loc.lower()}",
            {
                "ai_recommendation": ai.get("ai_recommendation"),
                "action": ai.get("action", "none"),
                "alerts": ai.get("alerts", []),
                "source": "ai",
            },
            ttl_seconds=3 * 3600,
        )
    except Exception as e:  # noqa: BLE001 — best-effort only
        logger.warning("Weather AI background refresh failed: %s", e)


class WeatherService:
    def __init__(self, db: Session):
        self.db = db

    async def get_intelligence(
        self,
        user_id: str,
        location: str,
        farm_id: str | None = None,
        save: bool = True,
        coordinates: tuple[float, float] | None = None,
    ) -> dict:
        """coordinates: exact (lat, lon) when known — skips text geocoding."""
        if coordinates:
            lat, lon = coordinates
            from app.ai.weather_client import get_forecast, parse_forecast
            from app.services.geo_service import geocode_reverse

            cache_key = f"weather:c:{round(lat, 3)}:{round(lon, 3)}:{7}"
            cached = cache_get(cache_key)
            if cached:
                loc, days = cached["location"], cached["days"]
            else:
                try:
                    raw = await get_forecast(lat, lon, 7)
                    days = parse_forecast(raw)
                except Exception as e:
                    logger.warning("Open-Meteo forecast failed (%s); trying OpenWeatherMap", e)
                    days = await openweather_client.get_forecast(lat, lon, 7)
                rev = await geocode_reverse(lat, lon)
                loc = (rev and (rev.get("village") or rev.get("district"))) or "your location"
                cache_set(cache_key, {"location": loc, "days": days}, ttl_seconds=1800)
        else:
            loc, days = await fetch_weather_days(location, 7)
        ai = await _ai_advice(loc, days)

        result = {
            "location": loc,
            "days": days,
            "ai_recommendation": ai.get("ai_recommendation"),
            "action": ai.get("action"),
            "alerts": ai.get("alerts", []),
        }

        if save and not getattr(self.db.get_bind(), "dialect", None).name.startswith("sqlite"):
            for d in days:
                self.db.add(
                    WeatherRecord(
                        user_id=uuid.UUID(user_id),
                        farm_id=uuid.UUID(farm_id) if farm_id else None,
                        location=loc,
                        record_date=date.fromisoformat(d["date"]),
                        temp_c=d.get("temp_c"),
                        feels_like_c=d.get("feels_like_c"),
                        humidity=d.get("humidity"),
                        wind_kph=d.get("wind_kph"),
                        precip_mm=d.get("precip_mm"),
                        precip_probability=d.get("precip_probability"),
                        condition=d.get("condition"),
                        alert="; ".join(ai.get("alerts", [])) or None,
                        ai_recommendation=ai.get("ai_recommendation"),
                        action=ai.get("action"),
                        model=settings.ANTHROPIC_MODEL,
                    )
                )
            self.db.flush()
        return result
