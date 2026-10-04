"""Section 4: signal confirmation logic.

A signal only changes when the score clears a band boundary by ``buffer`` points
for ``days`` consecutive official evaluations, or by ``decisive`` points once.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import date

from .aggregate import band_limits, band_of
from .params import ModelParams
from .result import SignalState


def step(state: SignalState, score: float, on: date, params: ModelParams) -> SignalState:
    """Advance the confirmed signal by ONE official evaluation."""
    raw = band_of(score, params)
    if state.signal is None:
        return SignalState(signal=raw, since=on, days_in_band=1)

    cfg = params["hysteresis"]
    lo, hi = band_limits(state.signal, params)
    if score >= hi + cfg["buffer"]:
        direction, beyond = +1, score - hi
    elif score < lo - cfg["buffer"]:
        direction, beyond = -1, lo - score
    else:
        direction, beyond = 0, 0.0

    if direction == 0:
        new = replace(state, pending_dir=0, pending_days=0)
    else:
        days = state.pending_days + 1 if direction == state.pending_dir else 1
        if days >= cfg["days"] or beyond >= cfg["decisive"]:
            new = SignalState(signal=raw, previous=state.signal, since=on, days_in_band=0)
        else:
            new = replace(state, pending_dir=direction, pending_days=days)

    if raw == new.signal:
        days_in_band = new.days_in_band + 1 if new.signal == state.signal else 1
    else:
        days_in_band = 0
    return replace(new, days_in_band=days_in_band)


def pending_view(state: SignalState, score: float, params: ModelParams) -> dict | None:
    if state.pending_dir == 0:
        return None
    return {
        "signal": band_of(score, params),
        "direction": "UP" if state.pending_dir > 0 else "DOWN",
        "days": state.pending_days,
        "required": params["hysteresis"]["days"],
    }
