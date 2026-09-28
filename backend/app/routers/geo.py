"""Location-aware endpoints: resolve farmer location, nearby mandis & vendors."""
from fastapi import APIRouter, Query

from app.core.deps import CurrentUser, DBSession
from app.schemas.location import LocationOut, MandiOut, NearbyVendorsOut
from app.services.geo_service import geocode_forward, geocode_reverse
from app.services.location_service import resolve_location_async
from app.services.market_service import find_nearest_mandis
from app.services.vendor_service import nearby_vendors

router = APIRouter(prefix="/geo", tags=["geo"])


@router.get("/location", response_model=LocationOut)
async def my_location(user: CurrentUser, db: DBSession):
    """Best-known coordinates for the farmer + precision metadata."""
    return (await resolve_location_async(db, user)).to_dict()


@router.post("/location", response_model=LocationOut)
async def save_location(payload: dict, user: CurrentUser, db: DBSession):
    """Save exact coordinates (GPS or map pin) on the profile.

    Body: {latitude, longitude, source, village?, district?, state?}
    """
    from app.schemas.location import LocationUpdate

    data = LocationUpdate(**payload)
    user.latitude = data.latitude
    user.longitude = data.longitude
    user.location_source = data.source
    if data.village is not None:
        user.village = data.village
    if data.district is not None:
        user.district = data.district
    if data.state is not None:
        user.state = data.state
    db.add(user)
    db.flush()
    return (await resolve_location_async(db, user)).to_dict()


@router.get("/reverse")
async def reverse(lat: float = Query(..., ge=-90, le=90), lon: float = Query(..., ge=-180, le=180)):
    """Coordinates -> address parts (used by the map picker)."""
    return await geocode_reverse(lat, lon) or {"display_name": None}


@router.get("/search")
async def search(q: str = Query(min_length=2)):
    """Place-name search for the location picker fallback."""
    return await geocode_forward(q) or {}


@router.get("/mandis", response_model=list[MandiOut])
async def mandis(
    user: CurrentUser,
    db: DBSession,
    crop: str | None = None,
    limit: int = Query(5, ge=1, le=10),
):
    loc = await resolve_location_async(db, user)
    return find_nearest_mandis(db, loc.latitude, loc.longitude, crop, limit=limit)


@router.get("/vendors", response_model=NearbyVendorsOut)
async def vendors(
    user: CurrentUser,
    db: DBSession,
    category: str | None = Query(None, description="seeds|fertilizer|equipment|pesticide|produce_buyer"),
    crop: str | None = None,
    limit: int = Query(15, ge=1, le=50),
    radius_km: int = Query(
        50,
        ge=5,
        le=300,
        description=(
            "Search radius in km, strictly applied (never widened). When nothing "
            "lies within it, the nearest 3 vendors are returned tagged `beyond_radius`."
        ),
    ),
):
    loc = await resolve_location_async(db, user)
    items = await nearby_vendors(db, loc.latitude, loc.longitude, category, crop, limit, radius_km)
    # The radius is honest: items are all within radius_km, except up to 3
    # tagged `beyond_radius` (nearest fallbacks shown when the radius had
    # nothing, so the UI can explain instead of widening silently).
    return NearbyVendorsOut(
        location=LocationOut(**loc.to_dict()),
        radius_km=radius_km,
        total=len([v for v in items if not v.get("beyond_radius")]),
        items=items,
    )
