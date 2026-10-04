"""Shared helpers for trend-based components."""
from __future__ import annotations

from datetime import date

from ..params import ModelParams
from ..primitives import freshness, rnd, trend
from ..result import RawComponent
from ..snapshot import Series


def series_freshness(series: Series, as_of: date, params: ModelParams, key: str) -> tuple[int | None, float]:
    age = series.age_bdays(as_of)
    fresh, hard = params["freshness"][key]
    return age, freshness(age, fresh, hard)


def trend_component(
    series: Series,
    kind: str,
    cfg,
    params: ModelParams,
    as_of: date,
    freshness_key: str,
) -> RawComponent:
    """Generic multi-horizon trend component (Real Yield, DXY, ETF)."""
    if series.last is None:
        return RawComponent(0.0, False, None, 0.0)
    age, f = series_freshness(series, as_of, params, freshness_key)
    horizons = cfg["horizons_days"]
    deltas = [None if (c := series.change(h, kind)) is None else c.delta for h in horizons]
    s, parts = trend(deltas, horizons, cfg["sigmas"], cfg["weights"], cfg["direction"],
                     params.dead_zone, params.kappa)
    d = params.digits
    inputs = {
        "value": series.last.value,
        "observation_date": series.last.date.isoformat(),
        "change_unit": "bp" if kind == "bp" else "pct",
        "changes": {p.key: None if p.delta is None else rnd(p.delta, d) for p in parts},
    }
    has_any = any(x is not None for x in deltas)
    return RawComponent(rnd(s, d), has_any, age, f if has_any else 0.0,
                        inputs, [p.as_dict(d) for p in parts])
