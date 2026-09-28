"""Market intelligence service (location-aware).

Price data priority chain:
  1. Real Agmarknet modal prices (data.gov.in) when DATA_GOV_API_KEY is set —
     location-aware (market > district > state > national), freshness-checked,
     cached 6h per location key.
  2. Deterministic synthetic baseline (documented heuristic) when the feed is
     unavailable, the crop is unknown to the mapping, or the newest real record
     is stale beyond FRESHNESS_DAYS.

When the farmer has coordinates, the analysis is anchored to their real
nearest APMC mandis (from the seeded directory) and the exact coordinates are
passed to the AI, which sharpens seasonal/timing advice for their area.
"""
import asyncio
import logging
import time
import uuid
from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.ai.claude_client import get_claude
from app.ai.prompts import MARKET_FORECAST_SYSTEM
from app.core.cache import cache_get, cache_set
from app.core.config import settings
from app.core.exceptions import AIError
from app.models.farm import Farm
from app.models.market_prediction import MarketPrediction
from app.models.mandi import Mandi
from app.models.profit_prediction import ProfitPrediction
from app.models.recommendation import Recommendation
from app.models.user import User
from app.schemas.ai_features import MarketPredictionRequest
from app.services import agmarknet_client, agmarknet_scraper
from app.services.geo_service import haversine_km
from app.services.location_service import resolve_location

logger = logging.getLogger("app.services.market")

# Deterministic fallback baseline — used only when the real Agmarknet feed is
# unavailable (no DATA_GOV_API_KEY, network failure, or stale data).
BASE_PRICES: dict[str, int] = {
    "wheat": 2400, "rice": 2200, "paddy": 2100, "cotton": 6800, "sugarcane": 340,
    "maize": 2022, "soybean": 4600, "onion": 1600, "potato": 1200, "tomato": 1400,
    "gram": 5400, "chickpea": 5400, "mustard": 5100, "groundnut": 5800,
    "turmeric": 9500, "chilli": 12500, "cumin": 22000, "banana": 1500,
    "mango": 3200, "guava": 2400, "barley": 2100, "bajra": 2300, "jowar": 2900,
}


def synthetic_price_history(crop: str, days: int = 90) -> list[dict]:
    """Deterministic seeded walk around the crop's base price for history context."""
    import hashlib
    import math

    base = BASE_PRICES.get(crop.lower().strip(), 2500)
    out = []
    for d in range(days, -1, -1):
        day = date.today() - timedelta(days=d)
        seed = int(hashlib.sha256(f"{crop}:{day.isoformat()}".encode()).hexdigest()[:8], 16)
        wave = math.sin(seed % 360) * 0.04 + ((seed % 100) / 100 - 0.5) * 0.03
        price = round(base * (1 + wave), 2)
        out.append({"date": day.isoformat(), "price": price})
    return out


# Crops pre-seeded for the realtime price ticker / market alert scans.
TICKER_CROPS: list[str] = [
    "wheat", "rice", "paddy", "maize", "cotton", "sugarcane", "soybean",
    "onion", "potato", "tomato", "gram", "mustard", "groundnut", "turmeric",
]


def resolve_price_context(db: Session, user: User) -> dict:
    """Farmer's price context (location + watched crops) for realtime features.

    Watched crops come from the latest profit prediction and crop
    recommendation, padded with the default ticker list. Sync on purpose —
    only local DB reads, no network.
    """
    loc = resolve_location(db, user)
    crops: list[str] = []

    latest_profit = (
        db.query(ProfitPrediction)
        .filter(ProfitPrediction.user_id == user.id)
        .order_by(ProfitPrediction.created_at.desc())
        .first()
    )
    if latest_profit and latest_profit.crop:
        name = latest_profit.crop.lower().strip()
        if name:
            crops.append(name)

    latest_rec = (
        db.query(Recommendation)
        .filter(Recommendation.user_id == user.id)
        .order_by(Recommendation.created_at.desc())
        .first()
    )
    if latest_rec and latest_rec.crops:
        first = latest_rec.crops[0]
        name = (first.get("crop_name") or first.get("name") if isinstance(first, dict) else str(first)) or ""
        name = name.lower().strip()
        if name and name not in crops:
            crops.append(name)

    farms = db.query(Farm).filter(Farm.user_id == user.id).all()
    for f in farms:
        if f.current_crop:
            name = f.current_crop.lower().strip()
            if name and name not in crops:
                crops.append(name)

    for c in TICKER_CROPS:
        if len(crops) >= 6:
            break
        if c not in crops:
            crops.append(c)

    return {
        "label": loc.label,
        "state": loc.state,
        "district": loc.district,
        "crops": crops,
    }


def price_snapshot(
    crop: str, state: str | None = None, district: str | None = None
) -> dict:
    """Cheapest realtime price read for one crop — tiered source, NO AI calls.

    Same source chain as MarketService.analyze (keyed feed > scrape >
    baseline) but without the Claude round-trip, so it is safe to call for a
    dozen crops at once. Cached 1h.

    NOTE: performs blocking network calls (data.gov.in). Never call from an
    async handler — use `price_snapshot_async` instead.
    """
    crop_key = crop.lower().strip()
    cache_key = f"ticker:{crop_key}:{(state or '').lower()}:{(district or '').lower()}"
    cached = cache_get(cache_key)
    if cached is not None:
        return cached

    source, history, meta = "baseline", [], {}
    for scope, kwargs in (
        ("district", {"district": district} if district else None),
        ("state", {"state": state} if state else None),
        ("national", {}),
    ):
        if kwargs is None:
            continue
        points = agmarknet_client.fetch_mandi_prices(crop_key, **kwargs)
        if points:
            source, history, meta = f"agmarknet_{scope}", points, {"scope": scope}
            break

    if not history:
        history = synthetic_price_history(crop_key)
        source = "baseline"

    current = history[-1]["price"]
    week_ago = history[-8]["price"] if len(history) >= 8 else current
    snap = {
        "crop": crop_key,
        "price": current,
        "unit": "INR/quintal",
        "trend_weekly_pct": _trend_pct(current, week_ago),
        "history": history[-14:],
        "source": source,
        "source_meta": meta,
        "is_live": source != "baseline",
        "as_of": history[-1]["date"],
    }
    cache_set(cache_key, snap, ttl_seconds=3600)
    return snap


# Hard cap for a cold price snapshot (Agmarknet HTTP + scrape). Cold misses
# resolve to the deterministic baseline inside this budget; a background
# refresh backfills the real live feed for the next request.
SNAPSHOT_TIMEOUT_S = 4.0

# Fire-and-forget tasks need a strong reference or the event loop may GC them.
_bg_tasks: set[asyncio.Task] = set()


def _spawn_snapshot(coro) -> None:
    task = asyncio.create_task(coro)
    _bg_tasks.add(task)
    task.add_done_callback(_bg_tasks.discard)


async def price_snapshot_async(
    crop: str, state: str | None = None, district: str | None = None
) -> dict:
    """Async-safe price snapshot with a hard latency cap.

    Cache hits return instantly. On a cold cache the blocking fetch runs in a
    worker thread, capped at SNAPSHOT_TIMEOUT_S; on timeout the deterministic
    baseline is served and a background refresh populates the cache with the
    live feed for subsequent requests.
    """
    crop_key = crop.lower().strip()
    cache_key = f"ticker:{crop_key}:{(state or '').lower()}:{(district or '').lower()}"
    cached = cache_get(cache_key)
    if cached is not None:
        return cached

    started = time.monotonic()
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(price_snapshot, crop_key, state, district),
            timeout=SNAPSHOT_TIMEOUT_S,
        )
    except asyncio.TimeoutError:
        logger.warning(
            "Price snapshot timed out after %.1fs for %r; serving baseline + bg refresh",
            time.monotonic() - started,
            crop_key,
        )
        _spawn_snapshot(asyncio.to_thread(price_snapshot, crop_key, state, district))
        history = synthetic_price_history(crop_key)
        current = history[-1]["price"]
        week_ago = history[-8]["price"] if len(history) >= 8 else current
        return {
            "crop": crop_key,
            "price": current,
            "unit": "INR/quintal",
            "trend_weekly_pct": _trend_pct(current, week_ago),
            "history": history[-14:],
            "source": "baseline",
            "source_meta": {},
            "is_live": False,
            "as_of": history[-1]["date"],
        }


def _weekly_series(history: list[dict], weeks: int = 8) -> list[dict]:
    """Downsample daily history to one point per week: 8 numbers, not 45 lines."""
    series = []
    for i in range(0, len(history), 7):
        chunk = history[i : i + 7]
        if chunk:
            series.append(
                {
                    "date": chunk[0]["date"],
                    "price": round(sum(p["price"] for p in chunk) / len(chunk), 2),
                }
            )
    return series[-weeks:]


def _trend_pct(current: float, past: float) -> float:
    if not past:
        return 0.0
    return round((current - past) / past * 100, 2)


def _heuristic_analysis(crop: str, history: list[dict]) -> dict:
    """Deterministic fallback so the feature always returns a usable analysis."""
    current = history[-1]["price"]
    week_ago = history[-8]["price"] if len(history) >= 8 else current
    month_ago = history[-30]["price"] if len(history) >= 30 else current
    quarter_ago = history[0]["price"] if history else current

    w = _trend_pct(current, week_ago)
    m = _trend_pct(current, month_ago)
    q = _trend_pct(current, quarter_ago)
    momentum = w + m * 0.5

    if momentum <= -3:
        rec = "sell_now"
        reasoning = (
            f"Prices are sliding (weekly {w:+.1f}%, monthly {m:+.1f}%). Selling now avoids "
            f"further erosion; storage will not recover the trend within two weeks."
        )
    elif momentum >= 3:
        rec = "wait_1_week" if abs(m) < 12 else "wait_2_weeks"
        reasoning = (
            f"Prices are rising (weekly {w:+.1f}%, monthly {m:+.1f}%). Waiting could capture "
            f"about Rs.{abs(current * momentum / 100):.0f}/quintal more if the trend holds."
        )
    else:
        rec = "sell_now"
        reasoning = (
            f"Prices are flat (weekly {w:+.1f}%, monthly {m:+.1f}%). With no clear upside and "
            f"storage cost/spoilage risk, selling at the current Rs.{current:,.0f}/quintal is safer."
        )

    return {
        "current_price": current,
        "trend_weekly": w,
        "trend_monthly": m,
        "trend_quarterly": q,
        "demand_forecast": "rising" if momentum > 3 else ("falling" if momentum < -3 else "stable"),
        "supply_forecast": "falling" if momentum > 3 else ("rising" if momentum < -3 else "stable"),
        "price_forecast_7d": round(current * (1 + max(min(w, 8), -8) / 100), 2),
        "price_forecast_14d": round(current * (1 + max(min(w + m * 0.5, 12), -12) / 100), 2),
        "price_forecast_30d": round(current * (1 + max(min(m, 15), -15) / 100), 2),
        "recommendation": rec,
        "confidence": 55.0,
        "reasoning": reasoning,
    }


def find_nearest_mandis(
    db: Session, lat: float, lon: float, crop: str | None = None, limit: int = 3
) -> list[dict]:
    """Nearest mandis from the directory, optionally preferring the crop."""
    mandis = db.query(Mandi).all()
    if not mandis:
        return []
    scored = []
    crop_lower = (crop or "").lower()
    for m in mandis:
        d = haversine_km(lat, lon, float(m.latitude), float(m.longitude))
        crop_bonus = -25.0 if crop_lower and crop_lower in [c.lower() for c in (m.major_crops or [])] else 0.0
        scored.append((d + crop_bonus, d, m))
    scored.sort(key=lambda t: t[0])
    return [
        {
            "id": str(m.id),
            "name": m.name,
            "city": m.city,
            "district": m.district,
            "state": m.state,
            "distance_km": round(d, 1),
            "major_crops": m.major_crops or [],
        }
        for _, d, m in scored[:limit]
    ]


class MarketService:
    def __init__(self, db: Session):
        self.db = db

    async def analyze(
        self,
        user_id: str,
        req: MarketPredictionRequest,
        farmer_loc: dict | None = None,
    ) -> MarketPrediction:
        crop_key = req.crop.lower().strip()
        loc_tag = farmer_loc["label"] if farmer_loc else "national"
        cache_key = f"market:{crop_key}:{(req.market or loc_tag).lower()}"
        cached = cache_get(cache_key)

        mandis: list[dict] = []
        if farmer_loc:
            mandis = find_nearest_mandis(
                self.db, farmer_loc["latitude"], farmer_loc["longitude"], crop_key, limit=3
            )

        # ---- Price source chain: keyed feed > keyless scrape > baseline ----
        state = farmer_loc.get("state") if farmer_loc else None
        district = farmer_loc.get("district") if farmer_loc else None
        market_name = (req.market or (mandis[0]["name"] if mandis else None))
        source = "baseline"
        history: list[dict] = []
        source_meta: dict = {}

        # Tier 1: keyed data.gov.in feed — most specific scope first. Scopes
        # run concurrently on worker threads (blocking client — never on the
        # event loop); the freshest scope wins.
        tier1_scopes = [
            (scope, kwargs)
            for scope, kwargs in (
                ("market", {"market": market_name} if market_name else None),
                ("district", {"district": district} if district else None),
                ("state", {"state": state} if state else None),
                ("national", {}),
            )
            if kwargs is not None
        ]
        tier1_results = await asyncio.gather(
            *(
                asyncio.to_thread(agmarknet_client.fetch_mandi_prices, req.crop, **kwargs)
                for _, kwargs in tier1_scopes
            ),
            return_exceptions=True,
        )
        for (scope, _), points in zip(tier1_scopes, tier1_results):
            if isinstance(points, BaseException):
                continue
            if points and agmarknet_client.latest_fresh_price(points) is not None:
                history = points
                source = f"agmarknet_{scope}"
                # Remember the top mandis seen at this scope for transparency.
                source_meta = {
                    "scope": scope,
                    "commodity": (agmarknet_client.AGMARKNET_COMMODITY.get(crop_key) or [None])[0],
                }
                break

        # Tier 2: keyless scrape of the public Agmarknet grid, location-filtered
        # (district/market match preferred; falls back to whole-state rows).
        if not history and state:
            try:
                scraped = await agmarknet_scraper.scrape_prices(
                    req.crop, state=state, district=district, market=market_name, days=90
                )
            except Exception as e:  # never let the scrape tier break the request
                logger.warning("Agmarknet scrape tier failed: %s", e)
                scraped = []
            if scraped and agmarknet_client.latest_fresh_price(scraped) is not None:
                history = scraped
                source = "agmarknet_scraped_state"
                source_meta = {
                    "scope": "scraped_state",
                    "commodity": agmarknet_scraper.AGMARKNET_COMMODITY.get(crop_key),
                    "district": district,
                    "market": market_name,
                }

        if not history:
            history = synthetic_price_history(req.crop)
            source = "baseline"

        current_price = history[-1]["price"]

        if cached:
            data = cached
        else:
            series = _weekly_series(history, weeks=8)
            location_block = ""
            if farmer_loc:
                location_block = (
                    f"\nFarmer location: {farmer_loc['label']} "
                    f"(lat {farmer_loc['latitude']:.4f}, lon {farmer_loc['longitude']:.4f}, "
                    f"precision: {farmer_loc['precision']})\n"
                )
                if mandis:
                    location_block += (
                        "Nearest mandis (name, district, distance km, major crops):\n"
                        + "\n".join(
                            f"- {m['name']}, {m['district']}, {m['distance_km']} km, crops: {', '.join(m['major_crops']) or 'n/a'}"
                            for m in mandis
                        )
                        + "\n"
                    )
            prompt = (
                f"Crop: {req.crop}\n"
                f"Market: {req.market or (loc_tag + ' region')}\n"
                f"Current price: INR {current_price}/quintal\n"
                f"Price source: {source} ({'real Agmarknet APMC data via data.gov.in' if source != 'baseline' else 'modeled baseline, not live market data'})\n"
                f"{location_block}\n"
                f"Recent weekly average prices (oldest to latest, INR/quintal):\n"
                + "\n".join(f"{p['date']}: {p['price']}" for p in series)
                + "\n\nReturn ONLY the JSON object per the schema. Keep reasoning under 60 words. No commentary."
            )
            try:
                data = await get_claude().acomplete_json(
                    system=MARKET_FORECAST_SYSTEM,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=1500,
                )
                cache_set(cache_key, data, ttl_seconds=3600)
            except AIError as e:
                logger.warning("AI market analysis unavailable (%s); using heuristic analysis", e)
                data = _heuristic_analysis(req.crop, history)
            except Exception as e:
                logger.exception("Market analysis failed")
                data = _heuristic_analysis(req.crop, history)

        pred = MarketPrediction(
            user_id=uuid.UUID(user_id),
            crop=req.crop,
            market=(mandis[0]["name"] if mandis else req.market),
            current_price=float(data.get("current_price", current_price)),
            price_unit="INR/quintal",
            trend_weekly=float(data.get("trend_weekly", 0)),
            trend_monthly=float(data.get("trend_monthly", 0)),
            trend_quarterly=float(data.get("trend_quarterly", 0)),
            demand_forecast=data.get("demand_forecast", "stable"),
            supply_forecast=data.get("supply_forecast", "stable"),
            price_forecast_7d=float(data.get("price_forecast_7d", current_price)),
            price_forecast_14d=float(data.get("price_forecast_14d", current_price)),
            price_forecast_30d=float(data.get("price_forecast_30d", current_price)),
            recommendation=data.get("recommendation", "hold"),
            confidence=float(data.get("confidence", 50)),
            reasoning=data.get("reasoning"),
            price_history=history,
            data_source=source,
            source_meta=source_meta or None,
            model=settings.ANTHROPIC_MODEL,
        )
        self.db.add(pred)
        self.db.flush()
        return pred
