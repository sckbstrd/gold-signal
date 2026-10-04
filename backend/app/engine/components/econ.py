"""2.5 US economic data, scored on surprise (actual - consensus), decayed by age."""
from __future__ import annotations

from datetime import timedelta

from ..params import ModelParams
from ..primitives import rnd, sq
from ..result import RawComponent
from ..snapshot import MarketSnapshot, Release

CODE = "ECON"


def delayed_releases(snap: MarketSnapshot, params: ModelParams) -> list[Release]:
    """Tracked releases that were due (scheduled + grace) but are not published at as_of."""
    cfg = params.component(CODE)
    grace = timedelta(hours=cfg["delayed_grace_hours"])
    lookback = timedelta(days=cfg["delayed_lookback_days"])
    out = []
    for r in snap.releases:
        if r.code not in cfg["events"]:
            continue
        published = r.released_at is not None and r.released_at <= snap.as_of
        overdue = r.scheduled_at + grace <= snap.as_of
        if not published and overdue and snap.as_of - r.scheduled_at <= lookback:
            out.append(r)
    return sorted(out, key=lambda r: (r.scheduled_at, r.code))


def score(snap: MarketSnapshot, params: ModelParams) -> RawComponent:
    cfg = params.component(CODE)
    d = params.digits
    if not snap.econ_covered:
        return RawComponent(0.0, False, None, 0.0, extra={"events": [], "mass": 0.0, "delayed": []})
    events = []
    num = mass = 0.0
    usable = [r for r in snap.releases if r.code in cfg["events"] and r.usable_at(snap.as_of)]
    for r in sorted(usable, key=lambda r: (r.released_at, r.code), reverse=True):
        spec = cfg["events"][r.code]
        age_days = (snap.as_of - r.released_at).total_seconds() / 86400
        if age_days > cfg["window_days"]:
            continue
        surprise = r.actual - r.consensus
        z = surprise / spec["sigma"]
        impact = spec["importance"] * spec["direction"] * sq(z, params.dead_zone, params.kappa)
        decay = 0.5 ** (age_days / cfg["half_life_days"])
        num += impact * decay
        mass += spec["importance"] * decay
        events.append({
            "code": r.code, "reference_period": r.reference_period,
            "released_at": r.released_at.isoformat(), "age_days": rnd(age_days, d),
            "previous": r.previous, "consensus": r.consensus, "actual": r.actual,
            "surprise": rnd(surprise, d), "surprise_z": rnd(z, d),
            "importance": spec["importance"], "gold_direction": spec["direction"],
            "impact": rnd(impact, d), "decay": rnd(decay, d), "weighted": rnd(impact * decay, d),
        })
    s = num / max(mass, cfg["min_mass"])

    delayed = delayed_releases(snap, params)
    important = [r for r in delayed if cfg["events"][r.code]["importance"] >= cfg["delayed_min_importance"]]
    f = cfg["delayed_freshness"] if important else 1.0
    subs = [{"key": e["code"], "delta": e["surprise"], "sigma": cfg["events"][e["code"]]["sigma"],
             "z": e["surprise_z"], "score": e["impact"], "weight": e["decay"], "missing": False}
            for e in events]
    inputs = {"value": None, "observation_date": events[0]["released_at"][:10] if events else None,
              "change_unit": None, "changes": {}}
    extra = {
        "events": events,
        "mass": rnd(mass, d),
        "delayed": [{"code": r.code, "reference_period": r.reference_period,
                     "scheduled_at": r.scheduled_at.isoformat()} for r in delayed],
    }
    # A quiet calendar is genuinely neutral information, so the component is never MISSING.
    return RawComponent(rnd(s, d), True, 0, f, inputs, subs, extra)
