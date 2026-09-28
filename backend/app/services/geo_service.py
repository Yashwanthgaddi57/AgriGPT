"""Geo utilities: distance, forward/reverse geocoding.

Forward geocoding uses Open-Meteo's keyless geocoder; reverse geocoding uses
Nominatim (OpenStreetMap). All helpers are cached and fail-soft: location
features degrade to district level when the network is unavailable.
"""
import logging
import math
from typing import Any

import httpx

from app.core.cache import cache_get, cache_set

logger = logging.getLogger("app.geo")

OPEN_METEO_GEOCODE = "https://geocoding-api.open-meteo.com/v1/search"
NOMINATIM_REVERSE = "https://nominatim.openstreetmap.org/reverse"
NOMINATIM_SEARCH = "https://nominatim.openstreetmap.org/search"
_UA = {"User-Agent": "AgriGPT/1.0 (support@agrigpt.app)"}

EARTH_RADIUS_KM = 6371.0088


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two points in kilometres."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


async def geocode_forward(location: str) -> dict[str, Any] | None:
    """Place name -> {name, latitude, longitude, admin1, country}. Cached 24h."""
    key = f"geo:fw:{location.lower().strip()}"
    cached = cache_get(key)
    if cached:
        return cached
    try:
        async with httpx.AsyncClient(timeout=5, headers=_UA) as client:
            resp = await client.get(
                OPEN_METEO_GEOCODE,
                params={"name": location, "count": 1, "language": "en", "format": "json"},
            )
            resp.raise_for_status()
            results = resp.json().get("results") or []
            if not results:
                # Open-Meteo's geocoder is spelling-intolerant (village names in
                # India have many transliterations). Fall back to Nominatim,
                # which is fuzzier about spelling.
                return await _nominatim_search(location, key)
            r = results[0]
            out = {
                "name": r.get("name", location),
                "latitude": float(r["latitude"]),
                "longitude": float(r["longitude"]),
                "admin1": r.get("admin1"),
                "country": r.get("country"),
            }
            cache_set(key, out, ttl_seconds=86400)
            return out
    except Exception as e:
        logger.warning("Forward geocode failed for %s: %s", location, e)
        return None


async def _nominatim_search(location: str, cache_key: str) -> dict[str, Any] | None:
    """Nominatim forward search fallback (spelling-tolerant). Cached 24h."""
    try:
        async with httpx.AsyncClient(timeout=5, headers=_UA) as client:
            resp = await client.get(
                NOMINATIM_SEARCH,
                params={
                    "q": location,
                    "format": "jsonv2",
                    "limit": 1,
                    "addressdetails": 1,
                    "countrycodes": "in",
                },
            )
            resp.raise_for_status()
            results = resp.json() or []
            if not results:
                return None
            r = results[0]
            addr = r.get("address", {}) or {}
            out = {
                "name": r.get("name") or (r.get("display_name") or location).split(",")[0].strip(),
                "latitude": float(r["lat"]),
                "longitude": float(r["lon"]),
                "admin1": addr.get("state"),
                "country": addr.get("country") or r.get("addresstype") and "India" or None,
            }
            cache_set(cache_key, out, ttl_seconds=86400)
            return out
    except Exception as e:
        logger.warning("Nominatim search failed for %s: %s", location, e)
        return None


async def geocode_reverse(lat: float, lon: float) -> dict[str, Any] | None:
    """Coordinates -> nearest address parts (village/district/state). Cached 24h."""
    key = f"geo:rv:{round(lat, 4)}:{round(lon, 4)}"
    cached = cache_get(key)
    if cached:
        return cached
    try:
        async with httpx.AsyncClient(timeout=5, headers=_UA) as client:
            resp = await client.get(
                NOMINATIM_REVERSE,
                params={
                    "lat": lat,
                    "lon": lon,
                    "format": "jsonv2",
                    "zoom": 14,
                    "addressdetails": 1,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            addr = data.get("address", {}) or {}
            out = {
                "display_name": data.get("display_name"),
                "village": addr.get("village") or addr.get("hamlet") or addr.get("suburb"),
                "district": addr.get("district") or addr.get("county") or addr.get("state_district"),
                "state": addr.get("state"),
                "country": addr.get("country"),
            }
            cache_set(key, out, ttl_seconds=86400)
            return out
    except Exception as e:
        logger.warning("Reverse geocode failed for %s,%s: %s", lat, lon, e)
        return None
