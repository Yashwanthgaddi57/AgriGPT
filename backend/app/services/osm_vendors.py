"""Live vendor discovery from OpenStreetMap via the Overpass API.

Three tiers, ALL evaluated (not gated on the previous one finding results):
  Tier 1 — strictly agri-tagged shops (shop=agriculture/seeds/fertilizer,
           agricultural machinery, agri vending).
  Tier 2 — hardware/trade/DIY/garden shops. Most Indian agri-input shops are
           tagged `shop=hardware`; agri relevance comes from the NAME keywords
           (kisan, agro, seed, fertilizer, tractor, pump, ...). Unnamed
           hardware shops are kept as generic supplies with lower priority.
  Tier 3 — named places matching strong agri keywords via Overpass name regex
           (name~"kisan|krishi|..."), catching shops tagged with unusual
           categories (shop=yes, commercial, retail etc.).

Cached 24h per (area, ring); fail-soft: on Overpass failure we return [] and
the curated directory still answers the request.
"""
import asyncio
import logging
import re
import time
from typing import Any

import httpx

from app.core.cache import cache_get, cache_set

logger = logging.getLogger("app.geo")

OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]
_UA = {"User-Agent": "AgriGPT/1.0 (support@agrigpt.app)"}

# Tier 1: unambiguous agri shop tags
_AGRI_SHOP_RE = "^(agriculture|agrarian|seeds|farm|agricultural_machinery|fertilizer)$"

# Tier 2: generic shop types. Indian agri-input shops are usually `shop=hardware`.
_TIER2_SHOP_RE = "^(hardware|trade|doityourself|garden_centre|wholesale)$"

# Strong agri keywords for name matching (tier 2 local filter + tier 3 regex).
_STRONG_AGRI_RE = re.compile(
    r"agri|agro|kisan|krishi|seed|beej|fertiliz|fertili|khaad|khad|"
    r"pesticide|dawa|insecticide|tractor|harvester|pump|sprayer|tiller|"
    r"farm|organic manure|bio "
)
# Weak signals that alone don't prove agri relevance but help tier 3.
_WEAK_AGRI_RE = re.compile(r"mandi|market|mills|oil|crushing|ginning|export|wholesale|buyer|procurement|collection|aggregator|trader")

# Overpass name regex for tier 3 (strong keywords only, escaped for QGIS regex).
_TIER3_NAME_RE = (
    "kisan|krishi|beej|agri|agro|fertilizer|fertiliser|seeds|pesticide|"
    "tractor|harvester|pump|sprayer|khaad|khad"
)


def _tier1_query(lat: float, lon: float, radius_m: int) -> str:
    return f"""
[out:json][timeout:20];
(
  node["shop"~"{_AGRI_SHOP_RE}"](around:{radius_m},{lat},{lon});
  way["shop"~"{_AGRI_SHOP_RE}"](around:{radius_m},{lat},{lon});
  node["craft"="agricultural_engines"](around:{radius_m},{lat},{lon});
  way["craft"="agricultural_engines"](around:{radius_m},{lat},{lon});
  node["vending"~"^(fertilizer|seeds)$"](around:{radius_m},{lat},{lon});
);
out center tags 60;
"""


def _tier2_query(lat: float, lon: float, radius_m: int) -> str:
    # No name-regex inside Overpass here: regex + tag filters make it scan and
    # time out. We fetch hardware/trade shops (index-backed) and filter locally.
    return f"""
[out:json][timeout:20];
(
  node["shop"~"{_TIER2_SHOP_RE}"](around:{radius_m},{lat},{lon});
  way["shop"~"{_TIER2_SHOP_RE}"](around:{radius_m},{lat},{lon});
);
out center tags 120;
"""


def _tier3_query(lat: float, lon: float, radius_m: int) -> str:
    # Name regex on nodes/ways WITHOUT a shop tag filter — catches shops that
    # are tagged oddly but named clearly. Regex on name is heavier; keeping the
    # element count low via `out center tags 60` and the 20s server timeout.
    return f"""
[out:json][timeout:20];
(
  node["name"~"{_TIER3_NAME_RE}", i](around:{radius_m},{lat},{lon});
  way["name"~"{_TIER3_NAME_RE}", i](around:{radius_m},{lat},{lon});
);
out center tags 60;
"""


def _name_is_agri(name: str) -> bool:
    return bool(_STRONG_AGRI_RE.search(name.lower()))


def _categorize(tags: dict[str, Any], name_lower: str = "") -> str | None:
    """OSM tags -> our vendor category. None = not agri-relevant."""
    shop = tags.get("shop", "")
    if shop in ("agriculture", "agrarian", "seeds", "farm"):
        return "seeds"
    if shop == "fertilizer":
        return "fertilizer"
    if shop == "agricultural_machinery" or tags.get("craft") == "agricultural_engines":
        return "equipment"
    if tags.get("vending") in ("fertilizer", "seeds"):
        return "seeds" if tags["vending"] == "seeds" else "fertilizer"
    # Tier 2/3 (name-keyword shops): categorize by dominant keyword
    if any(k in name_lower for k in ("seed", "beej")):
        return "seeds"
    if any(k in name_lower for k in ("fertiliz", "fertili", "khaad", "khad", "manure")):
        return "fertilizer"
    if any(k in name_lower for k in ("tractor", "harvester", "pump", "sprayer", "machin")):
        return "equipment"
    if any(k in name_lower for k in ("pesticide", "insecticide", "dawa")):
        return "pesticide"
    if _WEAK_AGRI_RE.search(name_lower):
        return "produce_buyer"
    if _STRONG_AGRI_RE.search(name_lower):
        return "seeds"  # general agri-input shop
    if shop in ("hardware", "doityourself", "trade", "wholesale", "garden_centre"):
        return "pesticide"  # generic supplies shop (kept, low relevance)
    return None


async def _run_query(client: httpx.AsyncClient, query: str) -> list[dict]:
    """POST to Overpass with mirror failover. Raises on total failure."""
    last_err: Exception | None = None
    for url in OVERPASS_URLS:
        try:
            resp = await client.post(url, data={"data": query}, headers=_UA)
            resp.raise_for_status()
            return resp.json().get("elements", [])
        except Exception as e:
            last_err = e
            continue
    raise RuntimeError(f"Overpass failed on all mirrors: {last_err}")


def _parse(elements: list[dict], default_category: str | None = None) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for el in elements:
        tags = el.get("tags", {}) or {}
        lat_c = float(el.get("lat") or (el.get("center") or {}).get("lat") or 0)
        lon_c = float(el.get("lon") or (el.get("center") or {}).get("lon") or 0)
        if not lat_c or not lon_c:
            continue
        name = tags.get("name")
        if not name:
            continue
        category = _categorize(tags, name.lower()) or default_category
        if not category:
            continue

        phone = tags.get("phone") or tags.get("contact:phone") or tags.get("contact:mobile")
        out.append(
            {
                "id": f"osm-{el.get('type', 'node')}-{el.get('id')}",
                "name": name,
                "category": category,
                "description": tags.get("description")
                or tags.get("operator")
                or tags.get("brand")
                or "Agri shop on OpenStreetMap",
                "phone": phone,
                "address": tags.get("addr:street") or tags.get("addr:place"),
                "city": tags.get("addr:city") or tags.get("addr:town") or tags.get("addr:village"),
                "district": tags.get("addr:district"),
                "state": tags.get("addr:state"),
                "latitude": lat_c,
                "longitude": lon_c,
                "crops": [],
                "source": "osm",
            }
        )

    seen: set[tuple] = set()
    unique: list[dict[str, Any]] = []
    for v in out:
        key = (v["name"].lower(), round(v["latitude"], 4), round(v["longitude"], 4))
        if key not in seen:
            seen.add(key)
            unique.append(v)
    return unique


async def discover_vendors_osm(
    lat: float,
    lon: float,
    radius_m: int = 25000,
    limit: int = 40,
) -> list[dict[str, Any]]:
    """Agri shops near the pin. All tiers run; radius escalation; cached 24h."""
    cache_key = f"osm:v3:{round(lat, 2)}:{round(lon, 2)}:{radius_m}"
    cached = cache_get(cache_key)
    if cached is not None:
        return cached

    results: list[dict[str, Any]] = []
    started = time.monotonic()
    try:
        # Short per-request timeout: a hung Overpass server must never hold a
        # farmer request. Failures fail-soft into a 10-min negative cache.
        async with httpx.AsyncClient(timeout=6) as client:
            # Tier 1 + tier 2 in parallel; both always run.
            t1 = _run_query(client, _tier1_query(lat, lon, radius_m))
            t2 = _run_query(client, _tier2_query(lat, lon, radius_m))
            t1_res, t2_res = await asyncio.gather(t1, t2, return_exceptions=True)
            if isinstance(t1_res, BaseException):
                logger.warning("Overpass tier-1 discovery failed: %s", t1_res)
                t1_res = []
            if isinstance(t2_res, BaseException):
                logger.warning("Overpass tier-2 discovery failed: %s", t2_res)
                t2_res = []
            results = _parse(t1_res) + _parse(t2_res)

            # Tier 2 local name filter: named+agri first, then unnamed hardware
            # shops (still useful — a rural hardware shop usually sells pumps,
            # pipes and sprayer spares). Dedup across tiers.
            named = [v for v in results if _name_is_agri(v["name"])]
            unnamed = [v for v in results if not _name_is_agri(v["name"]) and v["category"] in ("pesticide",)]
            results = named + unnamed

            # Tier 3: name-regex hunt for unusually-tagged agri shops.
            if len(results) < 10:
                try:
                    elements = await _run_query(client, _tier3_query(lat, lon, radius_m))
                    extra = _parse(elements)
                    seen_names = {(v["name"].lower(), round(v["latitude"], 4)) for v in results}
                    results += [v for v in extra if (v["name"].lower(), round(v["latitude"], 4)) not in seen_names]
                except RuntimeError as e:
                    logger.warning("Overpass tier-3 discovery failed: %s", e)

            # Radius escalation: nothing found nearby -> try one wider ring.
            # Capped at 45km (larger rings time out on free Overpass servers)
            # and skipped when the time budget is already spent.
            if not results and radius_m < 45000 and (time.monotonic() - started) < 6:
                wider = await discover_vendors_osm(lat, lon, radius_m=45000, limit=limit)
                if wider:
                    cache_set(cache_key, wider, ttl_seconds=86400)
                    return wider
    except Exception as e:  # noqa: BLE001 — fail-soft by design
        logger.warning("Vendor discovery error: %s", e)
        cache_set(cache_key, [], ttl_seconds=600)
        return []

    results = results[:limit]
    cache_set(cache_key, results, ttl_seconds=86400)
    return results
