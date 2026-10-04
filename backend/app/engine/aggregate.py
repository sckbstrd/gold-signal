"""Section 3: aggregation into the 0-100 Gold Score, and band lookup."""
from __future__ import annotations

from .params import ModelParams
from .primitives import rnd
from .result import ComponentResult, RawComponent, status_for

BAND_ORDER = ("SELL", "REDUCE", "HOLD", "BUY", "STRONG_BUY")


def band_of(score: float, params: ModelParams) -> str:
    bands = params["bands"]
    for label in reversed(BAND_ORDER):
        if score >= bands[label]:
            return label
    return "SELL"


def band_limits(label: str, params: ModelParams) -> tuple[float, float]:
    """[lo, hi) of a band; the top band's hi is open (+inf)."""
    bands = params["bands"]
    idx = BAND_ORDER.index(label)
    lo = float(bands[label])
    hi = float(bands[BAND_ORDER[idx + 1]]) if idx + 1 < len(BAND_ORDER) else float("inf")
    return lo, hi


def finalize(code: str, raw: RawComponent, params: ModelParams) -> ComponentResult:
    d = params.digits
    w = params.weights[code]
    s_eff = rnd(raw.freshness * raw.s, d)
    points = w * (1 + s_eff) / 2
    impact = "BULLISH" if s_eff >= params.neutral else "BEARISH" if s_eff <= -params.neutral else "NEUTRAL"
    return ComponentResult(
        code=code, weight=w, s=raw.s, freshness=raw.freshness, s_eff=s_eff,
        points=rnd(points, 2), tilt=rnd(points - w / 2, 2), impact=impact,
        status=status_for(raw.freshness, raw.has_data), age_bdays=raw.age_bdays,
        inputs=raw.inputs, sub_scores=raw.sub_scores, extra=raw.extra,
    )


def gold_score(components: dict[str, ComponentResult]) -> float:
    return rnd(sum(c.points for c in components.values()), 1)
