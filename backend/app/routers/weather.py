"""Weather intelligence endpoints."""
from fastapi import APIRouter

from app.core.deps import CurrentUser, DBSession
from app.services.activity_service import log_activity
from app.services.location_service import resolve_location_async
from app.services.weather_service import WeatherService

router = APIRouter(prefix="/weather", tags=["weather"])


@router.get("")
async def weather(location: str | None = None, user: CurrentUser = None, db: DBSession = None):
    """Exact farmer coordinates when available; otherwise geocoded/typed location."""
    loc = await resolve_location_async(db, user)
    coords = None
    if loc.precision in ("gps", "map_pin"):
        coords = (loc.latitude, loc.longitude)
    result = await WeatherService(db).get_intelligence(
        str(user.id), location or loc.label or loc.district or "Nashik", coordinates=coords
    )
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
