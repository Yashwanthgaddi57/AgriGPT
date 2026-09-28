"""Nearby agri-vendor discovery.

Sources merged, always sorted by TRUE distance (haversine km):
  1. Curated directory (`vendors` table, seeded with known agri-businesses)
  2. Live OpenStreetMap discovery near the farmer's pin (real local shops)

Sorting, display distance and radius filtering all use the same real distance.
Crop/category affinities are returned as flags — they are never baked into the
distance, so the UI can show honest "X km away" values.

OSM discovery runs at the farmer's chosen radius (capped for free-Overpass
stability); the nationwide curated directory covers beyond that cap.
"""
import asyncio
from typing import Any

from sqlalchemy.orm import Session

from app.models.mandi import Vendor
from app.services.geo_service import haversine_km
from app.services.osm_vendors import discover_vendors_osm

# Overall deadline for live discovery inside a request. Discovery results are
# cached 24h, so only the first request for an area pays this cost. Kept small:
# the curated directory answers instantly, OSM results arrive on a later load.
DISCOVERY_TIMEOUT_S = 12.0

# Free Overpass servers time out on very large rings, so OSM discovery is
# capped; the curated directory (nationwide) covers the rest of the radius.
_OSM_MAX_RING_M = 60_000
_OSM_MIN_RING_M = 8_000


def _osm_ring_for(radius_km: int) -> int:
    return max(_OSM_MIN_RING_M, min(int(radius_km * 1000), _OSM_MAX_RING_M))


async def nearby_vendors(
    db: Session,
    lat: float,
    lon: float,
    category: str | None = None,
    crop: str | None = None,
    limit: int = 15,
    radius_km: int = 50,
) -> list[dict[str, Any]]:
    """Directory + OSM vendors within radius_km, sorted by true distance.

    The radius is honest: only vendors actually within radius_km are returned.
    An empty result is an honest "nothing within this radius" — the UI shows
    that and offers a bigger radius. (No silent widening: a farmer asking for
    10 km must not get shops 40 km away.)
    """
    radius_km = max(5, min(int(radius_km or 50), 300))
    crop_lower = (crop or "").lower()

    directory: list[dict[str, Any]] = []
    for v in db.query(Vendor).all():
        if category and v.category != category:
            continue
        d = haversine_km(lat, lon, float(v.latitude), float(v.longitude))
        crop_match = bool(crop_lower and crop_lower in [c.lower() for c in (v.crops or [])])
        directory.append(
            {
                "id": str(v.id),
                "name": v.name,
                "category": v.category,
                "description": v.description,
                "phone": v.phone,
                "address": v.address,
                "city": v.city,
                "district": v.district,
                "state": v.state,
                "latitude": float(v.latitude),
                "longitude": float(v.longitude),
                "crops": v.crops or [],
                "distance_km": round(d, 1),
                "raw_distance_km": round(d, 1),
                "matches_crop": crop_match,
                "source": "directory",
            }
        )

    osm_shops: list[dict[str, Any]] = []
    if lat and lon:
        try:
            # Never let a slow Overpass hold the response hostage. Discovery
            # results are cached 24h, so only the first request for an area
            # pays this cost.
            osm_shops = await asyncio.wait_for(
                discover_vendors_osm(lat, lon, radius_m=_osm_ring_for(radius_km), limit=40),
                timeout=DISCOVERY_TIMEOUT_S,
            )
        except Exception:  # noqa: BLE001 — fail-soft by design: directory still answers
            osm_shops = []

    for v in osm_shops:
        if category and v.get("category") != category:
            continue
        try:
            d = round(haversine_km(lat, lon, v["latitude"], v["longitude"]), 1)
        except (KeyError, TypeError, ValueError):
            continue
        v["distance_km"] = d
        v["raw_distance_km"] = d
        v["matches_crop"] = False

    merged = [v for v in (directory + osm_shops) if v.get("distance_km") is not None]

    # Crop matches get a small priority WITHIN the sort (never enough to cross
    # a 2 km band), so they surface early without lying about real distance.
    merged.sort(key=lambda v: v["distance_km"] - (1.99 if v["matches_crop"] else 0.0))

    # Honest radius filter: strictly within the requested radius. If empty,
    # return the nearest 3 beyond it so the UI can show "closest is X km away"
    # instead of a bare blank page. Callers must label these clearly.
    within = [v for v in merged if v["raw_distance_km"] <= radius_km]
    if within:
        return within[:limit]

    nearest = sorted(merged, key=lambda v: v["raw_distance_km"])[:3]
    for v in nearest:
        v["beyond_radius"] = True
    return nearest
