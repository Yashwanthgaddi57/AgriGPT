"""Dashboard aggregation service: widgets + charts from latest data."""
import asyncio
import logging
import time
import uuid
from datetime import date, timedelta

from sqlalchemy import func, or_

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.disease_report import DiseaseReport
from app.models.market_prediction import MarketPrediction
from app.models.profit_prediction import ProfitPrediction
from app.models.recommendation import Recommendation
from app.models.user import User
from app.core.cache import cache_get, cache_set
from app.services.weather_service import fetch_weather_days

logger = logging.getLogger("app.services.dashboard")

# Hard ceiling for any blocking network fetch during an overview load.
# The dashboard must never wait on the internet — cached data renders first.
WEATHER_TIMEOUT_S = 3.0
WEATHER_STALE_TTL_S = 24 * 3600  # serve last-good data up to a day old


async def get_dashboard(db: Session, user: User) -> dict:
    uid = uuid.UUID(str(user.id))

    # Latest profit prediction
    latest_profit = (
        db.query(ProfitPrediction)
        .filter(ProfitPrediction.user_id == uid)
        .order_by(ProfitPrediction.created_at.desc())
        .first()
    )

    # Latest crop recommendation (for current crop hint)
    latest_rec = (
        db.query(Recommendation)
        .filter(Recommendation.user_id == uid)
        .order_by(Recommendation.created_at.desc())
        .first()
    )

    # Disease alerts in last 14 days
    since = date.today() - timedelta(days=14)
    disease_alerts = (
        db.query(DiseaseReport)
        .filter(
            DiseaseReport.user_id == uid,
            DiseaseReport.created_at >= since,
            DiseaseReport.is_healthy.is_(False),
        )
        .order_by(DiseaseReport.created_at.desc())
        .limit(5)
        .all()
    )

    # Latest market predictions for recommendation cards
    market_preds = (
        db.query(MarketPrediction)
        .filter(MarketPrediction.user_id == uid)
        .order_by(MarketPrediction.created_at.desc())
        .limit(3)
        .all()
    )

    # Weather (live, not persisted here) — anchored to the farmer's exact pin
    from app.services.location_service import resolve_location_async

    loc = await resolve_location_async(db, user)
    location = loc.label
    coords = (
        (loc.latitude, loc.longitude) if loc.precision in ("gps", "map_pin") else None
    )
    weather_alerts: list[str] = []
    weather_days: list[dict] = []
    action = None
    try:
        wx = await _weather_fast(location, coords)
        weather_days = wx["days"]
        weather_alerts = wx["alerts"]
        action = wx["action"]
        ai_recommendation = wx.get("ai_recommendation")
        weather_stale = wx.get("stale", False)
    except Exception as e:
        logger.warning("Dashboard weather unavailable: %s", e)
        ai_recommendation = None
        weather_stale = False

    current_crop = (
        (latest_profit.crop if latest_profit else None)
        or (latest_rec.crops[0]["crop_name"] if latest_rec and latest_rec.crops else None)
        or user.soil_type and None  # fallback handled below
    )
    current_crop = current_crop or "Not set"

    # Charts: build series from latest profit prediction scenarios + history
    revenue_projection: list[dict] = []
    profit_projection: list[dict] = []
    yield_estimation: list[dict] = []
    if latest_profit:
        base_rev = float(latest_profit.expected_revenue or 0)
        base_profit = float(latest_profit.expected_profit or 0)
        base_yield = float(latest_profit.expected_yield_quintals or 0)
        months = ["Now", "M1", "M2", "M3", "M4", "Harvest"]
        ramp = [0.15, 0.35, 0.55, 0.75, 0.92, 1.0]
        for m, r in zip(months, ramp):
            revenue_projection.append({"label": m, "value": round(base_rev * r, 2)})
            profit_projection.append({"label": m, "value": round(base_profit * r, 2)})
            yield_estimation.append({"label": m, "value": round(base_yield * r, 2)})

    demand_forecast: list[dict] = []
    if market_preds:
        mp = market_preds[0]
        today = date.today()
        demand_forecast = [
            {"label": "Current", "value": float(mp.current_price or 0)},
            {"label": "+7d", "value": float(mp.price_forecast_7d or 0)},
            {"label": "+14d", "value": float(mp.price_forecast_14d or 0)},
            {"label": "+30d", "value": float(mp.price_forecast_30d or 0)},
        ]

    return {
        "location": {"label": loc.label, "precision": loc.precision, "latitude": loc.latitude, "longitude": loc.longitude},
        "farm": {
            "farm_size_acres": float(user.farm_size_acres or 0),
            "village": user.village,
            "district": user.district,
            "state": user.state,
            "soil_type": user.soil_type,
            "water_source": user.water_availability,
            "current_crop": current_crop,
            "current_season": _season_now(),
        },
        "crop_health": _crop_health_summary(db, uid),
        "widgets": {
            "current_crop": current_crop,
            "current_season": _season_now(),
            "expected_revenue": float(latest_profit.expected_revenue or 0) if latest_profit else 0,
            "expected_profit": float(latest_profit.expected_profit or 0) if latest_profit else 0,
            "risk_score": float(latest_profit.risk_score or 0) if latest_profit else 0,
            "disease_alerts": len(disease_alerts),
            "weather_alerts": weather_alerts,
            "weather_action": action,
            "ai_recommendation": ai_recommendation,
            "weather_stale": weather_stale,
            "market_recommendations": [
                {
                    "crop": mp.crop,
                    "price": float(mp.current_price or 0),
                    "recommendation": mp.recommendation,
                    "trend_weekly": float(mp.trend_weekly or 0),
                }
                for mp in market_preds
            ],
        },
        "charts": {
            "revenue_projection": revenue_projection,
            "profit_projection": profit_projection,
            "yield_estimation": yield_estimation,
            "demand_forecast": demand_forecast,
            "weather_forecast": weather_days,
        },
    }


def _season_now() -> str:
    """Indian cropping season by month."""
    m = date.today().month
    if m in (6, 7, 8, 9, 10):
        return "kharif"
    if m in (11, 12, 1, 2, 3):
        return "rabi"
    return "zaid"


def _crop_health_summary(db: Session, uid) -> dict:
    """Recent scans + open issues for the dashboard Crop Health card."""
    try:
        since = date.today() - timedelta(days=30)
        recent = (
            db.query(DiseaseReport)
            .filter(DiseaseReport.user_id == uid, DiseaseReport.created_at >= since)
            .order_by(DiseaseReport.created_at.desc())
            .limit(3)
            .all()
        )
        open_count = (
            db.query(DiseaseReport)
            .filter(
                DiseaseReport.user_id == uid,
                DiseaseReport.is_healthy.is_(False),
                or_(
                    DiseaseReport.followup_status.in_(["open", "monitoring"]),
                    DiseaseReport.followup_status.is_(None),
                ),
            )
            .count()
        )
        return {
            "recent_scans": [
                {
                    "id": str(r.id),
                    "crop": r.crop,
                    "disease_name": r.disease_name,
                    "is_healthy": r.is_healthy,
                    "severity": r.severity,
                    "followup_status": r.followup_status or ("open" if not r.is_healthy else None),
                    "image_url": r.image_url,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                }
                for r in recent
            ],
            "open_issues": open_count or 0,
        }
    except Exception as e:
        logger.warning("Crop health summary failed: %s", e)
        return {"recent_scans": [], "open_issues": 0}


async def _weather_lite(location: str, coordinates: tuple[float, float] | None = None) -> dict:
    """Weather + AI action for the dashboard, fully cached.

    Forecast: 30 min cache (inside fetch_weather_days).
    AI advice: 3 h cache (weather_service._ai_advice) — the dashboard used to
    call Claude directly here, adding seconds to EVERY overview load.
    """
    from app.services.weather_service import _ai_advice

    loc, days = await fetch_weather_days(location, 5, coordinates=coordinates)
    ai = await _ai_advice(loc, days)
    return {"days": days, "action": ai.get("action", "none"), "alerts": ai.get("alerts", []), "ai_recommendation": ai.get("ai_recommendation")}


def _weather_cache_key(location: str, coordinates: tuple[float, float] | None) -> str:
    coord_tag = f"@{coordinates[0]:.4f},{coordinates[1]:.4f}" if coordinates else ""
    return f"dashwx:{location.lower()}{coord_tag}"


# Fire-and-forget tasks need a strong reference or the event loop may GC them.
_bg_tasks: set[asyncio.Task] = set()


def _spawn(coro) -> None:
    task = asyncio.create_task(coro)
    _bg_tasks.add(task)
    task.add_done_callback(_bg_tasks.discard)


async def _weather_fast(location: str, coordinates: tuple[float, float] | None = None) -> dict:
    """Stale-while-revalidate weather: instant render, background refresh.

    1. Fresh cache hit (< 30 min)          -> serve immediately
    2. Stale but present (up to 24 h old)  -> serve immediately + background refresh
    3. Nothing cached                      -> blocking fetch, capped at 3 s
    """
    key = _weather_cache_key(location, coordinates)
    fresh = cache_get(f"{key}:data")
    if fresh:
        return fresh

    stale = cache_get(f"{key}:stale")
    if stale:
        # Fire-and-forget refresh so the NEXT overview load is fresh.
        _spawn(_weather_refresh(location, coordinates, key))
        return {**stale, "stale": True}

    # Cold start: allow one short blocking fetch so first paint has data.
    try:
        wx = await asyncio.wait_for(_weather_lite(location, coordinates), timeout=WEATHER_TIMEOUT_S)
        cache_set(f"{key}:data", wx, ttl_seconds=1800)
        cache_set(f"{key}:stale", wx, ttl_seconds=WEATHER_STALE_TTL_S)
        return wx
    except Exception:
        logger.warning("Dashboard weather cold fetch failed/slow for %r", location, exc_info=True)
        # Keep trying in the background — next load gets data.
        _spawn(_weather_refresh(location, coordinates, key))
        return {"days": [], "action": "none", "alerts": [], "ai_recommendation": None, "stale": True}


async def _weather_refresh(location: str, coordinates: tuple[float, float] | None, key: str) -> None:
    """Background refresh — populates :data and leaves the old copy in :stale."""
    started = time.monotonic()
    try:
        wx = await _weather_lite(location, coordinates)
        cache_set(f"{key}:data", wx, ttl_seconds=1800)
        cache_set(f"{key}:stale", wx, ttl_seconds=WEATHER_STALE_TTL_S)
        logger.info("Dashboard weather refreshed in %.0f ms (bg)", (time.monotonic() - started) * 1000)
    except Exception as e:
        logger.warning("Dashboard weather background refresh failed: %s", e)
