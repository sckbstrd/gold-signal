"""2.7 Central-bank gold purchases (monthly, keyed by publication date). Long-term only."""
from __future__ import annotations

from ..calendars import NYSE, business_days_between
from ..params import ModelParams
from ..primitives import freshness, rnd, sq
from ..result import RawComponent
from ..snapshot import MarketSnapshot

CODE = "CENTRAL_BANKS"


def score(snap: MarketSnapshot, params: ModelParams) -> RawComponent:
    cfg = params.component(CODE)
    d = params.digits
    months = sorted((m for m in snap.cb_months if m.available_at <= snap.as_of), key=lambda m: m.period)
    if len(months) < 12:
        return RawComponent(0.0, False, None, 0.0, extra={"months_available": len(months)})
    last12 = months[-12:]
    t12 = sum(m.net_tonnes for m in last12)
    t3 = sum(m.net_tonnes for m in last12[-3:])
    level_z = (t12 - cfg["baseline_t"]) / cfg["level_scale_t"]
    momentum_z = (4 * t3 - t12) / cfg["momentum_scale_t"]
    level = sq(level_z, params.dead_zone, params.kappa)
    momentum = sq(momentum_z, params.dead_zone, params.kappa)
    s = cfg["level_weight"] * level + cfg["momentum_weight"] * momentum

    published = max(m.available_at for m in last12).date()
    age = business_days_between(published, snap.as_of_date, NYSE)
    fresh, hard = params["freshness"][CODE]
    f = freshness(age, fresh, hard)
    inputs = {"value": rnd(t12, 2), "observation_date": last12[-1].period.isoformat(),
              "change_unit": "tonnes", "changes": {}}
    subs = [
        {"key": "level", "delta": rnd(t12 - cfg["baseline_t"], d), "sigma": cfg["level_scale_t"],
         "z": rnd(level_z, d), "score": rnd(level, d), "weight": cfg["level_weight"], "missing": False},
        {"key": "momentum", "delta": rnd(4 * t3 - t12, d), "sigma": cfg["momentum_scale_t"],
         "z": rnd(momentum_z, d), "score": rnd(momentum, d), "weight": cfg["momentum_weight"],
         "missing": False},
    ]
    extra = {
        "t12_tonnes": rnd(t12, 2), "t3_tonnes": rnd(t3, 2), "baseline_tonnes": cfg["baseline_t"],
        "published": published.isoformat(),
        "monthly": [[m.period.strftime("%Y-%m"), m.net_tonnes] for m in last12],
    }
    return RawComponent(rnd(s, d), True, age, f, inputs, subs, extra)
