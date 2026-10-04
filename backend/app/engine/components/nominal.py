"""2.4 US 10Y nominal yield, de-duplicated against the real-yield engine.

nominal = real + breakeven. The real part is already scored by REAL_YIELD, so
this component scores only (a) the breakeven (inflation-expectations) trend and
(b) the nominal level relative to its own trailing 252-observation norm.
"""
from __future__ import annotations

import statistics

from ..params import ModelParams
from ..primitives import rnd, sq, trend
from ..result import RawComponent
from ..snapshot import MarketSnapshot, Obs, Series
from .common import series_freshness

CODE = "NOMINAL_10Y"


def breakeven_series(snap: MarketSnapshot) -> Series:
    real = {o.date: o.value for o in snap.real_10y.obs}
    pts = tuple(Obs(o.date, o.value - real[o.date]) for o in snap.nominal_10y.obs if o.date in real)
    return Series("US_BREAKEVEN_10Y", snap.nominal_10y.calendar, pts)


def score(snap: MarketSnapshot, params: ModelParams) -> RawComponent:
    cfg = params.component(CODE)
    d = params.digits
    nominal = snap.nominal_10y
    if nominal.last is None:
        return RawComponent(0.0, False, None, 0.0)
    age, f = series_freshness(nominal, snap.as_of_date, params, CODE)

    be = breakeven_series(snap)
    horizons = cfg["horizons_days"]
    deltas = [None if (c := be.change(h, "bp")) is None else c.delta for h in horizons]
    be_trend, parts = trend(deltas, horizons, cfg["be_sigmas"], cfg["weights"], +1,
                            params.dead_zone, params.kappa)

    window = nominal.tail(cfg["level_window_obs"])
    level = nominal.last.value
    if len(window) >= cfg["level_min_obs"]:
        mean = statistics.fmean(window)
        std = statistics.pstdev(window)
        std_used = max(std, cfg["level_std_floor_pct"])
        z_level = (level - mean) / std_used
        level_score = sq(-z_level, params.dead_zone, params.kappa)
    else:
        mean = std = std_used = z_level = None
        level_score = 0.0

    be_part = cfg["be_weight"] * be_trend
    level_part = cfg["level_weight"] * level_score
    s = be_part + level_part

    subs = [{**p.as_dict(d), "weight": rnd(p.weight * cfg["be_weight"], d)} for p in parts]
    subs.append({
        "key": "level",
        "delta": None if mean is None else rnd((level - mean) * 100, d),
        "sigma": None if std_used is None else rnd(std_used * 100, d),
        "z": None if z_level is None else rnd(z_level, d),
        "score": rnd(level_score, d), "weight": cfg["level_weight"], "missing": mean is None,
    })
    inputs = {
        "value": level,
        "observation_date": nominal.last.date.isoformat(),
        "change_unit": "bp",
        "changes": {f"d{h}": None if (c := nominal.change(h, "bp")) is None else rnd(c.delta, d)
                    for h in horizons},
        "breakeven_changes": {p.key: None if p.delta is None else rnd(p.delta, d) for p in parts},
    }
    extra = {
        "nominal": level,
        "real": snap.real_10y.last.value if snap.real_10y.last else None,
        "breakeven": None if be.last is None else rnd(be.last.value, d),
        "mean_252": None if mean is None else rnd(mean, d),
        "std_252": None if std is None else rnd(std, d),
        "z_level": None if z_level is None else rnd(z_level, d),
        "breakeven_trend": rnd(be_trend, d),
        "level_score": rnd(level_score, d),
        "be_part": rnd(be_part, d),
        "level_part": rnd(level_part, d),
    }
    return RawComponent(rnd(s, d), True, age, f, inputs, subs, extra)
