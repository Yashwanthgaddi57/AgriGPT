"""Unit tests for pure functions (no external services)."""
from app.ai.claude_client import extract_json
from app.services.market_service import synthetic_price_history


def test_extract_json_plain():
    assert extract_json('{"a": 1}') == {"a": 1}


def test_extract_json_fenced():
    text = 'Here you go:\n```json\n{"b": [1, 2]}\n```\nThanks!'
    assert extract_json(text) == {"b": [1, 2]}


def test_extract_json_with_prose():
    text = 'Sure! {"c": {"d": "e"}} hope that helps'
    assert extract_json(text) == {"c": {"d": "e"}}


def test_extract_json_raises_on_garbage():
    import pytest

    from app.core.exceptions import AIError

    with pytest.raises(AIError):
        extract_json("no json here at all")


def test_extract_json_repairs_truncated_output():
    """Model hit max_tokens mid-JSON -> repair closes brackets and drops dangling keys."""
    truncated = '{"current_price": 1600, "trend_weekly": 2.5, "trend_m'
    data = extract_json(truncated)
    assert data["current_price"] == 1600
    assert data["trend_weekly"] == 2.5


def test_extract_json_repairs_truncated_nested():
    truncated = '{"a": {"b": [1, 2]'
    data = extract_json(truncated)
    assert data == {"a": {"b": [1, 2]}}


def test_synthetic_price_history_shape():
    history = synthetic_price_history("wheat", days=30)
    assert len(history) == 31
    assert all("date" in p and "price" in p for p in history)
    # deterministic
    assert history == synthetic_price_history("wheat", days=30)
    # prices near base
    assert all(2000 < p["price"] < 2800 for p in history)


def test_season_helper():
    from app.services.dashboard_service import _season_now

    assert _season_now() in ("kharif", "rabi", "zaid")
