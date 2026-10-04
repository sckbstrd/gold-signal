"""2.2 Fed expectations.

Current policy (target range, EFFR) and market-implied policy (T-bill proxy for
the expected path) are kept strictly separate. The score is 70% the *change* in
the expected path and 30% the amount of easing already priced over 12 months.
"""
from __future__ import annotations

from ..params import ModelParams
from ..primitives import rnd, sq, trend
from ..result import RawComponent
from ..snapshot import MarketSnapshot, Obs, Series
from .common import series_freshness

CODE = "FED"


def path_series(snap: MarketSnapshot) -> Series:
    """P = (implied 6M + implied 12M) / 2 on dates where both exist."""
    one_y = {o.date: o.value for o in snap.tbill_1y.obs}
    pts = tuple(Obs(o.date, (o.value + one_y[o.date]) / 2) for o in snap.tbill_6m.obs if o.date in one_y)
    return Series("FED_PATH", snap.tbill_6m.calendar, pts)


def score(snap: MarketSnapshot, params: ModelParams) -> RawComponent:
    cfg = params.component(CODE)
    d = params.digits
    path = path_series(snap)
    lower, upper = snap.fed_lower.last, snap.fed_upper.last
    if path.last is None or lower is None or upper is None:
        return RawComponent(0.0, False, None, 0.0)
    age, f = series_freshness(path, snap.as_of_date, params, CODE)

    horizons = cfg["horizons_days"]
    deltas = [None if (c := path.change(h, "bp")) is None else c.delta for h in horizons]
    repricing, parts = trend(deltas, horizons, cfg["sigmas"], cfg["weights"], cfg["direction"],
                             params.dead_zone, params.kappa)
    mid = (lower.value + upper.value) / 2
    r12 = snap.tbill_1y.last.value
    priced_bp = (r12 - mid) * 100
    stance_z = -priced_bp / cfg["stance_scale_bp"]
    stance = sq(stance_z, params.dead_zone, params.kappa)
    s = cfg["repricing_weight"] * repricing + cfg["stance_weight"] * stance

    inputs = {
        "value": rnd(path.last.value, d),
        "observation_date": path.last.date.isoformat(),
        "change_unit": "bp",
        "changes": {p.key: None if p.delta is None else rnd(p.delta, d) for p in parts},
    }
    subs = [{**p.as_dict(d), "weight": rnd(p.weight * cfg["repricing_weight"], d)} for p in parts]
    subs.append({"key": "stance", "delta": rnd(priced_bp, d), "sigma": cfg["stance_scale_bp"],
                 "z": rnd(stance_z, d), "score": rnd(stance, d),
                 "weight": cfg["stance_weight"], "missing": False})
    extra = {
        "current_policy": {
            "target_lower": lower.value, "target_upper": upper.value, "midpoint": mid,
            "effr": snap.effr.last.value if snap.effr.last else None,
        },
        "market_implied": {
            "method": "TBILL_PROXY",
            "r3m": snap.tbill_3m.last.value if snap.tbill_3m.last else None,
            "r6m": snap.tbill_6m.last.value, "r12m": r12,
            "path_point": rnd(path.last.value, d), "priced_12m_bp": rnd(priced_bp, 1),
        },
        "repricing": rnd(repricing, d),
        "stance": rnd(stance, d),
    }
    return RawComponent(rnd(s, d), True, age, f, inputs, subs, extra)
