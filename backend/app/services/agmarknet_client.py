"""Agmarknet mandi price client via data.gov.in (real market data).

Fetches variety-wise daily wholesale prices (min/max/modal, INR/quintal)
reported by APMC markets to AGMARKNET, published through data.gov.in.

Contract (verified against the live resource, 2026-09):
  GET https://api.data.gov.in/resource/9ef84268-d588-465a-a308-a864a43d0070
  params: api-key, format=json, offset, limit (<=1000)
  filters: filters[state.keyword]  (state needs the .keyword suffix)
           filters[district], filters[market], filters[commodity]

Record fields: state, district, market, commodity, variety, grade,
arrival_date (dd/mm/yyyy), min_price, max_price, modal_price (strings).

Fail-soft: every failure mode (no key, network, rate limit, bad rows)
returns [] so the synthetic baseline in market_service stays the fallback.
"""
import logging
import time
from datetime import date, datetime, timedelta
from typing import Any

import httpx

from app.core.cache import cache_get, cache_set

logger = logging.getLogger("app.market.agmarknet")

RESOURCE_URL = "https://api.data.gov.in/resource/9ef84268-d588-465a-a308-a864a43d0070"
_UA = {"User-Agent": "AgriGPT/1.0 (support@agrigpt.app)"}

# Circuit breaker: data.gov.in throttles/outages for stretches at a time. After
# repeated failures, stop calling it for a while so interactive endpoints
# (ticker) fail fast to the baseline instead of hanging on timeouts.
_api_dead_until = 0.0
_API_COOLDOWN_S = 900  # 15 min
_FAILURES_TO_OPEN = 2
_failure_streak = 0

# Agmarknet commodity names vary by crop/region (cotton is "Kapas", soybean
# "Soyabean", ...), so each app-level crop maps to an ordered list of candidate
# names tried until one yields rows. Unknown crops just fall back to baseline.
AGMARKNET_COMMODITY: dict[str, list[str]] = {
    "wheat": ["Wheat"],
    "rice": ["Rice"],
    "paddy": ["Paddy(Dhan)(Common)", "Paddy"],
    "cotton": ["Cotton", "Kapas (Kappas)", "Kapas"],
    "sugarcane": ["Sugarcane"],
    "maize": ["Maize", "Bhutta (Corn)"],
    "soybean": ["Soyabean"],
    "onion": ["Onion"],
    "potato": ["Potato", "Potato (Fresh)"],
    "tomato": ["Tomato"],
    "gram": ["Gram"],
    "chickpea": ["Chickpea", "Gram"],
    "mustard": ["Mustard", "Mustard Seed"],
    "groundnut": ["Groundnut"],
    "turmeric": ["Turmeric"],
    "chilli": ["Chilli(Dry)", "Chilli"],
    "cumin": ["Cumin Seed"],
    "banana": ["Banana"],
    "mango": ["Mango"],
    "guava": ["Guava"],
    "barley": ["Barley"],
    "bajra": ["Bajra(Pearl Millet/Cumbu)", "Bajra"],
    "jowar": ["Jowar(Sorghum)", "Jowar"],
}

# How fresh a record must be to count as a live quote (markets report daily
# but the publication pipeline has gaps — a week is the honest ceiling).
FRESHNESS_DAYS = 7


def parse_arrival_date(raw: Any) -> date | None:
    """Agmarknet sends dd/mm/yyyy strings; tolerate a few variants."""
    if not raw:
        return None
    value = str(raw).strip()
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%d/%m/%y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def _to_float(raw: Any) -> float | None:
    try:
        value = float(str(raw).strip().replace(",", ""))
        return value if value > 0 else None
    except (TypeError, ValueError):
        return None


def _parse_rows(records: list[dict]) -> list[dict]:
    """Normalize raw records into price points; quarantine nonsense rows."""
    by_day: dict[str, float] = {}
    for rec in records:
        modal = _to_float(rec.get("modal_price"))
        if modal is None:
            continue
        min_p = _to_float(rec.get("min_price"))
        max_p = _to_float(rec.get("max_price"))
        # Modal should sit inside the reported band; if not, trust modal but
        # flag once — dropping wholesale rows distorts thin markets.
        if min_p is not None and max_p is not None and not (min_p <= modal <= max_p):
            logger.debug("Suspicious price band: %s", rec)
        day = parse_arrival_date(rec.get("arrival_date"))
        if day is None:
            continue
        # Several varieties report per day: average them into one price point.
        by_day.setdefault(day, []).append(modal)
    out = []
    for day, prices in by_day.items():
        out.append({"date": day.isoformat(), "price": round(sum(prices) / len(prices), 2)})
    out.sort(key=lambda p: p["date"])
    return out


def _norm(s: str) -> str:
    """Lowercase alphanumerics only, for fuzzy place-name comparison."""
    import re as _re

    return _re.sub(r"[^a-z0-9]", "", str(s).lower())


def _fuzzy_district_match(row_district: str, wanted: str) -> bool:
    """Tolerate spelling drift (Hanamkonda vs Hanmakonda, Raichur vs Raichuru)."""
    import difflib

    a, b = _norm(row_district), _norm(wanted)
    if not a or not b:
        return False
    if a == b or a in b or b in a:
        return True
    return difflib.SequenceMatcher(None, a, b).ratio() >= 0.8


def _fetch_page(client: httpx.Client, params: dict) -> list[dict]:
    """One API call with a conditional retry — data.gov.in is flaky at times.

    A fast failure (connection reset, 5xx) is worth one retry; a slow timeout
    is not (retrying doubles the wait), so we bail and let the circuit open.
    """
    global _failure_streak, _api_dead_until
    last_exc: Exception | None = None
    start = time.monotonic()
    for attempt in range(2):
        try:
            resp = client.get(RESOURCE_URL, params=params)
            if resp.status_code in (403, 429):
                logger.warning("Agmarknet API rejected key/rate limit (%s)", resp.status_code)
                _failure_streak += 1
                return []
            resp.raise_for_status()
            _failure_streak = 0
            return resp.json().get("records") or []
        except Exception as e:
            last_exc = e
            if time.monotonic() - start > 5 or attempt == 1:
                break  # slow failure: no retry
    if last_exc:
        logger.warning("Agmarknet fetch failed (%s)", last_exc)
    _failure_streak += 1
    if _failure_streak >= _FAILURES_TO_OPEN:
        _api_dead_until = time.monotonic() + _API_COOLDOWN_S
        logger.warning("Agmarknet circuit opened for %ss after repeated failures", _API_COOLDOWN_S)
    return []


def fetch_mandi_prices(
    crop: str,
    state: str | None = None,
    district: str | None = None,
    market: str | None = None,
    days: int = 90,
    api_key: str | None = None,
) -> list[dict]:
    """Real daily modal prices for one crop, newest last.

    Commodity aliases are tried in order (cotton -> Kapas, ...). Location
    filters are best-effort: if the exact district filter yields nothing, rows
    are fetched state-wide and district-matched fuzzily client-side.
    Returns [] on any failure — never raises.
    """
    from app.core.config import settings

    key = api_key or settings.DATA_GOV_API_KEY
    if not key:
        return []

    candidates = AGMARKNET_COMMODITY.get(crop.lower().strip())
    if not candidates:
        return []

    cache_key = f"agmarknet:{crop.lower().strip()}:{(state or '').lower()}:{(district or '').lower()}:{(market or '').lower()}"
    cached = cache_get(cache_key)
    if cached is not None:
        return cached

    global _api_dead_until
    if time.monotonic() < _api_dead_until:
        return []  # circuit open: fail fast to baseline

    records: list[dict] = []
    used_commodity: str | None = None
    try:
        with httpx.Client(timeout=6, headers=_UA) as client:
            for commodity in candidates:
                # Narrowest filter first: market > district > state > national.
                filters: dict[str, str] = {"filters[commodity]": commodity}
                if market:
                    filters["filters[market]"] = market
                elif district:
                    filters["filters[district]"] = district
                elif state:
                    filters["filters[state.keyword]"] = state

                for offset in (0, 1000):  # two pages cover ~2 months of a busy mandi
                    page = _fetch_page(
                        client,
                        {"api-key": key, "format": "json", "offset": offset, "limit": 1000, **filters},
                    )
                    records.extend(page)
                    if len(page) < 1000:
                        break

                # Exact district filter found nothing -> state-wide + fuzzy match.
                if not records and district and not market and state:
                    state_filters = {"filters[commodity]": commodity, "filters[state.keyword]": state}
                    for offset in (0, 1000):
                        page = _fetch_page(
                            client,
                            {"api-key": key, "format": "json", "offset": offset, "limit": 1000, **state_filters},
                        )
                        records.extend(
                            r for r in page if _fuzzy_district_match(r.get("district") or "", district)
                        )
                        if len(page) < 1000:
                            break

                if records:
                    used_commodity = commodity
                    break
    except Exception as e:
        logger.warning("Agmarknet fetch failed (%s); falling back to baseline", e)
        _api_dead_until = time.monotonic() + _API_COOLDOWN_S
        return []

    points = _parse_rows(records)
    cutoff = date.today() - timedelta(days=days)
    points = [p for p in points if datetime.strptime(p["date"], "%Y-%m-%d").date() >= cutoff]

    # Daily gaps (holidays, missed reporting): forward-fill for a continuous
    # series so trend math and the chart stay honest about coverage.
    filled: list[dict] = []
    for point in points:
        if filled:
            prev = datetime.strptime(filled[-1]["date"], "%Y-%m-%d").date()
            day = datetime.strptime(point["date"], "%Y-%m-%d").date()
            gap = (day - prev).days
            if 1 < gap <= 7:
                for missing in range(1, gap):
                    mid_date = prev + timedelta(days=missing)
                    filled.append({"date": mid_date.isoformat(), "price": filled[-1]["price"]})
            elif gap > 7:
                filled = []  # too sparse to bridge; start over at this point
        filled.append(point)

    if filled:
        cache_set(cache_key, filled, ttl_seconds=6 * 3600)  # daily data, 6h cache
    return filled


def latest_fresh_price(points: list[dict]) -> float | None:
    """Most recent price only if it is within FRESHNESS_DAYS of today."""
    if not points:
        return None
    last = datetime.strptime(points[-1]["date"], "%Y-%m-%d").date()
    if (date.today() - last).days > FRESHNESS_DAYS:
        return None
    return points[-1]["price"]


def market_data_points(records: list[dict]) -> dict:
    """Top mandis (by most recent record) for the UI's market source panel."""
    mandis: dict[str, dict] = {}
    for rec in records:
        name = str(rec.get("market") or "").strip()
        if not name:
            continue
        modal = _to_float(rec.get("modal_price"))
        day = parse_arrival_date(rec.get("arrival_date"))
        if modal is None or day is None:
            continue
        entry = mandis.setdefault(
            name,
            {
                "market": name,
                "district": str(rec.get("district") or "").strip() or None,
                "state": str(rec.get("state") or "").strip() or None,
                "modal_price": modal,
                "arrival_date": day.isoformat(),
            },
        )
        if day.isoformat() >= entry["arrival_date"]:
            entry.update({"modal_price": modal, "arrival_date": day.isoformat()})
    return mandis
