"""AgriGPT Decision Engine.

Combines verified inputs — farm profile, crop age, weather, crop health,
market snapshots, farm economics — into a deterministic TODAY'S FARM PLAN.

Design rules (from the master spec):
  - The engine NEVER invents data; it reasons over fetched/recorded values.
  - Every priority carries its basis ("Reason: 65% rain probability tomorrow").
  - Deterministic rule layers are cheap, cacheable and testable. An optional
    AI narrative is layered on top by the copilot, never for arithmetic.
"""
import asyncio
import logging
import uuid
from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.core.cache import cache_get, cache_set
from app.models.disease_report import DiseaseReport
from app.models.expense import Expense
from app.models.farm import Farm
from app.models.harvest import Harvest
from app.models.profit_prediction import ProfitPrediction
from app.models.user import User
from app.services.location_service import resolve_location_async
from app.services.weather_service import fetch_weather_days

logger = logging.getLogger("app.decision")

PRIORITY_SCALE = ("low", "medium", "high")


def _days_since(d: date | None) -> int | None:
    if d is None:
        return None
    days = (date.today() - d).days
    return days if days >= 0 else None


def _crop_stage(days: int | None) -> str | None:
    """Generic stage label by crop age. Conservative, crop-agnostic."""
    if days is None:
        return None
    if days <= 15:
        return "establishment"
    if days <= 45:
        return "vegetative"
    if days <= 75:
        return "flowering/fruiting"
    if days <= 110:
        return "grain/fruit development"
    return "maturity approaching"


def _rain_context(days: list[dict]) -> dict | None:
    """Rain decision context from the next 48h of forecast data."""
    if not days:
        return None
    today = days[0]
    tomorrow = days[1] if len(days) > 1 else None
    next48 = [today, tomorrow] if tomorrow else [today]
    rain_mm = sum((d.get("precip_mm") or 0) for d in next48)
    rain_prob = max((d.get("precip_probability") or 0) for d in next48)
    if rain_mm >= 20 or rain_prob >= 60:
        return {
            "level": "high",
            "rain_mm_48h": round(rain_mm, 1),
            "rain_probability_pct": rain_prob,
            "summary": f"Rain likely in the next 48 hours ({rain_mm:.0f} mm, {rain_prob}% probability).",
        }
    if rain_mm >= 5 or rain_prob >= 35:
        return {
            "level": "medium",
            "rain_mm_48h": round(rain_mm, 1),
            "rain_probability_pct": rain_prob,
            "summary": f"Some rain possible in the next 48 hours ({rain_mm:.0f} mm, {rain_prob}% probability).",
        }
    return None


def _disease_context(db: Session, uid) -> dict:
    since = date.today() - timedelta(days=21)
    recent = (
        db.query(DiseaseReport)
        .filter(
            DiseaseReport.user_id == uid,
            DiseaseReport.created_at >= since,
            DiseaseReport.is_healthy.is_(False),
        )
        .order_by(DiseaseReport.created_at.desc())
        .first()
    )
    if not recent:
        return {"has_open_issue": False}
    status = recent.followup_status or "open"
    return {
        "has_open_issue": status in ("open", "monitoring"),
        "crop": recent.crop,
        "possible_issue": recent.disease_name,
        "confidence": float(recent.confidence or 0),
        "severity": recent.severity,
        "followup_status": status,
        "days_ago": (date.today() - recent.created_at.date()).days,
    }


def _economics_context(db: Session, uid) -> dict:
    """Estimated economics (latest profit prediction) vs recorded reality."""
    latest = (
        db.query(ProfitPrediction)
        .filter(ProfitPrediction.user_id == uid)
        .order_by(ProfitPrediction.created_at.desc())
        .first()
    )
    expenses_total = (
        db.query(Expense)
        .filter(Expense.user_id == uid)
        .with_entities(Expense.amount_inr)
        .all()
    )
    spent = float(sum((e[0] or 0) for e in expenses_total)) if expenses_total else 0.0
    harvests = (
        db.query(Harvest)
        .filter(Harvest.user_id == uid)
        .order_by(Harvest.created_at.desc())
        .limit(1)
        .all()
    )
    last_harvest = None
    if harvests:
        h = harvests[0]
        last_harvest = {
            "crop": h.crop,
            "yield_quintals": float(h.actual_yield_quintals or 0),
            "price_per_quintal": float(h.selling_price_per_quintal or 0),
            "revenue_inr": float(h.revenue_inr or 0),
        }
    return {
        "estimated_cost": float(latest.total_cost or 0) if latest else 0,
        "estimated_revenue": float(latest.expected_revenue or 0) if latest else 0,
        "estimated_profit": float(latest.expected_profit or 0) if latest else 0,
        "crop": latest.crop if latest else None,
        "recorded_expenses_total": spent,
        "last_harvest": last_harvest,
    }


async def _market_context(crop: str | None, state: str | None, district: str | None) -> dict | None:
    if not crop:
        return None
    try:
        from app.services.market_service import price_snapshot_async

        snap = await price_snapshot_async(crop.lower(), state=state, district=district)
    except Exception as e:
        logger.warning("Market snapshot failed for %s: %s", crop, e)
        return None
    return {
        "crop": snap["crop"],
        "price": snap["price"],
        "unit": snap["unit"],
        "trend_weekly_pct": snap["trend_weekly_pct"],
        "source": snap["source"],
        "is_live": snap["is_live"],
        "as_of": snap["as_of"],
    }


def _priorities(
    *,
    rain: dict | None,
    health: dict,
    market: dict | None,
    economics: dict,
    stage: str | None,
    crop: str | None,
    days: int | None,
) -> list[dict]:
    """Ordered, rule-based priorities with stated basis. Deterministic."""
    priorities: list[dict] = []

    # 1. Open disease issue takes precedence — protecting the standing crop.
    if health.get("has_open_issue"):
        sev = health.get("severity", "medium")
        level = "high" if sev in ("high", "critical") else "medium"
        priorities.append({
            "rank": len(priorities) + 1,
            "icon": "health",
            "level": level,
            "title": f"Follow up on the {health.get('crop', '')} issue: {health.get('possible_issue', '')}".strip(),
            "detail": (
                f"A scan {health.get('days_ago', '?')} days ago flagged this possible issue "
                f"({health.get('confidence', 0):.0f}% confidence, follow-up status: {health.get('followup_status')}). "
                "Re-check the affected plants today."
            ),
            "basis": f"Scan from {health.get('days_ago', '?')} days ago; severity {sev}.",
        })

    # 2. Rain vs irrigation conflict.
    if rain and rain["level"] == "high":
        priorities.append({
            "rank": len(priorities) + 1,
            "icon": "weather",
            "level": "high",
            "title": "Hold irrigation — rain is likely",
            "detail": rain["summary"] + " Consider postponing irrigation and field spraying.",
            "basis": f"{rain['rain_probability_pct']}% rain probability / {rain['rain_mm_48h']} mm expected in 48h (Open-Meteo forecast).",
        })
    elif rain and rain["level"] == "medium":
        priorities.append({
            "rank": len(priorities) + 1,
            "icon": "weather",
            "level": "low",
            "title": "Check the forecast before irrigating",
            "detail": rain["summary"],
            "basis": f"{rain['rain_probability_pct']}% rain probability in 48h (Open-Meteo forecast).",
        })

    # 3. High-humidity disease window during sensitive stages.
    if stage in ("flowering/fruiting", "grain/fruit development"):
        priorities.append({
            "rank": len(priorities) + 1,
            "icon": "crop",
            "level": "medium",
            "title": f"Crop is in {stage} — monitor for disease-favorable humidity",
            "detail": (
                f"{(crop or 'The crop').capitalize()} is around day {days} ({stage}). "
                "Warm, humid days raise fungal risk; inspect lower leaves and dense canopy areas."
            ),
            "basis": f"Planting date on record; age {days} days.",
        })

    # 4. Market / sell timing when live price exists.
    if market:
        trend = market.get("trend_weekly_pct") or 0
        if trend <= -3:
            m_level, m_title = "medium", "Prices are sliding — review your sell timing"
            m_detail = f"{market['crop'].capitalize()} is {trend:+.1f}% this week at {market['price']:,.0f} {market['unit']}. If you're close to harvest, compare nearby mandis before committing."
        elif trend >= 3:
            m_level, m_title = "low", "Prices are rising — watch the trend"
            m_detail = f"{market['crop'].capitalize()} is up {trend:+.1f}% this week ({market['price']:,.0f} {market['unit']}). Worth monitoring before selling."
        else:
            m_level, m_title = "low", "Market is stable"
            m_detail = f"{market['crop'].capitalize()} is around {market['price']:,.0f} {market['unit']} ({trend:+.1f}% this week)."
        src = "live Agmarknet data" if market.get("is_live") else "modeled baseline estimate (no live feed)"
        priorities.append({
            "rank": len(priorities) + 1,
            "icon": "market",
            "level": m_level,
            "title": m_title,
            "detail": m_detail,
            "basis": f"Price source: {src}, as of {market.get('as_of')}.",
        })

    # 5. Economics: spent vs estimated cost.
    if economics.get("estimated_cost") and economics.get("recorded_expenses_total"):
        spent = economics["recorded_expenses_total"]
        est = economics["estimated_cost"]
        if spent > est * 1.2:
            priorities.append({
                "rank": len(priorities) + 1,
                "icon": "economics",
                "level": "medium",
                "title": "Recorded spending is above the estimate",
                "detail": f"You've recorded ₹{spent:,.0f} of expenses against an estimated total cost of ₹{est:,.0f}. Review remaining spend.",
                "basis": "Sum of your recorded expenses vs your latest profit estimate.",
            })

    # Always end with the safe default when nothing fired.
    if not priorities:
        priorities.append({
            "rank": 1,
            "icon": "crop",
            "level": "low",
            "title": "Walk your farm today",
            "detail": "No alerts fired from your weather, crop health or market data. A short field walk is the best baseline check.",
            "basis": "No open issues in your data for today.",
        })

    for i, p in enumerate(priorities[:4], start=1):
        p["rank"] = i
    return priorities[:4]


async def build_today_plan(db: Session, user: User, save: bool = True) -> dict:
    """Assemble the full TODAY context: farm, weather, health, market, economics,
    briefing lines and priorities. Deterministic; AI narrative added separately."""
    uid = uuid.UUID(str(user.id))

    # --- Farm context (profile or best farm record) ---
    farm = (
        db.query(Farm)
        .filter(Farm.user_id == uid)
        .order_by(Farm.planting_date.desc().nullslast(), Farm.created_at.desc())
        .first()
    )
    crop = (farm.current_crop if farm and farm.current_crop else None) or None
    planting = farm.planting_date if farm else None
    days = _days_since(planting)
    stage = _crop_stage(days)

    loc = await resolve_location_async(db, user)

    # --- Weather (real data, cached, fail-soft) ---
    coords = (loc.latitude, loc.longitude) if loc.precision in ("gps", "map_pin") else None
    weather_days: list[dict] = []
    try:
        _, weather_days = await fetch_weather_days(
            loc.label or loc.district or "India", 5, coordinates=coords
        )
    except Exception as e:
        logger.warning("Decision engine weather unavailable: %s", e)
    rain = _rain_context(weather_days)

    # --- Health / economics / market ---
    health = _disease_context(db, uid)
    economics = _economics_context(db, uid)
    market = await _market_context(crop or economics.get("crop"), loc.state, loc.district)

    priorities = _priorities(
        rain=rain, health=health, market=market, economics=economics,
        stage=stage, crop=crop, days=days,
    )

    weather_line = None
    if weather_days:
        d0 = weather_days[0]
        weather_line = {
            "summary": f"{d0.get('condition', '—')}, ~{d0.get('temp_c', '—')}°C, humidity {d0.get('humidity', '—')}%",
            "rain_probability": d0.get("precip_probability"),
            "rain_mm": d0.get("precip_mm"),
            "source": "Open-Meteo (live forecast)",
        }

    return {
        "generated_for": date.today().isoformat(),
        "farm": {
            "name": farm.name if farm else None,
            "size_acres": float(farm.area_acres) if farm and farm.area_acres else float(user.farm_size_acres or 0),
            "village": farm.village if farm else user.village,
            "district": farm.district if farm else user.district,
            "state": farm.state if farm else user.state,
            "crop": crop,
            "planting_date": planting.isoformat() if planting else None,
            "crop_age_days": days,
            "crop_stage": stage,
            "soil_type": farm.soil_type if farm else user.soil_type,
            "water_source": farm.water_source if farm else user.water_availability,
        },
        "weather": weather_line,
        "crop_health": health,
        "market": market,
        "economics": economics,
        "priorities": priorities,
        "disclaimer": (
            "Priorities are decision-support suggestions generated from your farm data, "
            "live weather and market feeds. They are not guarantees — verify important "
            "actions with your local agriculture officer."
        ),
    }
