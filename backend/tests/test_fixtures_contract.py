"""The Android mock fixtures must be current engine output in the documented API shape."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app import presenters
from app.engine import evaluate

MOCK = Path(__file__).resolve().parents[2] / "android" / "app" / "src" / "main" / "assets" / "mock"


@pytest.fixture()
def result(snapshot, prior, params):
    return evaluate(snapshot, prior, params).result


def _load(name):
    return json.loads((MOCK / name).read_text(encoding="utf-8"))


def test_signal_fixture_is_up_to_date(result):
    fresh = json.loads(json.dumps(presenters.signal_response(result, "2026-10-05T23:30:00+00:00")))
    assert _load("signal.json") == fresh, "run scripts/generate_android_fixtures.py"


def test_signal_fixture_shape():
    s = _load("signal.json")
    for key in ("model_version", "evaluated_at", "data_status", "global", "gram_try", "disclaimer_code"):
        assert key in s
    g = s["global"]
    assert set(g) >= {"score", "raw_band", "signal", "confidence", "regime", "components", "explanation"}
    assert [c["code"] for c in g["components"]] == [
        "REAL_YIELD", "FED", "DXY", "NOMINAL_10Y", "ECON", "ETF", "CENTRAL_BANKS"]
    assert round(sum(c["points"] for c in g["components"]), 1) == g["score"]
    assert set(g["explanation"]) == {"headline", "positive", "neutral", "negative", "warnings", "conclusion"}


def test_every_indicator_has_a_fixture():
    for code in ("REAL_YIELD", "FED", "DXY", "NOMINAL_10Y", "ECON", "ETF", "CENTRAL_BANKS", "GRAM_TRY"):
        d = _load(f"indicator_{code}.json")
        assert d["code"] == code
        assert "contribution" in d and "sub_scores" in d and "series" in d


def test_backtest_fixture_is_flagged_as_demo():
    b = _load("backtest_demo.json")
    assert b["is_demo"] is True
    assert {"code": "DEMO_DATA", "params": {}} in b["warnings"]
