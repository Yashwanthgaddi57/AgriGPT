"""Weather intelligence endpoints."""
import logging

from fastapi import APIRouter

from app.core.deps import CurrentUser, DBSession
from app.core.exceptions import ExternalServiceError
from app.services.activity_service import log_activity
from app.services.location_service import resolve_location_async
from app.services.weather_service import WeatherService

logger = logging.getLogger("app.api.weather")

router = APIRouter(prefix="/weather", tags=["weather"])


# Neutral forecast shown when every weather provider failed. The farmer still
# gets a usable screen instead of a 502 — the dashboard is dominated by this
# endpoint, so one flaky upstream must not break the whole page.
_DEGRADED_DAYS = [
    {
        "date": "",
        "temp_c": None,
        "temp_max_c": None,
        "temp_min_c": None,
        "feels_like_c": None,
        "humidity": None,
        "wind_kph": None,
        "precip_mm": None,
        "precip_probability": None,
        "condition": "Data unavailable",
    }
]


@router.get("")
async def weather(location: str | None = None, user: CurrentUser = None, db: DBSession = None):
    """Exact farmer coordinates when available; otherwise geocoded/typed location.

    Fails soft: when both providers are unreachable the answer is a degraded
    200 (condition 'Data unavailable') rather than a 502, so the dashboard
    still renders and the next request retries the providers.
    """
    loc = await resolve_location_async(db, user)
    coords = None
    if loc.precision in ("gps", "map_pin"):
        coords = (loc.latitude, loc.longitude)
    try:
        result = await WeatherService(db).get_intelligence(
            str(user.id), location or loc.label or loc.district or "Nashik", coordinates=coords
        )
    except ExternalServiceError as e:
        # Nothing is cached on failure, so the next request retries providers.
        logger.warning("Weather providers unavailable for user %s: %s", user.id, e)
        result = {
            "location": location or loc.label or loc.district or "your location",
            "days": _DEGRADED_DAYS,
            "ai_recommendation": None,
            "action": "none",
            "alerts": ["Weather service is temporarily unavailable — showing limited data. Try refreshing in a minute."],
            "source": "unavailable",
        }
    if location:
        result["location"] = location
    log_activity(db, str(user.id), "weather.fetched", None, None, {"location": result["location"], "precision": loc.precision})
    return result


@router.get("/history")
async def history(user: CurrentUser, db: DBSession, limit: int = 30):
    import uuid as uuidlib

    from app.models.weather_record import WeatherRecord

    items = (
        db.query(WeatherRecord)
        .filter(WeatherRecord.user_id == uuidlib.UUID(str(user.id)))
        .order_by(WeatherRecord.record_date.desc())
        .limit(limit)
        .all()
    )
    return {"items": items}
