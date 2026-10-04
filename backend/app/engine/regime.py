"""Section 6: market regime (GOLD_BULL / GOLD_BEAR / TRANSITION / PANIC)."""
from __future__ import annotations

import math

from .params import ModelParams
from .primitives import rnd
from .result import ComponentResult, RegimeState
from .snapshot import MarketSnapshot

PANIC = "PANIC"


def _pct(a: float | None, b: float | None) -> float | None:
    if a is None or b is None or b == 0:
        return None
    return 100.0 * (a / b - 1.0)


def _logpct(a: float | None, b: float | None) -> float | None:
    if a is None or b is None or a <= 0 or b <= 0:
        return None
    return 100.0 * math.log(a / b)


def panic_check(snap: MarketSnapshot, params: ModelParams) -> dict:
    """Evaluate every panic rule; missing inputs simply cannot trigger."""
    p = params["regime"]["panic"]
    val = lambda o: None if o is None else o.value  # noqa: E731
    vix = val(snap.vix.last)
    vix_5 = _pct(vix, val(snap.vix.back(5)))
    gold_1d = _logpct(val(snap.gold.last), val(snap.gold.back(1)))
    gold_5d = _logpct(val(snap.gold.last), val(snap.gold.back(5)))
    dxy_1d = _logpct(val(snap.dxy.last), val(snap.dxy.back(1)))
    rules = {
        "VIX_LEVEL": vix is not None and vix >= p["vix_level"],
        "VIX_SPIKE": vix is not None and vix_5 is not None
                     and vix >= p["vix_spike_level"] and vix_5 >= p["vix_spike_change_pct"],
        "GOLD_DAILY_MOVE": gold_1d is not None and abs(gold_1d) >= p["gold_1d_abs_pct"],
        "FORCED_LIQUIDATION": gold_5d is not None and vix is not None
                              and gold_5d <= p["gold_5d_pct"] and vix >= p["gold_5d_vix_min"],
        "DOLLAR_SQUEEZE": dxy_1d is not None and dxy_1d >= p["dxy_1d_pct"],
    }
    r = lambda x: None if x is None else rnd(x, 4)  # noqa: E731
    return {
        "triggered": any(rules.values()),
        "rules": [k for k, v in rules.items() if v],
        "inputs": {"vix": vix, "vix_5d_pct": r(vix_5), "gold_1d_pct": r(gold_1d),
                   "gold_5d_pct": r(gold_5d), "dxy_1d_pct": r(dxy_1d)},
    }


def candidate(components: dict[str, ComponentResult], score: float, panic: bool,
              score_change_20: float | None, params: ModelParams) -> tuple[str, dict]:
    cfg = params["regime"]
    major = params["major"]
    w_major = sum(params.weights[k] for k in major)
    th = cfg["breadth_threshold"]
    bull = sum(params.weights[k] for k in major if components[k].s_eff > th) / w_major
    bear = sum(params.weights[k] for k in major if components[k].s_eff < -th) / w_major
    info = {"bull_breadth": rnd(bull, 4), "bear_breadth": rnd(bear, 4),
            "score_change_20": None if score_change_20 is None else rnd(score_change_20, 1)}
    if panic:
        return PANIC, info
    rev = cfg["reversal_points"]
    ch = 0.0 if score_change_20 is None else score_change_20
    if bull >= cfg["breadth_min"] and score >= cfg["bull_score_min"] and ch > -rev:
        return "GOLD_BULL", info
    if bear >= cfg["breadth_min"] and score <= cfg["bear_score_max"] and ch < rev:
        return "GOLD_BEAR", info
    return "TRANSITION", info


def step(state: RegimeState, cand: str, params: ModelParams) -> RegimeState:
    """Advance the confirmed regime by one official evaluation."""
    cfg = params["regime"]
    if state.regime is None:
        return RegimeState(regime=cand)
    if cand == PANIC:
        return RegimeState(regime=PANIC)                       # enter immediately
    if state.regime == PANIC:
        calm = state.calm_days + 1
        if calm >= cfg["panic_exit_days"]:
            return RegimeState(regime=cand)
        return RegimeState(regime=PANIC, candidate=cand, calm_days=calm)
    if cand == state.regime:
        return RegimeState(regime=state.regime)
    days = state.candidate_days + 1 if cand == state.candidate else 1
    if days >= cfg["confirm_days"]:
        return RegimeState(regime=cand)
    return RegimeState(regime=state.regime, candidate=cand, candidate_days=days)


def pending_view(state: RegimeState, params: ModelParams) -> dict | None:
    if state.regime == PANIC and state.candidate is not None:
        return {"regime": state.candidate, "days": state.calm_days,
                "required": params["regime"]["panic_exit_days"]}
    if state.candidate is None or state.candidate_days == 0:
        return None
    return {"regime": state.candidate, "days": state.candidate_days,
            "required": params["regime"]["confirm_days"]}
