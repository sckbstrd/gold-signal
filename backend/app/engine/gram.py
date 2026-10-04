"""Section 7: Turkish gram gold.

GramGold_TRY = XAUUSD / 31.1034768 * USDTRY.
The FX leg scores USD/TRY moves *in excess of the TRY-USD interest carry*, and
tilts the global score additively (a neutral lira leaves the global view intact).
"""
from __future__ import annotations

from .params import ModelParams
from .primitives import freshness, rnd, trend
from .snapshot import MarketSnapshot


def gram_price(xauusd: float, usdtry: float, params: ModelParams) -> float:
    return xauusd / params["gram"]["troy_oz_grams"] * usdtry


def fx_leg(snap: MarketSnapshot, i_usd: float | None, params: ModelParams) -> dict:
    cfg = params["gram"]
    d = params.digits
    fx = snap.usdtry
    age = fx.age_bdays(snap.as_of_date)
    fresh, hard = params["freshness"]["USDTRY"]
    f = freshness(age, fresh, hard)
    i_try = snap.try_policy_rate.last.value if snap.try_policy_rate.last else None
    if fx.last is None or i_try is None or i_usd is None:
        return {"s": 0.0, "freshness": 0.0, "status": "MISSING", "age_bdays": age,
                "i_try_pct": i_try, "i_usd_pct": i_usd}

    changes, carry, excess = {}, {}, []
    for h in cfg["fx_horizons_days"]:
        key = f"d{h}"
        ch = fx.change(h, "logpct")
        if ch is None:
            changes[key] = carry[key] = None
            excess.append(None)
            continue
        c = (i_try - i_usd) * ch.days / 365
        changes[key], carry[key] = rnd(ch.delta, d), rnd(c, d)
        excess.append(ch.delta - c)
    s, parts = trend(excess, cfg["fx_horizons_days"], cfg["fx_sigmas"], cfg["fx_weights"], +1,
                     params.dead_zone, params.kappa)
    status = "FRESH" if f >= 1 else "AGING" if f > 0 else "STALE"
    return {
        "s": rnd(s, d), "freshness": f, "status": status, "age_bdays": age,
        "usdtry": fx.last.value, "observation_date": fx.last.date.isoformat(),
        "usdtry_change_pct": changes, "carry_pct": carry,
        "excess_pct": {p.key: None if p.delta is None else rnd(p.delta, d) for p in parts},
        "i_try_pct": i_try, "i_usd_pct": i_usd,
        "sub_scores": [p.as_dict(d) for p in parts],
    }


def gram_score(global_score: float, fx: dict, params: ModelParams) -> tuple[float, float]:
    tilt = params["gram"]["fx_tilt_max"] * fx["freshness"] * fx["s"]
    return rnd(min(100.0, max(0.0, global_score + tilt)), 1), rnd(tilt, 2)


def legs_agree(global_score: float, fx: dict, params: ModelParams) -> bool:
    band = params["gram"]["global_neutral_band"]
    g = 0 if abs(global_score - 50) < band else (1 if global_score > 50 else -1)
    s = fx["s"] * fx["freshness"]
    x = 0 if abs(s) < params.neutral else (1 if s > 0 else -1)
    return g * x >= 0


def gram_confidence(global_conf: int, global_score: float, fx: dict, params: ModelParams) -> int:
    cfg = params["gram"]
    agree = 1.0 if legs_agree(global_score, fx, params) else 0.0
    return int(round(global_conf * (cfg["conf_base"] + cfg["conf_agree_bonus"] * agree) * fx["freshness"]))
