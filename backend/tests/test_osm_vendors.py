"""Classification + discovery tests for the OSM vendor pipeline.

Live Overpass is unreachable from CI (all mirrors time out), so these tests
mock `_run_query` and assert on the query text and parsed output instead.
They pin down the accuracy rules:
  * a generic hardware shop must NEVER classify as pesticide/produce_buyer,
  * tag evidence beats name evidence beats guessing,
  * tag-verified results survive even when the name says nothing agri,
  * tiers 1+2 cost ONE Overpass round trip, tier 3 only when results are thin.
"""
import time

import pytest

import app.services.osm_vendors as osm_mod
from app.core.cache import _memory_store
from app.services.agri_services import AGRI_CATEGORIES, CATEGORY_LABELS
from app.services.osm_vendors import (
    _categorize,
    _evidence_rank,
    _parse,
    _shops_query,
    _tier3_query,
    discover_vendors_osm,
    osm_cache_key,
)


@pytest.fixture(autouse=True)
def clean_cache():
    """The suite falls back to the in-process cache; keep tests isolated."""
    _memory_store.clear()
    yield
    _memory_store.clear()


# --------------------------------------------------------------------------
# _categorize — tag evidence beats name evidence beats guessing
# --------------------------------------------------------------------------


def test_generic_hardware_shop_is_not_pesticide():
    # Regression: this used to fall through to `return "pesticide"`.
    assert _categorize({"shop": "hardware"}, "sri lakshmi hardware") == "hardware"


def test_hardware_shop_with_trading_name_is_not_produce_buyer():
    # Regression: the weak rule ("... Mills", "... Traders") used to win.
    assert _categorize({"shop": "hardware"}, "balaji mills traders") == "hardware"
    assert _categorize({"shop": "trade"}, "venkatesh traders") == "hardware"


def test_wholesale_tag_is_produce_buyer():
    # vendor-range spec §3.5: wholesale trade buys produce.
    assert _categorize({"shop": "wholesale"}, "gods own wholesale") == "produce_buyer"


def test_untagged_place_with_trading_name_is_produce_buyer():
    # The weak rule still applies where the tag proves nothing.
    assert _categorize({}, "xyz procurement buyers") == "produce_buyer"


@pytest.mark.parametrize(
    "tags,expected",
    [
        ({"shop": "seeds"}, "seeds"),
        ({"shop": "fertilizer"}, "fertilizer"),
        ({"shop": "agriculture"}, "agri_store"),
        ({"shop": "agrarian"}, "agri_store"),
        ({"amenity": "marketplace"}, "market"),
        ({"shop": "agricultural_machinery"}, "equipment"),
        ({"craft": "agricultural_engines"}, "equipment"),
        ({"vending": "fertilizer"}, "fertilizer"),
    ],
)
def test_tag_verified_categories(tags, expected):
    assert _categorize(tags, "some unrelated name") == expected


def test_agri_named_hardware_shop_is_agri_store():
    # Tier 2: the name supplies the evidence the tag doesn't.
    assert _categorize({"shop": "hardware"}, "kisan agro centre") == "agri_store"
    assert _categorize({"shop": "hardware"}, "shri beej bhandar") == "seeds"


def test_pesticide_name_wins_over_untagged():
    assert _categorize({}, "agri pesticide works") == "pesticide"


def test_no_evidence_is_not_agri():
    assert _categorize({"shop": "clothes"}, "fashion point") is None
    assert _categorize({}, "fashion point") is None


# --------------------------------------------------------------------------
# _evidence_rank — ordering so the limit truncates generic hardware first
# --------------------------------------------------------------------------


def test_evidence_rank_tiers():
    assert _evidence_rank({"shop": "agriculture"}, "anything") == 0
    assert _evidence_rank({"amenity": "marketplace"}, "godown chowk") == 0
    assert _evidence_rank({"shop": "hardware"}, "sri lakshmi hardware") == 2
    assert _evidence_rank({"shop": "hardware"}, "kisan agro") == 1


# --------------------------------------------------------------------------
# _parse — tag-verified results survive even without an agri-looking name
# --------------------------------------------------------------------------


def test_parse_keeps_tag_verified_non_agri_named_results():
    # Regression: a post-parse name filter used to drop these entirely.
    parsed = _parse(
        [
            {
                "type": "node",
                "id": 1,
                "lat": 17.0,
                "lon": 78.0,
                "tags": {"amenity": "marketplace", "name": "Godown Chowk"},
            }
        ]
    )
    assert len(parsed) == 1
    assert parsed[0]["category"] == "market"
    assert parsed[0]["source"] == "osm"


def test_parse_assigns_rank_and_drops_uncategorizable():
    parsed = _parse(
        [
            {"type": "node", "id": 1, "lat": 17.0, "lon": 78.0,
             "tags": {"shop": "hardware", "name": "Plain Hardware"}},
            {"type": "node", "id": 2, "lat": 17.0, "lon": 78.1,
             "tags": {"shop": "clothes", "name": "Fashion Point"}},
        ]
    )
    assert len(parsed) == 1
    assert parsed[0]["_rank"] == 2


# --------------------------------------------------------------------------
# discover_vendors_osm — one merged round trip, tier 3 only when thin
# --------------------------------------------------------------------------


def _elements(n: int, start_id: int = 1) -> list[dict]:
    return [
        {
            "type": "node",
            "id": start_id + i,
            "lat": 17.0 + i * 0.001,
            "lon": 78.0 + i * 0.001,
            "tags": {"shop": "agriculture", "name": f"Agri Farm {start_id + i}"},
        }
        for i in range(n)
    ]


async def test_discovery_uses_single_merged_query_when_dense(monkeypatch):
    calls: list[str] = []

    async def fake_run(client, query):
        calls.append(query)
        return _elements(12)

    monkeypatch.setattr(osm_mod, "_run_query", fake_run)
    results = await discover_vendors_osm(17.0, 78.0, radius_m=45000)

    # Dense results -> tiers 1+2 only; the name-regex tier never runs.
    assert len(calls) == 1
    # One request carries both out statements (tag tiers + hardware tiers)...
    assert calls[0].count("out center tags") == 2
    # ...and contains no expensive name regex (that is tier 3's job).
    assert '["name"~' not in calls[0]
    assert '["name"~' in _tier3_query(17.0, 78.0, 45000)
    # `_rank` must never leak into cached/returned payloads.
    assert all("_rank" not in v for v in results)
    assert len(results) == 12


async def test_discovery_runs_tier3_only_when_results_are_thin(monkeypatch):
    calls: list[str] = []

    async def fake_run(client, query):
        calls.append(query)
        return _elements(3)

    monkeypatch.setattr(osm_mod, "_run_query", fake_run)
    await discover_vendors_osm(17.0, 78.0, radius_m=45000)
    assert len(calls) == 2
    assert calls[1] == _tier3_query(17.0, 78.0, 45000)


async def test_discovery_sorts_by_evidence_and_caps(monkeypatch):
    async def fake_run(client, query):
        # 5 tag-verified, then 5 generic hardware — output must interleave
        # evidence first regardless of response order.
        return _elements(5) + [
            {
                "type": "node",
                "id": 100 + i,
                "lat": 17.1 + i * 0.001,
                "lon": 78.1 + i * 0.001,
                "tags": {"shop": "hardware", "name": f"Plain Hardware {i}"},
            }
            for i in range(5)
        ]

    monkeypatch.setattr(osm_mod, "_run_query", fake_run)
    results = await discover_vendors_osm(17.0, 78.0, radius_m=45000, limit=6)
    assert len(results) == 6
    # Evidence first: all 5 tag-verified shops before any generic hardware.
    assert [v["category"] for v in results[:5]] == ["agri_store"] * 5
    assert results[5]["category"] == "hardware"


async def test_discovery_caches_results_and_hits_cache(monkeypatch):
    calls: list[str] = []

    async def fake_run(client, query):
        calls.append(query)
        return _elements(12)

    monkeypatch.setattr(osm_mod, "_run_query", fake_run)
    await discover_vendors_osm(17.5, 78.5, radius_m=45000)
    await discover_vendors_osm(17.5, 78.5, radius_m=45000)
    assert len(calls) == 1  # second call served from cache

    # Full-day TTL for non-empty results; 15 min for empty (see below).
    key = osm_cache_key(17.5, 78.5, 45000)
    expiry, _ = _memory_store[key]
    assert expiry - time.monotonic() > 86000


async def test_empty_results_use_short_ttl(monkeypatch):
    async def fake_run(client, query):
        return []

    monkeypatch.setattr(osm_mod, "_run_query", fake_run)
    results = await discover_vendors_osm(12.0, 79.0, radius_m=45000)
    assert results == []

    # radius 45000 skips escalation, so the empty result is cached briefly —
    # a transient all-mirrors outage must not blank an area for 24h.
    key = osm_cache_key(12.0, 79.0, 45000)
    expiry, _ = _memory_store[key]
    ttl = expiry - time.monotonic()
    assert 800 <= ttl <= 910


async def test_discovery_fails_soft_when_all_mirrors_fail(monkeypatch):
    async def fake_run(client, query):
        raise RuntimeError("Overpass failed on all mirrors")

    monkeypatch.setattr(osm_mod, "_run_query", fake_run)
    results = await discover_vendors_osm(13.0, 79.5, radius_m=45000)
    assert results == []


# --------------------------------------------------------------------------
# Wiring — the new hardware category must be complete end to end
# --------------------------------------------------------------------------


def test_hardware_category_is_wired_everywhere():
    assert "hardware" in AGRI_CATEGORIES
    # agri.py builds option lists with CATEGORY_LABELS[key] — KeyError otherwise.
    assert all(key in CATEGORY_LABELS for key in AGRI_CATEGORIES)
    assert "hardware" in osm_mod.CATEGORIES
