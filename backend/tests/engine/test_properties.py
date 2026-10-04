"""Model properties that must hold for ANY input, not just the example."""
from __future__ import annotations

import random
from dataclasses import replace
from datetime import date

from app.engine import calendars, evaluate
from app.engine.components import trend_components
from app.engine.snapshot import Series
from tests.conftest import series_with_changes, shift_as_of

END = date(2026, 10, 1)


def _real(d1, d7, d30):
    return series_with_changes("US_REAL_10Y", calendars.US_GOVT, END, 1.8, {1: d1, 7: d7, 30: d30}, "bp")


def test_score_and_points_bounded(snapshot, prior, params):
    rng = random.Random(11)
    for _ in range(40):
        d = [rng.uniform(-200, 200) for _ in range(3)]
        snap = replace(snapshot, real_10y=_real(*d))
        r = evaluate(snap, prior, params).result
        assert 0 <= r.global_.score <= 100
        assert 0 <= r.gram.score <= 100
        assert 0 <= r.global_.confidence <= 100
        for c in r.components.values():
            assert -1 < c.s < 1
            assert 0 <= c.points <= c.weight


def test_noise_is_ignored(snapshot, params):
    """Moves below a quarter of the typical move contribute exactly zero."""
    snap = replace(snapshot, real_10y=_real(-1.0, -2.5, -5.0))   # 0.2 sigma on every horizon
    assert trend_components.real_yield(snap, params).s == 0.0


def test_magnitude_matters(snapshot, params):
    small = trend_components.real_yield(replace(snapshot, real_10y=_real(-3, -8, -15)), params).s
    large = trend_components.real_yield(replace(snapshot, real_10y=_real(-12, -30, -70)), params).s
    assert 0 < small < large < 1


def test_monotone_in_real_yield_change(snapshot, params):
    prev = -1.0
    for d30 in range(120, -121, -10):
        s = trend_components.real_yield(replace(snapshot, real_10y=_real(0, 0, d30)), params).s
        assert s >= prev
        prev = s


def test_symmetry(snapshot, params):
    up = trend_components.real_yield(replace(snapshot, real_10y=_real(4, 13, 31)), params).s
    down = trend_components.real_yield(replace(snapshot, real_10y=_real(-4, -13, -31)), params).s
    assert up == -down


def test_stale_data_fades_to_neutral_and_flags_delay(snapshot, prior, params):
    real_only_old = replace(snapshot, real_10y=snapshot.real_10y.upto(date(2026, 9, 18)))
    r = evaluate(real_only_old, prior, params).result
    c = r.components["REAL_YIELD"]
    assert c.freshness == 0.0 and c.s_eff == 0.0 and c.points == 15.0
    assert c.status == "STALE"
    assert r.data_status == "DELAYED"
    assert r.global_.confidence <= 40
    assert any(w["code"] == "COMPONENT_STALE" for w in r.warnings)


def test_aging_data_partially_decays(snapshot, prior, params):
    aging = replace(snapshot, real_10y=snapshot.real_10y.upto(date(2026, 9, 28)))   # 4 bdays old
    c = evaluate(aging, prior, params).result.components["REAL_YIELD"]
    assert c.status == "AGING"
    assert 0 < c.freshness < 1
    assert abs(c.s_eff) < abs(c.s)


def test_missing_component_is_neutral(snapshot, prior, params):
    r = evaluate(replace(snapshot, etf_holdings=Series("ETF_HOLDINGS_T", calendars.NYSE)),
                 prior, params).result
    c = r.components["ETF"]
    assert c.status == "MISSING" and c.points == 5.0
    assert r.data_status == "DEGRADED"


def test_weekend_does_not_make_data_stale(snapshot, prior, params):
    """Evaluated on Monday, Friday's data is 1 business day old, not 3 calendar days."""
    r = evaluate(shift_as_of(snapshot, 3), prior, params).result
    assert r.components["DXY"].age_bdays == 1
    assert r.components["DXY"].freshness == 1.0


def test_deterministic(snapshot, prior, params):
    a = evaluate(snapshot, prior, params).result
    b = evaluate(snapshot, prior, params).result
    assert a == b
    assert a.inputs_sha256 == b.inputs_sha256


def test_inputs_hash_changes_with_inputs(snapshot, prior, params):
    a = evaluate(snapshot, prior, params).result
    b = evaluate(replace(snapshot, real_10y=_real(-3, -11, -29)), prior, params).result
    assert a.inputs_sha256 != b.inputs_sha256


def test_official_evaluations_must_move_forward(snapshot, prior, params):
    import pytest
    ev = evaluate(snapshot, prior, params)
    with pytest.raises(ValueError):
        evaluate(snapshot, ev.state, params)
