"""Tests for the keyless Agmarknet scrape tier."""
import asyncio
from datetime import date, timedelta

import pytest

from app.services import agmarknet_scraper as scraper


def _grid_html(rows: list[list[str]]) -> str:
    """Build a minimal SearchCmmMkt.aspx-style HTML grid (header + data rows)."""
    header = (
        "<tr><td>S.No</td><td>District</td><td>Market</td><td>Commodity</td>"
        "<td>Variety</td><td>Grade</td><td>Min</td><td>Max</td><td>Modal</td><td>Date</td></tr>"
    )
    body = header + "".join(
        "<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows
    )
    return f'<table id="cphBody_GridPriceData">{body}</table>'


def test_parse_grid_rows():
    today = date.today().strftime("%d/%m/%Y")
    html = _grid_html(
        [
            ["1", "Warangal", "Warangal", "Soyabean", "Black", "FAQ", "4500", "4800", "4650", today],
            ["2", "Karimnagar", "Karimnagar", "Soyabean", "Yellow", "FAQ", "4400", "4700", "4550", today],
        ]
    )
    rows = scraper.parse_grid(html)
    assert len(rows) == 2
    assert rows[0]["district"] == "Warangal"
    assert rows[0]["market"] == "Warangal"
    assert rows[0]["modal_price"] == 4650.0
    assert rows[0]["arrival_date"] == today.replace("/", "-")[::-1] or rows[0]["arrival_date"] == date.today().isoformat()


def test_parse_grid_skips_header_and_bad_rows():
    today = date.today().strftime("%d/%m/%Y")
    html = _grid_html(
        [
            ["1", "Warangal", "Warangal", "Soyabean", "Black", "FAQ", "4500", "4800", "n/a", today],  # bad modal
            ["2", "Warangal", "Warangal", "Soyabean", "Black", "FAQ", "4500", "4800", "4650", "bad-date"],  # bad date
            ["3", "Warangal", "Warangal", "Soyabean", "Black", "FAQ", "4500", "4800", "4700", today],  # good
        ]
    )
    rows = scraper.parse_grid(html)
    assert len(rows) == 1
    assert rows[0]["modal_price"] == 4700.0


def test_filter_by_location_prefers_market_then_district_then_all():
    rows = [
        {"district": "Nalgonda", "market": "Nalgonda", "modal_price": 1},
        {"district": "Warangal", "market": "Warangal Uppal", "modal_price": 2},
        {"district": "Rangareddy", "market": "LB Nagar", "modal_price": 3},
    ]
    # Market match (substring, case-insensitive)
    hits = scraper.filter_by_location(rows, "Warangal", "uppal")
    assert len(hits) == 1 and hits[0]["modal_price"] == 2
    # District match
    hits = scraper.filter_by_location(rows, "rangareddy", None)
    assert len(hits) == 1 and hits[0]["modal_price"] == 3
    # No match anywhere -> unfiltered fallback (farmer still sees state trades)
    hits = scraper.filter_by_location(rows, "Kamareddy", "Siddipet")
    assert len(hits) == 3


def test_average_by_day_groups_and_sorts():
    rows = [
        {"arrival_date": "2026-09-22", "modal_price": 4600.0},
        {"arrival_date": "2026-09-22", "modal_price": 4700.0},
        {"arrival_date": "2026-09-21", "modal_price": 4500.0},
    ]
    points = scraper.average_by_day(rows)
    assert points == [
        {"date": "2026-09-21", "price": 4500.0},
        {"date": "2026-09-22", "price": 4650.0},
    ]


def test_average_by_day_respects_window():
    old = (date.today() - timedelta(days=120)).isoformat()
    fresh = date.today().isoformat()
    points = scraper.average_by_day(
        [{"arrival_date": old, "modal_price": 100}, {"arrival_date": fresh, "modal_price": 200}],
        days=90,
    )
    assert [p["date"] for p in points] == [fresh]


@pytest.mark.asyncio
async def test_scrape_requires_state_and_known_crop():
    assert await scraper.scrape_prices("onion", state=None) == []
    assert await scraper.scrape_prices("dragonfruit", state="Telangana") == []


@pytest.mark.asyncio
async def test_scrape_end_to_end_with_fake_http(monkeypatch):
    """Codes resolve from dropdowns -> grid fetched -> filtered -> averaged."""
    from app.core.cache import _memory_store

    _memory_store.clear()
    today = date.today()
    yesterday = today - timedelta(days=1)
    pages = {
        # code-resolution page
        scraper.SEARCH_URL: (
            '<select id="ddlCommodity">'
            '<option value="0">--Select--</option><option value="112">Soyabean</option></select>'
            '<select id="ddlState">'
            '<option value="0">--Select--</option><option value="TL">Telangana</option></select>'
        ),
        # grid page (query differs, but the fake client ignores params)
        "GRID": _grid_html(
            [
                ["1", "Warangal", "Warangal", "Soyabean", "Black", "FAQ", "4500", "4800", "4650", today.strftime("%d/%m/%Y")],
                ["2", "Warangal", "Warangal", "Soyabean", "Yellow", "FAQ", "4550", "4850", "4750", today.strftime("%d/%m/%Y")],
                ["3", "Warangal", "Warangal", "Soyabean", "Black", "FAQ", "4400", "4700", "4550", yesterday.strftime("%d/%m/%Y")],
                ["4", "Nalgonda", "Nalgonda", "Soyabean", "Black", "FAQ", "4300", "4600", "4450", today.strftime("%d/%m/%Y")],
            ]
        ),
    }

    class FakeResponse:
        status_code = 200

        def __init__(self, text):
            self.text = text

        def raise_for_status(self):
            return None

    class FakeAsyncClient:
        def __init__(self, *a, **kw):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, url, params=None):
            if params:  # grid request carries query params
                return FakeResponse(pages["GRID"])
            return FakeResponse(pages[scraper.SEARCH_URL])

    monkeypatch.setattr(scraper.httpx, "AsyncClient", FakeAsyncClient)

    points = await scraper.scrape_prices(
        "soybean", state="Telangana", district="Warangal", market=None, days=90
    )
    # District filter keeps only Warangal rows: 2 varieties averaged per day.
    assert len(points) == 2
    assert points[-1] == {"date": today.isoformat(), "price": 4700.0}
    assert points[0] == {"date": yesterday.isoformat(), "price": 4550.0}

    _memory_store.clear()


@pytest.mark.asyncio
async def test_scrape_failsoft_on_network_error(monkeypatch):
    from app.core.cache import _memory_store

    _memory_store.clear()
    monkeypatch.setattr("app.core.config.settings.DATA_GOV_API_KEY", "")

    class BoomAsyncClient:
        def __init__(self, *a, **kw):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, *a, **kw):
            raise RuntimeError("network down")

    monkeypatch.setattr(scraper.httpx, "AsyncClient", BoomAsyncClient)
    assert await scraper.scrape_prices("soybean", state="Telangana") == []
    _memory_store.clear()
