from __future__ import annotations

from datetime import date

from app.engine import hysteresis
from app.engine.result import SignalState

D = date(2026, 1, 5)


def run(start: str, scores: list[float], params) -> list[SignalState]:
    state = SignalState(signal=start)
    out = []
    for s in scores:
        state = hysteresis.step(state, s, D, params)
        out.append(state)
    return out


def test_documented_demo_table(params):
    scores = [58.0, 61.5, 64.2, 62.8, 63.4, 65.1, 66.0, 71.0, 59.0, 56.5, 47.0]
    states = run("HOLD", scores, params)
    assert [s.signal for s in states] == ["HOLD"] * 6 + ["BUY"] * 4 + ["HOLD"]
    assert [s.pending_days for s in states] == [0, 0, 1, 0, 1, 2, 0, 0, 0, 1, 0]


def test_decisive_move_confirms_immediately(params):
    (state,) = run("HOLD", [72.0], params)
    assert state.signal == "BUY" and state.previous == "HOLD" and state.since == D


def test_can_skip_bands(params):
    (state,) = run("HOLD", [86.0], params)
    assert state.signal == "STRONG_BUY"


def test_inside_buffer_never_changes(params):
    states = run("HOLD", [62.9] * 30 + [37.1] * 30, params)
    assert {s.signal for s in states} == {"HOLD"}


def test_top_and_bottom_bands_are_absorbing_without_reverse_move(params):
    assert {s.signal for s in run("STRONG_BUY", [100.0] * 10, params)} == {"STRONG_BUY"}
    assert {s.signal for s in run("SELL", [0.0] * 10, params)} == {"SELL"}


def test_direction_reversal_resets_pending(params):
    states = run("HOLD", [64.0, 64.0, 36.0, 36.0, 64.0], params)
    assert [s.pending_dir for s in states] == [1, 1, -1, -1, 1]
    assert [s.pending_days for s in states] == [1, 2, 1, 2, 1]
    assert states[-1].signal == "HOLD"


def test_days_in_band_counts_and_resets(params):
    states = run("BUY", [65.0, 66.0, 58.0, 65.0], params)
    assert [s.days_in_band for s in states] == [1, 2, 0, 1]
