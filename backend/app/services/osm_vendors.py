"""Live vendor discovery from OpenStreetMap via the Overpass API.

Two evidence tiers, both always evaluated:
  Tier 1 — TAG-verified: strictly agri-tagged shops (shop=agriculture/seeds/
           fertilizer, agricultural machinery, agri vending), plus
           amenity=marketplace markets and agrarian stores. The tag itself
           is the proof of agri relevance — the name never matters.
  Tier 2 — NAME-verified: hardware/trade/DIY/garden shops. Most Indian
           agri-input shops are tagged `shop=hardware`; agri relevance comes
           from the NAME keywords (kisan, agro, seed, fertilizer, tractor,
           pump, ...). Generic shops without an agri keyword keep their OSM
           identity as `hardware` (rural hardware stores sell pumps, pipes
           and sprayer spares) and rank LAST; shop=wholesale classifies as
           produce_buyer (wholesale trade buys produce — vendor-range §3.5).

A third name-regex query runs only when tiers 1+2 found <10 places, catching
oddly-tagged agri shops by name (kisan|krishi|...).

Tiers 1+2 share ONE Overpass round trip (index-backed selectors only — the
name regex is what times out free mirrors, so it stays in the separate
tier-3 request). Cached 24h per (area, ring); fail-soft: on Overpass failure
we return [] and the curated directory still answers the request.
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

# Tier 1: unambiguous agri shop tags. Tuple feeds both the Overpass regex
# and the evidence ranking, so the two can never drift apart.
_AGRI_SHOPS = (
    "agriculture",
    "agrarian",
    "seeds",
    "farm",
    "agricultural_machinery",
    "fertilizer",
)
_AGRI_SHOP_RE = "^(" + "|".join(_AGRI_SHOPS) + ")$"

# Every category the Nearby Agri Services map understands. Order matters only
# for documentation; `_categorize` applies specific rules before generic ones.
CATEGORIES = [
    "seeds",
    "pesticide",
    "fertilizer",
    "agri_store",
    "hardware",
    "equipment",
    "market",
    "feed",
    "fpo",
    "services",
    "produce_buyer",
]

# Tier 2: generic shop types. Indian agri-input shops are usually `shop=hardware`.
_TIER2_SHOP_RE = "^(hardware|trade|doityourself|garden_centre|wholesale)$"

# Generic supply shops carried as `hardware` when the name says nothing agri.
# (shop=wholesale is deliberately NOT here: wholesale trade = a produce buyer.)
_GENERIC_SHOPS = frozenset({"hardware", "trade", "doityourself", "garden_centre"})

# Strong agri keywords for name matching (tier 2 local filter + tier 3 regex).
_STRONG_AGRI_RE = re.compile(
    r"agri|agro|kisan|krishi|seed|beej|fertiliz|fertili|khaad|khad|"
    r"pesticide|dawa|insecticide|tractor|harvester|pump|sprayer|tiller|"
    r"farm|organic manure|bio "
)
# Weak signals that alone don't prove agri relevance but help tier 3.
_WEAK_AGRI_RE = re.compile(
    r"mandi|market|mills|oil|crushing|ginning|export|wholesale|buyer|procurement|collection|aggregator|trader"
)

# Overpass name regex for tier 3 (strong keywords only, escaped for QGIS regex).
_TIER3_NAME_RE = (
    "kisan|krishi|beej|agri|agro|fertilizer|fertiliser|seeds|pesticide|"
    "tractor|harvester|pump|sprayer|khaad|khad"
)


def _shops_query(lat: float, lon: float, radius_m: int) -> str:
    """Tiers 1+2 in ONE Overpass round trip (two out statements, one request).

    Index-backed tag selectors only — no name regex here (that is what makes
    free mirrors scan and time out; name matching lives in `_tier3_query`).
    Per-tier output budgets mirror the old three-query caps (120 tag-verified
    + 120 hardware), so a dense hardware ring can never crowd markets and
    strictly-tagged shops out of the response. agrarian stores are matched
    once — they used to be fetched by BOTH the strict and the market query.
    """
    return f"""
[out:json][timeout:20];
(
  node["shop"~"{_AGRI_SHOP_RE}"](around:{radius_m},{lat},{lon});
  way["shop"~"{_AGRI_SHOP_RE}"](around:{radius_m},{lat},{lon});
  node["craft"="agricultural_engines"](around:{radius_m},{lat},{lon});
  way["craft"="agricultural_engines"](around:{radius_m},{lat},{lon});
  node["vending"~"^(fertilizer|seeds)$"](around:{radius_m},{lat},{lon});
  node["amenity"="marketplace"](around:{radius_m},{lat},{lon});
  way["amenity"="marketplace"](around:{radius_m},{lat},{lon});
);
out center tags 120;
(
  node["shop"~"{_TIER2_SHOP_RE}"](around:{radius_m},{lat},{lon});
  way["shop"~"{_TIER2_SHOP_RE}"](around:{radius_m},{lat},{lon});
);
out center tags 120;
"""


def _tier3_query(lat: float, lon: float, radius_m: int) -> str:
    """Name regex on nodes/ways WITHOUT a shop tag filter — catches shops that
    are tagged oddly but named clearly. Regex on name is heavier; keeping the
    element count low via `out center tags 60` and the 20s server timeout.
    """
    return f"""
[out:json][timeout:20];
(
  node["name"~"{_TIER3_NAME_RE}", i](around:{radius_m},{lat},{lon});
  way["name"~"{_TIER3_NAME_RE}", i](around:{radius_m},{lat},{lon});
);
out center tags 60;
"""


def _evidence_rank(tags: dict[str, Any], name_lower: str = "") -> int:
    """0 = the OSM tag proves agri relevance, 1 = name evidence, 2 = generic.

    Used to order results so the caller's `limit` truncates generic hardware
    before proven agri businesses (the documented "lower priority" rule).
    """
    shop = (tags.get("shop") or "").lower()
    amenity = (tags.get("amenity") or "").lower()
    craft = (tags.get("craft") or "").lower()
    vending = (tags.get("vending") or "").lower()
    if (
        shop in _AGRI_SHOPS
        or amenity == "marketplace"
        or craft == "agricultural_engines"
        or vending in ("fertilizer", "seeds")
    ):
        return 0
    if shop in _GENERIC_SHOPS and not _STRONG_AGRI_RE.search(name_lower):
        return 2
    return 1


def _categorize(tags: dict[str, Any], name_lower: str = "") -> str | None:
    """OSM tags -> our agri-service category. None = not agri-relevant.

    Most specific signals first so, e.g., a seed shop is not downgraded to a
    generic "agri store". Tag evidence beats name evidence beats guessing.
    """
    shop = (tags.get("shop") or "").lower()
    amenity = (tags.get("amenity") or "").lower()
    office = (tags.get("office") or "").lower()
    craft = (tags.get("craft") or "").lower()
    vending = (tags.get("vending") or "").lower()

    # --- Farmer organisations / FPOs -------------------------------------
    if amenity == "marketplace" and ("producer" in name_lower or "fpo" in name_lower):
        return "fpo"
    if any(
        k in name_lower
        for k in (
            "fpo",
            "farmer producer",
            "farmers producer",
            "producer company",
            "farmers association",
            "farmers' association",
            "krishak samaj",
            "farmer cooperative",
            "farmers cooperative",
        )
    ):
        return "fpo"
    if office in ("association", "cooperative") and _STRONG_AGRI_RE.search(name_lower):
        return "fpo"

    # --- Markets ---------------------------------------------------------
    if amenity == "marketplace" or shop == "greengrocer":
        return "market"
    if any(
        k in name_lower
        for k in (
            "mandi",
            "apmc",
            "market yard",
            "wholesale market",
            "vegetable market",
            "sabzi mandi",
            "veg market",
            "krishi upaj mandi",
        )
    ):
        return "market"

    # --- Animal / cattle feed -------------------------------------------
    if any(
        k in name_lower
        for k in (
            "cattle feed",
            "animal feed",
            "poultry feed",
            "fish feed",
            "feed mill",
            "pashu aahar",
            "pashuahar",
            "pashu ahar",
        )
    ):
        return "feed"
    if shop == "pet_food":
        return "feed"

    # --- Seeds -----------------------------------------------------------
    if shop == "seeds" or vending == "seeds":
        return "seeds"
    if any(k in name_lower for k in ("seed", "beej", "nursery")):
        return "seeds"

    # --- Fertilizer ------------------------------------------------------
    if shop == "fertilizer" or vending == "fertilizer":
        return "fertilizer"
    if any(k in name_lower for k in ("fertiliz", "fertili", "khaad", "khad", "manure")):
        return "fertilizer"

    # --- Equipment / machinery ------------------------------------------
    if shop == "agricultural_machinery" or craft == "agricultural_engines":
        return "equipment"
    if any(k in name_lower for k in ("tractor", "harvester", "pump", "sprayer", "machin", "rotavator", "implement")):
        return "equipment"

    # --- Crop protection --------------------------------------------------
    if any(k in name_lower for k in ("pesticide", "insecticide", "herbicide", "fungicide", "dawa")):
        return "pesticide"

    # --- Services (transport, soil testing, custom hiring, agri centres) ---
    if any(
        k in name_lower
        for k in (
            "transport",
            "soil test",
            "soil testing",
            "custom hiring",
            "agri service",
            "agri centre",
            "agri center",
            "krishi sewa",
            "krishi seva",
            "labour",
            "tractor service",
        )
    ):
        return "services"

    # --- General agri-input store ----------------------------------------
    if shop in ("agriculture", "agrarian", "farm"):
        return "agri_store"
    if _STRONG_AGRI_RE.search(name_lower):
        return "agri_store"  # general agri-input shop (kisan/agro/krishi/...)

    # --- Generic supply shops (hardware/trade/DIY/garden) ------------------
    # The tag alone proves nothing, and a weak trading word ("... Traders",
    # "... Mills") in a hardware shop's name does not make it a crop buyer —
    # so this branch runs BEFORE the weak-name rule. Checked before it used
    # to fall through to `pesticide`, which was simply wrong: a farmer
    # filtering crop-protection products must never see a hardware store.
    if shop in _GENERIC_SHOPS:
        return "hardware"

    # --- Wholesale trade buys produce (vendor-range spec §3.5) -------------
    if shop == "wholesale":
        return "produce_buyer"

    # --- Weak trading keywords: only for otherwise-untagged places ---------
    if _WEAK_AGRI_RE.search(name_lower):
        return "produce_buyer"

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
    raise RuntimeError(f"Overpass failed on all mirrors: {last_err!r}")


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
        name_lower = name.lower()
        category = _categorize(tags, name_lower) or default_category
        if not category:
            continue

        phone = tags.get("phone") or tags.get("contact:phone") or tags.get("contact:mobile")
        website = tags.get("website") or tags.get("contact:website")
        osm_kind = el.get("type", "node")
        osm_id = el.get("id")
        item: dict[str, Any] = {
            "id": f"osm-{osm_kind}-{osm_id}",
            "name": name,
            "category": category,
            "subcategory": tags.get("shop") or tags.get("amenity") or tags.get("craft"),
            "description": tags.get("description")
            or tags.get("operator")
            or tags.get("brand")
            or "Agri service on OpenStreetMap",
            "phone": phone,
            "website": website,
            "opening_hours": tags.get("opening_hours"),
            "address": tags.get("addr:street") or tags.get("addr:place"),
            "city": tags.get("addr:city") or tags.get("addr:town") or tags.get("addr:village"),
            "district": tags.get("addr:district"),
            "state": tags.get("addr:state"),
            "pincode": tags.get("addr:postcode"),
            "latitude": lat_c,
            "longitude": lon_c,
            "crops": [],
            # OSM carries no ratings/reviews — always present as None so the
            # UI omits them instead of showing invented numbers.
            "rating": None,
            "review_count": None,
            "source": "osm",
            "source_kind": "osm",
            "source_id": f"{osm_kind}/{osm_id}",
            "last_updated": None,
        }
        # Evidence tier for prioritisation; popped by discover_vendors_osm
        # before anything is cached or returned.
        item["_rank"] = _evidence_rank(tags, name_lower)
        out.append(item)

    seen: set[tuple] = set()
    unique: list[dict[str, Any]] = []
    for v in out:
        key = (v["name"].lower(), round(v["latitude"], 4), round(v["longitude"], 4))
        if key not in seen:
            seen.add(key)
            unique.append(v)
    return unique


def osm_cache_key(lat: float, lon: float, radius_m: int) -> str:
    """Shared cache key for a discovery ring.

    Both `discover_vendors_osm` and `agri_services.nearby_agri_services`
    (which peeks the cache before deciding to call us) must build the key the
    same way — a drift here means a guaranteed cache miss on every request.
    """
    return f"osm:v5:{round(lat, 2)}:{round(lon, 2)}:{radius_m}"


async def discover_vendors_osm(
    lat: float,
    lon: float,
    radius_m: int = 25000,
    limit: int = 40,
) -> list[dict[str, Any]]:
    """Agri shops near the pin. Tag tiers share one request; radius escalation; cached 24h."""
    cache_key = osm_cache_key(lat, lon, radius_m)
    cached = cache_get(cache_key)
    if cached is not None:
        return cached

    results: list[dict[str, Any]] = []
    started = time.monotonic()
    try:
        # Per-request timeout: a hung Overpass server must never hold a farmer
        # request. Overpass latency is highly variable (observed 1s healthy,
        # 7s+ degraded) — 6s caused frequent false failures, so allow 10s per
        # mirror attempt (the caller's asyncio.wait_for still bounds the total).
        async with httpx.AsyncClient(timeout=10) as client:
            # Tiers 1+2 in ONE round trip: the same index-backed selectors as
            # the old three parallel requests, but one request means one
            # failover chain and one rate-limit token instead of three.
            try:
                results = _parse(await _run_query(client, _shops_query(lat, lon, radius_m)))
            except RuntimeError as e:
                logger.warning("Overpass tag-tier discovery failed: %r", e)
                results = []

            # Tier 3: name-regex hunt for unusually-tagged agri shops. The
            # regex scan is the expensive part, so it only runs when the tag
            # tiers came back thin (<10 results).
            if len(results) < 10:
                try:
                    elements = await _run_query(client, _tier3_query(lat, lon, radius_m))
                    extra = _parse(elements)
                    seen_names = {(v["name"].lower(), round(v["latitude"], 4)) for v in results}
                    results += [
                        v
                        for v in extra
                        if (v["name"].lower(), round(v["latitude"], 4)) not in seen_names
                    ]
                except RuntimeError as e:
                    logger.warning("Overpass tier-3 discovery failed: %r", e)

            # Radius escalation: nothing found nearby -> try one wider ring.
            # Capped at 45km (larger rings time out on free Overpass servers)
            # and skipped when the time budget is already spent.
            if not results and radius_m < 45000 and (time.monotonic() - started) < 6:
                wider = await discover_vendors_osm(lat, lon, radius_m=45000, limit=limit)
                if wider:
                    cache_set(cache_key, wider, ttl_seconds=86400)
                    return wider
    except Exception as e:  # noqa: BLE001 — fail-soft by design
        logger.warning("Vendor discovery error: %r", e)
        cache_set(cache_key, [], ttl_seconds=600)
        return []

    # Evidence first: tag-verified (0), name-verified (1), generic hardware
    # (2) last — so the result cap never crowds out proven agri businesses.
    # Popping here keeps `_rank` out of every cached/returned payload.
    results.sort(key=lambda v: v.pop("_rank", 1))
    results = results[:limit]
    # Never cache an empty result for a full day: a transient all-mirrors
    # outage would otherwise blank an area's live results for 24h even after
    # Overpass recovers. Empty areas are re-queried cheaply every 15 min.
    cache_set(cache_key, results, ttl_seconds=86400 if results else 900)
    return results
