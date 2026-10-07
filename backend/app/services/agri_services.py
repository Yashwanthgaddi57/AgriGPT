"""Nearby agricultural services — one query across both data sources.

Sources merged (deduplicated, then sorted by TRUE haversine distance):
  1. The curated `vendors` directory (AgriGPT-maintained businesses).
  2. Live OpenStreetMap discovery via Overpass (`osm_vendors`), cached 24h.

Design rules that matter for honesty:
  * Distances are always real great-circle km — never a relevance score.
  * The radius is strict. If nothing is inside it we return an empty list and
    the UI offers a bigger radius; we never silently widen the search.
  * Missing fields (rating, website, hours, phone) stay null. OSM has no
    ratings, so the UI hides the rating rather than inventing a number.
"""
import asyncio
import logging
import re
import unicodedata
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.core.cache import cache_get, cache_set
from app.models.mandi import Mandi, Vendor
from app.services.geo_service import haversine_km
from app.services.osm_vendors import CATEGORIES as OSM_CATEGORIES
from app.services.osm_vendors import discover_vendors_osm, osm_cache_key

logger = logging.getLogger("app.geo")

# Canonical category keys the API accepts and the UI renders.
AGRI_CATEGORIES: list[str] = list(OSM_CATEGORIES)

# Farmer-friendly labels (used for server-side search + reporting).
CATEGORY_LABELS: dict[str, str] = {
    "seeds": "Seeds",
    "pesticide": "Pesticides",
    "fertilizer": "Fertilizers",
    "agri_store": "Agri Stores",
    "hardware": "Hardware & Supplies",
    "equipment": "Equipment",
    "market": "Markets",
    "feed": "Animal Feed",
    "fpo": "FPOs / Farmer Groups",
    "services": "Agri Services",
    "produce_buyer": "Crop Buyers",
}

# Words a farmer may type that should act as a category filter
# ("pesticide shops near me", "fertilizer shops within 10 km", ...).
_CATEGORY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "seeds": ("seed", "seeds", "beej", "nursery", "sapling", "plantation material"),
    "pesticide": ("pesticide", "pesticides", "insecticide", "herbicide", "fungicide", "dawa", "crop protection"),
    "fertilizer": ("fertilizer", "fertiliser", "khaad", "khad", "manure", "urea", "dap", "nutrient"),
    "agri_store": ("agri store", "agro store", "agri shop", "agri input", "kisan", "agro", "krishi", "farm supply"),
    "hardware": ("hardware", "hardware store", "plumbing", "irrigation pipe", "pipe fitting"),
    "equipment": ("equipment", "tractor", "machinery", "machine", "implement", "pump", "sprayer", "harvester", "rotavator"),
    "market": ("market", "markets", "mandi", "apmc", "vegetable", "sabzi", "wholesale", "market yard"),
    "feed": ("feed", "cattle feed", "animal feed", "poultry", "fish feed", "pashu"),
    "fpo": ("fpo", "producer company", "farmer group", "farmer organisation", "farmer organization", "cooperative", "co-operative"),
    "services": ("service", "services", "transport", "soil test", "soil testing", "custom hiring", "labour", "labor"),
    "produce_buyer": ("buyer", "buyers", "procurement", "trader", "ginning", "mills", "aggregator"),
}

SORTS = ("nearest", "rating", "name")

_OSM_MAX_RING_M = 60_000
_OSM_MIN_RING_M = 8_000
# Overpass latency is highly variable (observed 1s healthy, 7s+ degraded), so
# this must exceed one full per-mirror attempt (see osm_vendors client timeout)
# or the first mirror never gets a fair chance before we give up.
DISCOVERY_TIMEOUT_S = 15.0

# After a failed/timed-out Overpass call, skip live discovery for this long.
# Without it, an unreachable Overpass makes every map load wait for the timeout
# (the curated directory could answer instantly). Kept short so a recovered
# network is picked up quickly.
_OSM_FAILURE_TTL_S = 300

# Words that carry no identity when comparing business names.
_NOISE_RE = re.compile(
    r"\b(pvt|private|ltd|limited|and|co|company|shop|store|stores|centre|center|"
    r"enterprises|agency|agencies|traders|trading|india)\b"
)


def clamp_radius(radius_km: int | float | None) -> int:
    """Radius in km, bounded to the selectable range (5..100)."""
    try:
        value = int(radius_km or 25)
    except (TypeError, ValueError):
        value = 25
    return max(5, min(value, 100))


def normalize_name(name: str) -> str:
    """Comparison key that ignores case, punctuation and business boilerplate."""
    text = unicodedata.normalize("NFKD", name or "").lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    text = _NOISE_RE.sub(" ", text)
    return re.sub(r"\s+", " ", text).strip()


def categories_from_search(search: str | None) -> list[str]:
    """Derive category filters from free text like 'pesticide shops near me'."""
    if not search:
        return []
    text = search.lower()
    found: list[str] = []
    for category, words in _CATEGORY_KEYWORDS.items():
        if any(word in text for word in words):
            found.append(category)
    return found


def _osm_ring_for(radius_km: int) -> int:
    return max(_OSM_MIN_RING_M, min(int(radius_km * 1000), _OSM_MAX_RING_M))


def _source_label(kind: str | None) -> str:
    if kind == "osm":
        return "OpenStreetMap"
    if kind == "directory":
        return "AgriGPT directory"
    return kind or "Unknown"


def _dedupe(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Drop duplicates by source identity, then by normalised name + location.

    The same shop frequently appears in both the curated directory and OSM (and
    OSM itself can hold a node and a way for one place) — one marker only.
    """
    seen_source: set[tuple[str, str]] = set()
    seen_place: set[tuple[str, int, int]] = set()
    out: list[dict[str, Any]] = []
    for item in items:
        src = (item.get("source") or "", item.get("source_id") or "")
        if src[1] and src in seen_source:
            continue
        place = (
            normalize_name(item.get("name") or ""),
            round(float(item.get("latitude") or 0), 3),
            round(float(item.get("longitude") or 0), 3),
        )
        if place[0] and place in seen_place:
            continue
        if src[1]:
            seen_source.add(src)
        seen_place.add(place)
        out.append(item)
    return out


def _matches_search(item: dict[str, Any], needle: str) -> bool:
    haystack = " ".join(
        str(item.get(field) or "")
        for field in ("name", "description", "address", "city", "district", "state", "subcategory")
    ).lower()
    haystack += " " + CATEGORY_LABELS.get(item.get("category") or "", "").lower()
    haystack += " " + (item.get("category") or "").replace("_", " ")
    return needle in haystack


def _sort_key(sort: str):
    if sort == "rating":
        # Rated places first (best first), then nearest.
        return lambda v: (
            0 if v.get("rating") is not None else 1,
            -(v.get("rating") or 0),
            v.get("distance_km") or 0,
        )
    if sort == "name":
        return lambda v: (v.get("name") or "").lower()
    return lambda v: (
        v.get("distance_km") if v.get("distance_km") is not None else float("inf")
    )


def _mandi_items(db: Session, lat: float, lon: float) -> list[dict[str, Any]]:
    """Seeded APMC wholesale markets as `market` category items.

    Real, maintained directory data — this is what guarantees the map shows
    something nearby even when live OSM discovery is unavailable (spec D11:
    wholesale markets come from BOTH the mandi directory and OSM marketplaces).
    """
    items: list[dict[str, Any]] = []
    for m in db.query(Mandi).all():
        try:
            distance = haversine_km(lat, lon, float(m.latitude), float(m.longitude))
        except (TypeError, ValueError):
            continue
        crops = [str(c) for c in (m.major_crops or [])]
        items.append(
            {
                "id": f"mandi-{m.id}",
                "name": m.name,
                "category": "market",
                "subcategory": "apmc",
                "description": (
                    "APMC wholesale market"
                    + (f" — trades {', '.join(crops)}" if crops else "")
                ),
                "phone": None,
                "website": None,
                "opening_hours": None,
                "address": None,
                "city": m.city,
                "district": m.district,
                "state": m.state,
                "pincode": None,
                "latitude": float(m.latitude),
                "longitude": float(m.longitude),
                "rating": None,
                "review_count": None,
                "crops": crops,
                "distance_km": round(distance, 1),
                "matches_crop": False,
                "source": _source_label("directory"),
                "source_kind": "directory",
                "source_id": None,
                "last_updated": m.created_at,
            }
        )
    return items


def _directory_items(db: Session, lat: float, lon: float) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for v in db.query(Vendor).all():
        try:
            distance = haversine_km(lat, lon, float(v.latitude), float(v.longitude))
        except (TypeError, ValueError):
            continue
        items.append(
            {
                "id": str(v.id),
                "name": v.name,
                "category": v.category,
                "subcategory": v.subcategory,
                "description": v.description,
                "phone": v.phone,
                "website": v.website,
                "opening_hours": v.opening_hours,
                "address": v.address,
                "city": v.city,
                "district": v.district,
                "state": v.state,
                "pincode": v.pincode,
                "latitude": float(v.latitude),
                "longitude": float(v.longitude),
                "rating": float(v.rating) if v.rating is not None else None,
                "review_count": v.review_count,
                "crops": v.crops or [],
                "distance_km": round(distance, 1),
                "matches_crop": False,
                # `source` is the human label shown in the UI; `source_kind` is
                # the raw machine value kept for filtering/analytics.
                "source": _source_label("directory"),
                "source_kind": "directory",
                "source_id": v.source_id,
                "last_updated": (v.updated_at or v.created_at),
            }
        )
    items.extend(_mandi_items(db, lat, lon))
    return items


async def nearby_agri_services(
    db: Session,
    lat: float,
    lon: float,
    *,
    radius_km: int | float | None = 25,
    categories: list[str] | None = None,
    search: str | None = None,
    crop: str | None = None,
    sort: str = "nearest",
    limit: int = 60,
) -> list[dict[str, Any]]:
    """Agri services strictly within `radius_km`, sorted (default: nearest)."""
    radius = clamp_radius(radius_km)
    sort = sort if sort in SORTS else "nearest"
    crop_lower = (crop or "").lower().strip()

    wanted = [c for c in (categories or []) if c in AGRI_CATEGORIES]
    # Free-text search may itself imply categories ("pesticide shops near me").
    for implied in categories_from_search(search):
        if implied not in wanted:
            wanted.append(implied)

    items = _directory_items(db, lat, lon)

    # Serve a valid cached discovery result even while a recent attempt for
    # this area failed (the failure marker must not hide good data). Only when
    # nothing is cached do we skip live discovery during the failure window,
    # so a slow/unreachable Overpass never stalls the map on every request.
    fail_key = f"agri:osm-fail:{round(lat, 1)}:{round(lon, 1)}"
    osm: list[dict[str, Any]] = []
    cached_osm = cache_get(osm_cache_key(lat, lon, _osm_ring_for(radius)))
    if cached_osm is not None:
        osm = cached_osm
    elif not cache_get(fail_key):
        try:
            osm = await asyncio.wait_for(
                discover_vendors_osm(lat, lon, radius_m=_osm_ring_for(radius), limit=60),
                timeout=DISCOVERY_TIMEOUT_S,
            )
        except Exception as e:  # fail-soft: the curated directory still answers
            # %r not %s: TimeoutError()'s str() is empty, which produced useless
            # "OSM discovery unavailable: " log lines.
            logger.warning("OSM discovery unavailable: %r", e)
            cache_set(fail_key, True, ttl_seconds=_OSM_FAILURE_TTL_S)
            osm = []

    fetched_at = datetime.now(timezone.utc)
    for shop in osm:
        try:
            distance = haversine_km(lat, lon, float(shop["latitude"]), float(shop["longitude"]))
        except (KeyError, TypeError, ValueError):
            continue
        kind = shop.get("source") or "osm"
        items.append(
            {
                **shop,
                "distance_km": round(distance, 1),
                "matches_crop": False,
                "source": _source_label(kind),
                "source_kind": kind,
                # When we retrieved it — the honest meaning of "last updated" for
                # a live OSM fetch (the element itself carries no timestamp here).
                "last_updated": shop.get("last_updated") or fetched_at,
            }
        )

    merged = _dedupe(items)

    if wanted:
        allowed = set(wanted)
        merged = [v for v in merged if v.get("category") in allowed]

    if crop_lower:
        for v in merged:
            v["matches_crop"] = crop_lower in [str(c).lower() for c in (v.get("crops") or [])]

    needle = (search or "").strip().lower()
    if needle:
        # Words that only describe a category ("pesticide shops near me") must
        # not filter every result out of the text match.
        stripped = needle
        for implied in categories_from_search(search):
            for word in _CATEGORY_KEYWORDS.get(implied, ()):
                stripped = stripped.replace(word, " ")
        stripped = re.sub(r"\b(near|me|nearby|shops?|stores?|find|show|where|can|i|buy|within|km|kms|the|a|in)\b", " ", stripped)
        stripped = re.sub(r"\s+", " ", stripped).strip()
        if stripped:
            merged = [v for v in merged if _matches_search(v, stripped)]

    within = [
        v
        for v in merged
        if v.get("distance_km") is not None and v["distance_km"] <= radius
    ]
    within.sort(key=_sort_key(sort))
    return within[: max(1, min(int(limit or 60), 200))]
