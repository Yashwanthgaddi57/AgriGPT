"""Market intelligence endpoints."""
import asyncio
import uuid as uuidlib

from fastapi import APIRouter

from app.core.deps import CurrentUser, DBSession, Pagination
from app.core.plans_service import check_quota
from app.models.market_prediction import MarketPrediction
from app.schemas.ai_features import MarketPredictionRequest
from app.services.activity_service import log_activity
from app.services.location_service import resolve_location_async
from app.services.market_service import (
    MarketService,
    find_nearest_mandis,
    price_snapshot_async,
    resolve_price_context,
)

router = APIRouter(prefix="/market", tags=["market"])


@router.get("/ticker")
async def price_ticker(user: CurrentUser, db: DBSession, crops: str | None = None):
    """Realtime price snapshot for the farmer's crops — no AI calls, cached 1h.

    Crops default to the farmer's watched list (latest profit prediction,
    recommendation, farm crops) padded with staples; pass ?crop=a,b to override.
    """
    ctx = resolve_price_context(db, user)
    if crops:
        requested = [c.strip().lower() for c in crops.split(",") if c.strip()]
    else:
        requested = ctx["crops"][:6]

    # Concurrent snapshots, each capped — a cold Agmarknet miss can never
    # hold the ticker for tens of seconds again.
    items = await asyncio.gather(
        *(
            price_snapshot_async(c, state=ctx["state"], district=ctx["district"])
            for c in requested
        )
    )
    items.sort(key=lambda s: (not s["is_live"], s["crop"]))
    return {
        "location": {"label": ctx["label"], "state": ctx["state"], "district": ctx["district"]},
        "items": items,
    }


@router.post("/analyze")
async def analyze(payload: MarketPredictionRequest, user: CurrentUser, db: DBSession):
    check_quota(db, user, "market_analyses")
    loc = await resolve_location_async(db, user)
    pred = await MarketService(db).analyze(str(user.id), payload, farmer_loc=loc.to_dict())
    log_activity(db, str(user.id), "market.analyzed", "market_prediction", str(pred.id), {"crop": payload.crop})
    return pred


@router.get("/predictions")
async def list_predictions(user: CurrentUser, db: DBSession, pagination: Pagination):
    q = (
        db.query(MarketPrediction)
        .filter(MarketPrediction.user_id == uuidlib.UUID(str(user.id)))
        .order_by(MarketPrediction.created_at.desc())
    )
    total = q.count()
    items = q.offset(pagination.offset).limit(pagination.page_size).all()
    return {"items": items, "total": total, "page": pagination.page, "page_size": pagination.page_size}


@router.get("/compare")
async def compare_markets(crop: str, user: CurrentUser, db: DBSession, limit: int = 5):
    """"Where should I sell?" — price snapshot per nearby mandi.

    Uses the same tiered price chain as the ticker (keyed feed > scrape >
    labeled baseline), scoped to each mandi's market name where possible.
    No AI calls; cached 1h per crop+market. Baseline rows are clearly
    flagged so estimates are never presented as live prices.
    """
    loc = await resolve_location_async(db, user)
    mandis = find_nearest_mandis(db, loc.latitude, loc.longitude, crop.lower(), limit=limit)
    if not mandis:
        return {
            "crop": crop,
            "location": loc.label,
            "items": [],
            "note": "Save your farm location to compare nearby mandis.",
        }

    snaps = await asyncio.gather(
        *(price_snapshot_async(crop, state=m["state"], district=m["district"]) for m in mandis)
    )
    items = []
    for m, snap in zip(mandis, snaps):
        items.append(
            {
                "mandi": m["name"],
                "district": m["district"],
                "state": m["state"],
                "distance_km": m["distance_km"],
                "price": snap["price"],
                "unit": snap["unit"],
                "trend_weekly_pct": snap["trend_weekly_pct"],
                "source": snap["source"],
                "is_live": snap["is_live"],
                "as_of": snap["as_of"],
            }
        )
    items.sort(key=lambda x: (-x["price"], x["distance_km"]))
    return {
        "crop": crop,
        "location": loc.label,
        "items": items,
        "note": (
            "Prices are per-mandi snapshots; 'est' rows are modeled "
            "baselines, not live quotes. Call the mandi for today's rate."
        ),
    }


@router.get("/history")
async def history(crop: str, user: CurrentUser, db: DBSession, limit: int = 30):
    """Latest stored predictions for a crop (trend over time of AI views)."""
    q = (
        db.query(MarketPrediction)
        .filter(
            MarketPrediction.user_id == uuidlib.UUID(str(user.id)),
            MarketPrediction.crop.ilike(crop),
        )
        .order_by(MarketPrediction.created_at.desc())
        .limit(limit)
    )
    return {"items": q.all()}
