from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime, timedelta, timezone

import pytest

from app.engine import calendars, evaluate
from app.engine.aggregate import band_of
from app.engine.components import econ
from app.engine.gram import fx_leg, gram_price, gram_score
from app.engine.result import RegimeState
from app.engine.snapshot import Release, Series
from tests.conftest import series_with_changes

T = datetime(2026, 10, 2, 23, 30, tzinfo=timezone.utc)


def _one_release(snapshot, params, code, actual, consensus):
    r = Release(code, "x", T - timedelta(minutes=1), T - timedelta(minutes=1), None, consensus, actual)
    snap = replace(snapshot, releases=(r,))
    return econ.score(snap, params).extra["events"][0]


# ------------------------------------------------------------------ economic data
def test_user_nfp_example_is_bullish(snapshot, params):
    e = _one_release(snapshot, params, "NFP", 30.0, 100.0)
    assert e["surprise"] == -70.0
    assert e["impact"] == pytest.approx(0.329, abs=5e-4)


def test_user_cpi_example_is_bearish(snapshot, params):
    e = _one_release(snapshot, params, "CPI_YOY", 3.5, 3.1)
    assert e["impact"] == pytest.approx(-0.668, abs=5e-4)


def test_single_release_cannot_saturate(snapshot, params):
    r = Release("NFP", "x", T, T, None, 100.0, -500.0)
    s = econ.score(replace(snapshot, releases=(r,)), params).s
    assert 0.45 < s <= 0.5          # floor mass 2.0 halves a single max surprise


def test_delayed_release_degrades(snapshot, prior, params):
    late = Release("NFP", "2026-09-late", datetime(2026, 10, 2, 12, 30, tzinfo=timezone.utc), None,
                   22.0, 100.0, None)
    snap = replace(snapshot, releases=tuple(r for r in snapshot.releases if r.code != "NFP") + (late,))
    r = evaluate(snap, prior, params).result
    assert r.components["ECON"].freshness == 0.5
    assert r.data_status == "DEGRADED"
    assert any(w["code"] == "RELEASE_DELAYED" and w["params"]["event"] == "NFP" for w in r.warnings)


# ------------------------------------------------------------------ gram gold
def test_gram_price_formula(params):
    assert round(gram_price(4180.50, 49.85, params), 2) == 6700.15


def test_contrast_case_gram_hold_not_sell(ref, params, snapshot):
    """Bearish global gold + TRY depreciating far faster than carry => gram HOLD, not SELL."""
    usdtry = series_with_changes("USDTRY", calendars.FX, date(2026, 10, 2), 52.0,
                                 {1: 0.9, 7: 3.1, 30: 8.4}, "logpct")
    fx = fx_leg(replace(snapshot, usdtry=usdtry), 3.625, params)
    expected = ref.run_example()["gram_contrast_case"]
    assert fx["s"] == pytest.approx(expected["s_fx"], abs=1e-4)
    score, _ = gram_score(31.0, fx, params)
    assert band_of(31.0, params) == "REDUCE"
    assert score == pytest.approx(expected["gram_score"], abs=0.05)
    assert band_of(score, params) == "HOLD"


def test_missing_fx_leg_leaves_gram_equal_to_global(snapshot, prior, params):
    r = evaluate(replace(snapshot, usdtry=Series("USDTRY", calendars.FX)), prior, params).result
    assert r.gram.score == r.global_.score
    assert r.gram.confidence == 0


# ------------------------------------------------------------------ regime
def _vix_spike(snapshot, level):
    obs = list(snapshot.vix.obs)
    obs[-1] = replace(obs[-1], value=level)
    return replace(snapshot, vix=replace(snapshot.vix, obs=tuple(obs)))


def test_panic_enters_immediately_and_cuts_confidence(snapshot, prior, params):
    calm = evaluate(snapshot, prior, params).result
    panic = evaluate(_vix_spike(snapshot, 41.0), prior, params).result
    assert panic.regime == "PANIC"
    assert "VIX_LEVEL" in panic.panic_trigger["rules"]
    assert panic.global_.confidence < calm.global_.confidence
    assert panic.global_.explanation["conclusion"]["code"] == "PANIC_CAUTION"


def _weekdays(snapshot, n):
    """The same data evaluated on n successive weekdays starting at as_of."""
    out, day = [], 0
    while len(out) < n:
        snap = replace(snapshot, as_of=snapshot.as_of + timedelta(days=day))
        day += 1
        if snap.as_of.weekday() < 5:
            out.append(snap)
    return out


def _run(snaps, state, params):
    regimes = []
    for snap in snaps:
        ev = evaluate(snap, state, params)
        state = ev.state
        regimes.append(ev.result.regime)
    return regimes


def test_panic_exit_needs_five_calm_evaluations(snapshot, prior, params):
    regimes = _run(_weekdays(snapshot, 5), replace(prior, regime=RegimeState(regime="PANIC")), params)
    assert regimes[:4] == ["PANIC"] * 4
    assert regimes[4] != "PANIC"


def test_regime_change_needs_three_days(snapshot, params, prior):
    regimes = _run(_weekdays(snapshot, 3), replace(prior, regime=RegimeState(regime="GOLD_BEAR")), params)
    assert regimes == ["GOLD_BEAR", "GOLD_BEAR", "GOLD_BULL"]


# ------------------------------------------------------------------ calendars
@pytest.mark.parametrize("d,cal,expected", [
    (date(2026, 4, 3), calendars.NYSE, False),        # Good Friday
    (date(2026, 4, 3), calendars.US_GOVT, True),
    (date(2026, 7, 3), calendars.NYSE, False),        # Independence Day observed
    (date(2026, 10, 12), calendars.US_GOVT, False),   # Columbus Day: no Treasury prints
    (date(2026, 10, 12), calendars.NYSE, True),
    (date(2026, 11, 11), calendars.US_GOVT, False),   # Veterans Day
    (date(2026, 11, 26), calendars.NYSE, False),      # Thanksgiving
    (date(2021, 12, 31), calendars.US_GOVT, False),   # Saturday New Year observed Friday
    (date(2021, 12, 31), calendars.NYSE, True),       # ...but NYSE stays open
    (date(2026, 6, 19), calendars.NYSE, False),       # Juneteenth
    (date(2026, 12, 25), calendars.FX, False),
    (date(2026, 12, 24), calendars.FX, True),
])
def test_holidays(d, cal, expected):
    assert calendars.is_business_day(d, cal) is expected


def test_business_day_age_skips_weekends_and_holidays():
    assert calendars.business_days_between(date(2026, 10, 2), date(2026, 10, 5), calendars.NYSE) == 1
    assert calendars.business_days_between(date(2026, 10, 9), date(2026, 10, 13), calendars.US_GOVT) == 1
    assert calendars.business_days_between(date(2026, 10, 2), date(2026, 10, 2), calendars.NYSE) == 0
