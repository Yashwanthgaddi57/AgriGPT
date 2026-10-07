"""Nearby agricultural services: map data for seed/pesticide/fertilizer shops,
input stores, equipment dealers, markets, feed shops, FPOs and agri services.

Data comes from the AgriGPT directory + OpenStreetMap (Overpass), merged and
deduplicated server-side. No vendor data is invented and no API keys are needed
to view the map.
"""
from fastapi import APIRouter, Query

from app.core.deps import CurrentUser, DBSession
from app.schemas.location import AgriNearbyOut, AgriServiceOut, LocationOut
from app.services.agri_services import (
    AGRI_CATEGORIES,
    CATEGORY_LABELS,
    SORTS,
    clamp_radius,
    nearby_agri_services,
)
from app.services.geo_service import geocode_reverse
from app.services.location_service import resolve_location_async

router = APIRouter(prefix="/agri", tags=["agri"])


@router.get("/categories")
async def categories() -> dict:
    """The category keys + farmer-friendly labels the UI filters by."""
    return {
        "categories": [
            {"key": key, "label": CATEGORY_LABELS[key]} for key in AGRI_CATEGORIES
        ]
    }


@router.get("/nearby", response_model=AgriNearbyOut)
async def nearby(
    user: CurrentUser,
    db: DBSession,
    lat: float | None = Query(None, ge=-90, le=90, description="Defaults to the farmer's saved location"),
    lng: float | None = Query(None, ge=-180, le=180),
    radius: int = Query(25, ge=1, le=100, description="Search radius in km (strictly applied)"),
    category: list[str] | None = Query(
        None,
        description="Repeatable and/or comma-separated: seeds, pesticide, fertilizer, agri_store, "
        "equipment, market, feed, fpo, services, produce_buyer",
    ),
    search: str | None = Query(None, max_length=120, description="Place or service text"),
    crop: str | None = Query(None, max_length=60),
    sort: str = Query("nearest", pattern="^(nearest|rating|name)$"),
    limit: int = Query(60, ge=1, le=200),
) -> AgriNearbyOut:
    """Agri services within `radius` km of (lat, lng), sorted by real distance."""
    if lat is None or lng is None:
        loc = await resolve_location_async(db, user)
        lat = loc.latitude if lat is None else lat
        lng = loc.longitude if lng is None else lng
        location = loc.to_dict()
    else:
        # Keep the response's location block honest: describe the coordinates
        # actually searched (e.g. a searched town), not the saved farm.
        rev = await geocode_reverse(lat, lng) or {}
        label = ", ".join(
            filter(None, [rev.get("village"), rev.get("district"), rev.get("state")])
        ) or f"{lat:.3f}, {lng:.3f}"
        location = {
            "latitude": lat,
            "longitude": lng,
            "precision": "search",
            "label": label,
            "village": rev.get("village"),
            "district": rev.get("district"),
            "state": rev.get("state"),
        }

    requested = [c.strip() for raw in (category or []) for c in (raw or "").split(",") if c.strip()]
    unknown = [c for c in requested if c not in AGRI_CATEGORIES]
    if unknown:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=422,
            detail=f"Unknown category: {', '.join(unknown)}. Valid: {', '.join(AGRI_CATEGORIES)}",
        )

    radius_km = clamp_radius(radius)
    results = await nearby_agri_services(
        db,
        lat,
        lng,
        radius_km=radius_km,
        categories=requested,
        search=search,
        crop=crop,
        sort=sort if sort in SORTS else "nearest",
        limit=limit,
    )

    note = None
    if not results:
        note = (
            f"No agricultural services found within {radius_km} km. "
            "Try a larger radius or search another town."
        )

    return AgriNearbyOut(
        results=[AgriServiceOut(**{k: v for k, v in r.items() if k in AgriServiceOut.model_fields}) for r in results],
        location=LocationOut(**location),
        radius_km=radius_km,
        total=len(results),
        categories=AGRI_CATEGORIES,
        note=note,
    )
