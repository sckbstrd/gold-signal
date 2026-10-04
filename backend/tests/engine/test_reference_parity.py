"""Randomised parity: engine == executable spec on thousands of deterministic cases."""
from __future__ import annotations

import random
from dataclasses import replace
from datetime import date

from app.engine import calendars, hysteresis
from app.engine.aggregate import band_of
from app.engine.components import fed, trend_components
from app.engine.primitives import sq
from app.engine.result import SignalState
from tests.conftest import series_with_changes

END_GOVT = date(2026, 10, 1)
END_FX = date(2026, 10, 2)


def test_squash_matches_reference(ref, params):
    rng = random.Random(1)
    for _ in range(5000):
        z = rng.uniform(-8, 8)
        assert sq(z, params.dead_zone, params.kappa) == ref.sq(z)


def test_real_yield_matches_reference(ref, params, snapshot):
    rng = random.Random(2)
    for _ in range(150):
        d1, d7, d30 = (round(rng.uniform(-60, 60), 2) for _ in range(3))
        s = series_with_changes("US_REAL_10Y", calendars.US_GOVT, END_GOVT, 1.9,
                                {1: d1, 7: d7, 30: d30}, "bp")
        got = trend_components.real_yield(replace(snapshot, real_10y=s), params).s
        assert got == ref.real_yield(d1, d7, d30)["s"]


def test_dxy_matches_reference(ref, params, snapshot):
    rng = random.Random(3)
    for _ in range(150):
        d1, d7, d30 = (round(rng.uniform(-5, 5), 3) for _ in range(3))
        s = series_with_changes("DXY", calendars.FX, END_FX, 99.0, {1: d1, 7: d7, 30: d30}, "logpct")
        got = trend_components.dxy(replace(snapshot, dxy=s), params).s
        assert abs(got - ref.dxy(d1, d7, d30)["s"]) <= 1e-4   # log/exp round trip


def test_fed_matches_reference(ref, params, snapshot):
    rng = random.Random(4)
    for _ in range(100):
        d1, d7, d30 = (round(rng.uniform(-50, 50), 2) for _ in range(3))
        r12 = round(rng.uniform(2.0, 5.0), 3)
        r6 = round(r12 + rng.uniform(-0.3, 0.3), 3)
        tb6 = series_with_changes("US_TBILL_6M", calendars.US_GOVT, END_GOVT, r6,
                                  {1: d1, 7: d7, 30: d30}, "bp")
        tb1 = series_with_changes("US_TBILL_1Y", calendars.US_GOVT, END_GOVT, r12,
                                  {1: d1, 7: d7, 30: d30}, "bp")
        got = fed.score(replace(snapshot, tbill_6m=tb6, tbill_1y=tb1), params).s
        assert abs(got - ref.fed(d1, d7, d30, implied_12m=r12, policy_mid=3.625)["s"]) <= 1e-4


def test_hysteresis_matches_reference_on_random_paths(ref, params):
    rng = random.Random(5)
    for _ in range(300):
        engine_state = SignalState()
        ref_state = ref.HysteresisState()
        score = rng.uniform(10, 90)
        for day in range(60):
            score = min(100.0, max(0.0, score + rng.gauss(0, 4)))
            score = round(score, 1)
            engine_state = hysteresis.step(engine_state, score, date(2026, 1, 1), params)
            ref_state = ref.step_hysteresis(ref_state, score)
            assert engine_state.signal == ref_state.signal
            assert engine_state.pending_dir == ref_state.pending_dir
            assert engine_state.pending_days == ref_state.pending_days


def test_bands_match_reference(ref, params):
    for tenth in range(0, 1001):
        score = tenth / 10
        assert band_of(score, params) == ref.band_of(score)
