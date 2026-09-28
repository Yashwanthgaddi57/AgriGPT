"""Keyless Agmarknet scrape fallback — no DATA_GOV_API_KEY required.

Fetches the public price grid at agmarknet.gov.in/SearchCmmMkt.aspx and
parses `cphBody_GridPriceData` rows (S.No, District/Market, Commodity,
Variety, Grade, Min, Max, Modal, Date). Codes for commodity/state are
resolved from the page's own dropdowns, cached 7 days (they are stable).
Results are filtered to the farmer's district/market when provided, and
subjected to the same freshness gate as the keyed feed.

Position in the price chain: keyed data.gov.in feed first (richest filters,
clean JSON); this scrape tier second; synthetic baseline last.

Parsing uses Scrapling's lxml-backed Selector (fast, CSS/XPath) with a
drift guard: the known table ID first, then a header-signature fallback so
markup tweaks degrade loudly instead of silently yielding no prices.

Fail-soft: every failure mode (network, HTML drift, parse errors) returns []
— the chain degrades instead of erroring.
"""
import logging
import re
from datetime import date, datetime, timedelta
from typing import Any

import httpx
from scrapling.parser import Selector

from app.core.cache import cache_get, cache_set

logger = logging.getLogger("app.market.scraper")

SEARCH_URL = "https://agmarknet.gov.in/SearchCmmMkt.aspx"
_UA = {"User-Agent": "AgriGPT/1.0 (support@agrigpt.app)"}
_TABLE_ID = "cphBody_GridPriceData"

# Commodity names as Agmarknet spells them (dropdown values).
AGMARKNET_COMMODITY = {
    "wheat": "Wheat", "rice": "Rice", "paddy": "Paddy(Dhan)(Common)",
    "cotton": "Cotton", "sugarcane": "Sugarcane", "maize": "Maize",
    "soybean": "Soyabean", "onion": "Onion", "potato": "Potato",
    "tomato": "Tomato", "gram": "Gram", "chickpea": "Chickpea",
    "mustard": "Mustard", "groundnut": "Groundnut", "turmeric": "Turmeric",
    "chilli": "Chilli(Dry)", "cumin": "Cumin Seed", "banana": "Banana",
    "mango": "Mango", "guava": "Guava", "barley": "Barley", "bajra": "Bajra(Pearl Millet/Cumbu)",
    "jowar": "Jowar(Sorghum)",
}


def _normalize(s: str) -> str:
    """Lowercase alnum comparison key: 'Rangareddy' == 'Ranga Reddy'-ish."""
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def _to_float(raw: Any) -> float | None:
    try:
        v = float(str(raw).strip().replace(",", ""))
        return v if v > 0 else None
    except (TypeError, ValueError):
        return None


def _parse_date(raw: str) -> date | None:
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%d %b %Y", "%d/%m/%y", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw.strip(), fmt).date()
        except ValueError:
            continue
    return None


async def resolve_codes(commodity: str, state: str) -> tuple[str | None, str | None]:
    """Pull Tx_Commodity / Tx_State codes from the page's dropdown options."""
    cache_key = f"agmarknet-codes:{_normalize(commodity)}:{_normalize(state)}"
    cached = cache_get(cache_key)
    if cached:
        return cached

    html = None
    try:
        async with httpx.AsyncClient(timeout=15, headers=_UA, follow_redirects=True) as client:
            resp = await client.get(SEARCH_URL)
            if resp.status_code < 400:
                html = resp.text
    except Exception as e:
        logger.warning("Agmarknet scrape: code page fetch failed: %s", e)
        return None, None
    if not html:
        return None, None

    def _extract(select_id: str, label: str) -> str | None:
        m = re.search(
            rf'<select[^>]*id="{select_id}"[^>]*>(.*?)</select>', html, re.S | re.I
        )
        if not m:
            return None
        options = re.findall(
            r'<option[^>]*value="([^"]*)"[^>]*>([^<]*)</option>', m.group(1), re.I
        )
        for value, text in options:
            if _normalize(text) == _normalize(label):
                return value
        # Fuzzy: 'paddy dhan common' contains 'paddy'
        for value, text in options:
            if _normalize(label) and _normalize(label) in _normalize(text):
                return value
        return None

    commodity_code = _extract("ddlCommodity", commodity)
    state_code = _extract("ddlState", state)
    result = (commodity_code, state_code)
    if commodity_code or state_code:
        cache_set(cache_key, result, ttl_seconds=7 * 86400)
    return result


def _cells(row: Any) -> list[str]:
    """Text of every th/td cell in a row, entities decoded, whitespace trimmed."""
    return [(c.text or "").replace("\xa0", " ").strip() for c in row.css("th,td")]


def _find_grid(root: Selector) -> Selector | None:
    """Locate the price grid. Known ID first, header-signature fallback second
    — so an Agmarknet markup tweak degrades loudly instead of silently
    returning no prices (drift becomes observable in the logs)."""
    by_id = root.css(f"table#{_TABLE_ID}")
    if by_id:
        return by_id[0]
    logger.warning(
        "Agmarknet scrape: table id %s missing — trying header-signature match "
        "(markup may have drifted)",
        _TABLE_ID,
    )
    for table in root.css("table"):
        header_cells = _cells(table.css("tr")[0]) if table.css("tr") else []
        header_text = " ".join(header_cells).lower()
        if all(hint in header_text for hint in ("market", "commodity", "modal")):
            logger.warning("Agmarknet scrape: recovered grid via header signature")
            return table
    logger.warning("Agmarknet scrape: no price grid found on page")
    return None


def _option_values(html: str, select_id: str) -> list[tuple[str, str]]:
    """(value, label) pairs of a <select> via Scrapling (entity-safe)."""
    root = Selector(html)
    select = root.css(f"select#{select_id}")
    if not select:
        return []
    return [
        (opt.attrib.get("value", ""), (opt.text or "").strip())
        for opt in select[0].css("option")
    ]


async def resolve_codes(commodity: str, state: str) -> tuple[str | None, str | None]:
    """Pull Tx_Commodity / Tx_State codes from the page's dropdown options."""
    cache_key = f"agmarknet-codes:{_normalize(commodity)}:{_normalize(state)}"
    cached = cache_get(cache_key)
    if cached:
        return cached

    html = None
    try:
        async with httpx.AsyncClient(timeout=15, headers=_UA, follow_redirects=True) as client:
            resp = await client.get(SEARCH_URL)
            if resp.status_code < 400:
                html = resp.text
    except Exception as e:
        logger.warning("Agmarknet scrape: code page fetch failed: %s", e)
        return None, None
    if not html:
        return None, None

    commodity_code = state_code = None
    try:
        commodity_options = _option_values(html, "ddlCommodity")
        state_options = _option_values(html, "ddlState")
    except Exception as e:  # malformed HTML — fail soft
        logger.warning("Agmarknet scrape: dropdown parse failed: %s", e)
        return None, None

    for options, label, setter in (
        (commodity_options, commodity, "c"),
        (state_options, state, "s"),
    ):
        want = _normalize(label)
        hit = next((v for v, t in options if _normalize(t) == want), None)
        if hit is None:  # fuzzy: 'paddy dhan common' contains 'paddy'
            hit = next((v for v, t in options if want and want in _normalize(t)), None)
        if setter == "c":
            commodity_code = hit
        else:
            state_code = hit

    result = (commodity_code, state_code)
    if commodity_code or state_code:
        cache_set(cache_key, result, ttl_seconds=7 * 86400)
    return result


def parse_grid(html: str) -> list[dict]:
    """Extract rows from the cphBody_GridPriceData grid (Scrapling-parsed)."""
    try:
        root = Selector(html)
        # Malformed HTML can leave Scrapling's lxml root as None; treat as empty.
        if getattr(root, "_root", None) is None:
            logger.warning("Agmarknet scrape: HTML produced no parse tree")
            return []
    except Exception as e:
        logger.warning("Agmarknet scrape: unparseable HTML: %s", e)
        return []
    grid = _find_grid(root)
    if grid is None:
        return []
    out: list[dict] = []
    for row in grid.css("tr"):
        cells = _cells(row)
        # Expected header: S.No | District | Market | Commodity | Variety
        # | Grade | Min | Max | Modal | Date
        if len(cells) < 10:
            continue
        if cells[0].lower().startswith("s."):
            continue  # header row
        d = _parse_date(cells[9])
        modal = _to_float(cells[8])
        if d is None or modal is None:
            continue
        out.append(
            {
                "state": "",  # not present in this grid; filtered by district/market
                "district": cells[1],
                "market": cells[2],
                "commodity": cells[3],
                "variety": cells[4],
                "grade": cells[5],
                "min_price": _to_float(cells[6]),
                "max_price": _to_float(cells[7]),
                "modal_price": modal,
                "arrival_date": d.isoformat(),
            }
        )
    return out


def filter_by_location(rows: list[dict], district: str | None, market: str | None) -> list[dict]:
    """Prefer rows matching the farmer's district, then market name.

    Falls back to unfiltered rows if the location filter is too strict —
    a farmer in a small district should still see the state's nearest trades.
    """
    if not rows:
        return []
    if market:
        hits = [r for r in rows if _normalize(market) in _normalize(r["market"]) or _normalize(r["market"]) in _normalize(market)]
        if hits:
            return hits
    if district:
        hits = [r for r in rows if _normalize(district) in _normalize(r["district"]) or _normalize(r["district"]) in _normalize(district)]
        if hits:
            return hits
    return rows


def average_by_day(rows: list[dict], days: int = 90) -> list[dict]:
    """Group by arrival_date -> mean modal price, sorted oldest->newest."""
    by_day: dict[str, list[float]] = {}
    for r in rows:
        by_day.setdefault(r["arrival_date"], []).append(r["modal_price"])
    points = [
        {"date": d, "price": round(sum(v) / len(v), 2)}
        for d, v in sorted(by_day.items())
    ]
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    return [p for p in points if p["date"] >= cutoff]


async def scrape_prices(
    crop: str,
    state: str | None = None,
    district: str | None = None,
    market: str | None = None,
    days: int = 90,
) -> list[dict]:
    """Keyless scrape of the Agmarknet public grid. Returns [] on any failure."""
    commodity = AGMARKNET_COMMODITY.get(crop.lower().strip())
    if not commodity or not state:
        return []

    cache_key = f"agmarknet-scrape:{crop.lower().strip()}:{_normalize(state)}:{_normalize(district or '')}:{_normalize(market or '')}"
    cached = cache_get(cache_key)
    if cached is not None:
        return cached

    commodity_code, state_code = await resolve_codes(commodity, state)
    if not commodity_code or not state_code:
        return []

    # SearchCmmMkt.aspx GET contract: codes in the query string, dates dd-MMM-yyyy.
    fmt = lambda d: d.strftime("%d-%b-%Y")
    to_date = date.today()
    from_date = to_date - timedelta(days=days)
    params = {
        "Tx_Commodity": commodity_code,
        "Tx_State": state_code,
        "Tx_District": "0",
        "Tx_Market": "0",
        "DateFrom": fmt(from_date),
        "DateTo": fmt(to_date),
        "Fr_Date": fmt(from_date),
        "To_Date": fmt(to_date),
        "Fr_Todate": fmt(from_date),
        "To_Todate": fmt(to_date),
        "Center_Commodity": commodity_code,
        "Center_State": state_code,
    }
    html = None
    try:
        async with httpx.AsyncClient(timeout=20, headers=_UA, follow_redirects=True) as client:
            resp = await client.get(SEARCH_URL, params=params)
            if resp.status_code < 400:
                html = resp.text
    except Exception as e:
        logger.warning("Agmarknet scrape: grid fetch failed: %s", e)
        return []
    if not html:
        return []

    rows = parse_grid(html)
    rows = filter_by_location(rows, district, market)
    points = average_by_day(rows, days)
    if points:
        cache_set(cache_key, points, ttl_seconds=6 * 3600)
    return points
