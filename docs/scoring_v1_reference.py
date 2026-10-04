"""
Gold Signal - Scoring Model v1.0.0 - executable reference.

This file IS the specification in code form. It is pure (no I/O, no clock,
no randomness), so the same inputs always give the same outputs. The worked
example in 02_SCORING_MODEL_V1.md is produced by running:

    python scoring_v1_reference.py

The production engine (backend/app/engine) must reproduce these numbers
exactly; its unit tests import the EXAMPLE_* fixtures below.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

MODEL_VERSION = "1.0.0"

# --------------------------------------------------------------------------
# Global constants (frozen for v1.0.0 - any change => new model version)
# --------------------------------------------------------------------------
DEAD_ZONE = 0.25          # moves smaller than 0.25 "typical moves" are noise
KAPPA = 2.0               # squash softness: tanh(z / 2)
ROUND = 4                 # round component outputs for cross-platform determinism

WEIGHTS = {
    "REAL_YIELD": 30, "FED": 20, "DXY": 15, "NOMINAL_10Y": 10,
    "ECON": 10, "ETF": 10, "CENTRAL_BANKS": 5,
}
CRITICAL = ("REAL_YIELD", "FED", "DXY")
MAJOR = ("REAL_YIELD", "FED", "DXY", "NOMINAL_10Y", "ECON")

BANDS = [  # (lower bound inclusive, label)
    (75.0, "STRONG_BUY"), (60.0, "BUY"), (40.0, "HOLD"), (25.0, "REDUCE"), (0.0, "SELL"),
]
BAND_ORDER = ["SELL", "REDUCE", "HOLD", "BUY", "STRONG_BUY"]
BAND_LIMITS = {  # [lo, hi)
    "SELL": (0.0, 25.0), "REDUCE": (25.0, 40.0), "HOLD": (40.0, 60.0),
    "BUY": (60.0, 75.0), "STRONG_BUY": (75.0, 100.0001),
}
HYST_BUFFER = 3.0         # score must clear a boundary by 3 points...
HYST_DAYS = 3             # ...for 3 consecutive official evaluations
HYST_DECISIVE = 10.0      # or clear it by 10 points once

# Freshness limits in business days (series calendar): (fresh, hard)
FRESHNESS = {
    "REAL_YIELD": (2, 7), "FED": (2, 7), "DXY": (2, 7), "NOMINAL_10Y": (2, 7),
    "ETF": (5, 15), "CENTRAL_BANKS": (55, 110), "USDTRY": (2, 7),
}


# --------------------------------------------------------------------------
# Primitives
# --------------------------------------------------------------------------
def soft(z: float, d: float = DEAD_ZONE) -> float:
    """Soft dead-zone: shrink |z| by d, never cross zero."""
    return math.copysign(max(abs(z) - d, 0.0), z)


def sq(z: float) -> float:
    """Squash a standardized move into (-1, 1) with a noise dead-zone."""
    return math.tanh(soft(z) / KAPPA)


def trend(deltas, sigmas, omegas, direction: int) -> float:
    """Multi-horizon trend score in (-1, 1).

    deltas : change over each horizon (same unit as sigmas)
    sigmas : reference 'typical move' per horizon
    omegas : horizon weights (sum to 1)
    direction : +1 if a rise is bullish for gold, -1 if a rise is bearish
    """
    return sum(w * sq(direction * d / s) for d, s, w in zip(deltas, sigmas, omegas))


def freshness(age_bdays: int | None, fresh: int, hard: int) -> float:
    if age_bdays is None:
        return 0.0
    if age_bdays <= fresh:
        return 1.0
    if age_bdays >= hard:
        return 0.0
    return (hard - age_bdays) / (hard - fresh)


def r(x: float) -> float:
    return round(x, ROUND)


H3 = (0.2, 0.3, 0.5)  # 1D / 7D / 30D horizon weights


# --------------------------------------------------------------------------
# Component engines. Inputs are already-computed horizon changes.
# Units: yields in percent (changes in basis points), FX/DXY/ETF in % log-change.
# --------------------------------------------------------------------------
def real_yield(d1_bp, d7_bp, d30_bp) -> dict:
    s = trend((d1_bp, d7_bp, d30_bp), (5, 12, 25), H3, -1)
    return {"s": r(s)}


def fed(p_d1_bp, p_d7_bp, p_d30_bp, implied_12m, policy_mid) -> dict:
    repricing = trend((p_d1_bp, p_d7_bp, p_d30_bp), (4, 10, 22), H3, -1)
    easing_bp = (implied_12m - policy_mid) * 100      # negative = cuts priced
    stance = sq(-easing_bp / 50)
    return {"s": r(0.7 * repricing + 0.3 * stance),
            "repricing": r(repricing), "stance": r(stance), "priced_bp_12m": round(easing_bp, 1)}


def dxy(d1_pct, d7_pct, d30_pct) -> dict:
    return {"s": r(trend((d1_pct, d7_pct, d30_pct), (0.45, 1.0, 2.1), H3, -1))}


def nominal_10y(be_d1_bp, be_d7_bp, be_d30_bp, level, mean_252, std_252) -> dict:
    breakeven = trend((be_d1_bp, be_d7_bp, be_d30_bp), (3, 7, 15), H3, +1)
    z_level = (level - mean_252) / max(std_252, 0.10)
    level_score = sq(-z_level)
    return {"s": r(0.6 * breakeven + 0.4 * level_score),
            "breakeven": r(breakeven), "level": r(level_score), "z_level": r(z_level)}


# code: (gold_sign, typical surprise sigma, importance)
ECON_SPEC = {
    "CPI_YOY":        (-1, 0.1, 0.7),
    "CORE_CPI_MOM":   (-1, 0.1, 1.0),
    "PCE_YOY":        (-1, 0.1, 0.5),
    "CORE_PCE_MOM":   (-1, 0.1, 0.8),
    "NFP":            (-1, 75.0, 1.0),   # thousands of jobs
    "UNEMPLOYMENT":   (+1, 0.1, 0.8),
    "INITIAL_CLAIMS": (+1, 15.0, 0.3),   # thousands
    "ISM_MFG":        (-1, 2.0, 0.5),
    "ISM_SERVICES":   (-1, 2.0, 0.5),
}
ECON_HALF_LIFE_DAYS = 14.0
ECON_WINDOW_DAYS = 60
ECON_MIN_MASS = 2.0


@dataclass
class Release:
    code: str
    age_days: float       # calendar days between release time and evaluation time
    actual: float
    consensus: float


def econ(releases: list[Release], high_importance_delayed: bool = False) -> dict:
    num = 0.0
    mass = 0.0
    items = []
    for ev in releases:
        if ev.age_days < 0 or ev.age_days > ECON_WINDOW_DAYS:
            continue  # not yet released (look-ahead guard) or too old
        g, sigma, imp = ECON_SPEC[ev.code]
        surprise = ev.actual - ev.consensus
        e = imp * g * sq(surprise / sigma)
        d = 0.5 ** (ev.age_days / ECON_HALF_LIFE_DAYS)
        num += e * d
        mass += imp * d
        items.append({"code": ev.code, "surprise": round(surprise, 4),
                      "impact": r(e), "decay": r(d)})
    s = num / max(mass, ECON_MIN_MASS)
    f = 0.5 if high_importance_delayed else 1.0
    return {"s": r(s), "freshness": f, "events": items}


def etf(d7_pct, d30_pct, d90_pct) -> dict:
    return {"s": r(trend((d7_pct, d30_pct, d90_pct), (1.0, 2.5, 5.0), (0.1, 0.5, 0.4), +1))}


def central_banks(trailing_12m_t, trailing_3m_t) -> dict:
    level = sq((trailing_12m_t - 500) / 250)
    momentum = sq((4 * trailing_3m_t - trailing_12m_t) / 400)
    return {"s": r(0.7 * level + 0.3 * momentum), "level": r(level), "momentum": r(momentum)}


# --------------------------------------------------------------------------
# Aggregation
# --------------------------------------------------------------------------
def band_of(score: float) -> str:
    for lo, label in BANDS:
        if score >= lo:
            return label
    return "SELL"


def aggregate(s: dict[str, float], f: dict[str, float]) -> dict:
    comps = {}
    for k, w in WEIGHTS.items():
        se = f[k] * s[k]
        pts = w * (1 + se) / 2
        comps[k] = {"weight": w, "s": s[k], "freshness": f[k], "s_eff": r(se),
                    "points": round(pts, 2), "tilt": round(pts - w / 2, 2)}
    score = round(sum(c["points"] for c in comps.values()), 1)
    return {"score": score, "raw_band": band_of(score), "components": comps}


@dataclass
class HysteresisState:
    signal: str | None = None
    pending_dir: int = 0        # +1 upgrade pending, -1 downgrade pending
    pending_days: int = 0


def step_hysteresis(state: HysteresisState, score: float) -> HysteresisState:
    """Advance the confirmed signal by one OFFICIAL evaluation."""
    if state.signal is None:
        return HysteresisState(band_of(score), 0, 0)
    lo, hi = BAND_LIMITS[state.signal]
    if score >= hi + HYST_BUFFER:
        direction, beyond = +1, score - hi
    elif score < lo - HYST_BUFFER:
        direction, beyond = -1, lo - score
    else:
        return HysteresisState(state.signal, 0, 0)
    days = state.pending_days + 1 if direction == state.pending_dir else 1
    if days >= HYST_DAYS or beyond >= HYST_DECISIVE:
        return HysteresisState(band_of(score), 0, 0)
    return HysteresisState(state.signal, direction, days)


def confidence(agg: dict, days_in_band: int, panic: bool) -> dict:
    comps = agg["components"]
    wsum = sum(WEIGHTS.values())
    strength = sum(c["weight"] * abs(c["s_eff"]) for c in comps.values())
    net = abs(sum(c["weight"] * c["s_eff"] for c in comps.values()))
    A = net / strength if strength > 1e-9 else 0.0
    M = min(1.0, (strength / wsum) / 0.5)
    F = sum(c["weight"] * c["freshness"] for c in comps.values()) / wsum
    P = min(1.0, days_in_band / 10)
    C = 100 * F * (0.40 * A + 0.30 * M + 0.30 * P) * (0.6 if panic else 1.0)
    delayed = any(comps[k]["freshness"] == 0.0 for k in CRITICAL)
    if delayed:
        C = min(C, 40.0)
    return {"confidence": int(round(C)), "agreement": r(A), "magnitude": r(M),
            "freshness": r(F), "persistence": r(P), "data_delayed": delayed}


def regime_candidate(agg: dict, panic_trigger: bool, score_change_20: float) -> str:
    if panic_trigger:
        return "PANIC"
    comps = agg["components"]
    wmaj = sum(WEIGHTS[k] for k in MAJOR)
    bull = sum(WEIGHTS[k] for k in MAJOR if comps[k]["s_eff"] > 0.15) / wmaj
    bear = sum(WEIGHTS[k] for k in MAJOR if comps[k]["s_eff"] < -0.15) / wmaj
    score = agg["score"]
    if bull >= 0.6 and score >= 55 and score_change_20 > -12:
        return "GOLD_BULL"
    if bear >= 0.6 and score <= 45 and score_change_20 < 12:
        return "GOLD_BEAR"
    return "TRANSITION"


def panic_trigger(vix, vix_chg_5d_pct, gold_1d_pct, gold_5d_pct, dxy_1d_pct) -> bool:
    return (vix >= 35
            or (vix >= 25 and vix_chg_5d_pct >= 50)
            or abs(gold_1d_pct) >= 4
            or (gold_5d_pct <= -6 and vix >= 25)
            or dxy_1d_pct >= 1.5)


# --------------------------------------------------------------------------
# Turkish gram gold
# --------------------------------------------------------------------------
TROY_OZ_GRAMS = 31.1034768


def gram_gold_try(xauusd: float, usdtry: float) -> float:
    return xauusd / TROY_OZ_GRAMS * usdtry


def usdtry_excess(log_chg_pct: float, days: float, i_try_pct: float, i_usd_pct: float) -> float:
    """USD/TRY move in excess of the TRY-USD interest carry over the same period."""
    return log_chg_pct - (i_try_pct - i_usd_pct) * days / 365


def fx_leg(x1, x7, x30) -> float:
    return r(trend((x1, x7, x30), (0.5, 1.2, 2.5), H3, +1))


FX_TILT_MAX = 25.0  # USD/TRY leg can move the gram score by at most +/-25 points


def gram_score(global_score: float, s_fx: float, f_fx: float) -> float:
    """Additive tilt (not a weighted average): a neutral FX leg leaves the
    global score untouched instead of diluting it toward 50."""
    return round(min(100.0, max(0.0, global_score + FX_TILT_MAX * f_fx * s_fx)), 1)


def gram_confidence(global_conf: int, global_score: float, s_fx: float, f_fx: float) -> int:
    g_dir = 0 if abs(global_score - 50) < 5 else (1 if global_score > 50 else -1)
    fx_dir = 0 if abs(s_fx) < 0.15 else (1 if s_fx > 0 else -1)
    agree = 0.0 if g_dir * fx_dir < 0 else 1.0
    return int(round(global_conf * (0.7 + 0.3 * agree) * f_fx))


# --------------------------------------------------------------------------
# Worked example (illustrative mock market, evaluated 2026-10-02 23:30 UTC)
# --------------------------------------------------------------------------
EXAMPLE_EVAL = "2026-10-02T23:30:00+00:00"


def _age(release_iso: str) -> float:
    from datetime import datetime
    delta = datetime.fromisoformat(EXAMPLE_EVAL) - datetime.fromisoformat(release_iso)
    return delta.total_seconds() / 86400


EXAMPLE_RELEASES = [  # release times in UTC (08:30 / 10:00 New York)
    Release("NFP", _age("2026-10-02T12:30:00+00:00"), 30.0, 100.0),
    Release("UNEMPLOYMENT", _age("2026-10-02T12:30:00+00:00"), 4.4, 4.3),
    Release("INITIAL_CLAIMS", _age("2026-10-01T12:30:00+00:00"), 241.0, 228.0),
    Release("ISM_MFG", _age("2026-10-01T14:00:00+00:00"), 48.9, 49.6),
    Release("CORE_PCE_MOM", _age("2026-09-25T12:30:00+00:00"), 0.2, 0.2),
    Release("PCE_YOY", _age("2026-09-25T12:30:00+00:00"), 2.7, 2.7),
    Release("INITIAL_CLAIMS", _age("2026-09-24T12:30:00+00:00"), 226.0, 232.0),
    Release("CPI_YOY", _age("2026-09-11T12:30:00+00:00"), 3.0, 2.9),
    Release("CORE_CPI_MOM", _age("2026-09-11T12:30:00+00:00"), 0.3, 0.3),
]


def run_example() -> dict:
    out = {}
    out["REAL_YIELD"] = real_yield(-3, -11, -28)
    # P = mean(implied 6M, implied 12M); policy target 3.50-3.75 -> mid 3.625
    out["FED"] = fed(-2, -9, -21, implied_12m=3.18, policy_mid=3.625)
    out["DXY"] = dxy(-0.22, -0.85, -1.70)
    # nominal d1/d7/d30 = -2/-7/-16bp, real = -3/-11/-28bp -> breakeven = +1/+4/+12bp
    out["NOMINAL_10Y"] = nominal_10y(1, 4, 12, level=4.45, mean_252=4.15, std_252=0.14)
    out["ECON"] = econ(EXAMPLE_RELEASES)
    out["ETF"] = etf(0.35, 1.6, 2.9)
    out["CENTRAL_BANKS"] = central_banks(780, 165)

    s = {k: v["s"] for k, v in out.items()}
    ages = {"REAL_YIELD": 1, "FED": 1, "DXY": 0, "NOMINAL_10Y": 1, "ETF": 1, "CENTRAL_BANKS": 23}
    f = {k: freshness(a, *FRESHNESS[k]) for k, a in ages.items()}
    f["ECON"] = out["ECON"]["freshness"]

    agg = aggregate(s, f)
    trig = panic_trigger(vix=17.8, vix_chg_5d_pct=-4, gold_1d_pct=0.6, gold_5d_pct=1.9, dxy_1d_pct=-0.22)
    conf = confidence(agg, days_in_band=6, panic=trig)
    reg = regime_candidate(agg, trig, score_change_20=+9.5)

    xau, usdtry_ = 4180.50, 49.85
    x = [usdtry_excess(c, d, 31.0, 3.625) for c, d in ((0.05, 1), (0.42, 7), (1.85, 30))]
    s_fx = fx_leg(*x)
    f_fx = freshness(0, *FRESHNESS["USDTRY"])
    g_score = gram_score(agg["score"], s_fx, f_fx)
    g_conf = gram_confidence(conf["confidence"], agg["score"], s_fx, f_fx)

    # Contrast case: bearish global gold, strongly bullish USD/TRY (TRY stress)
    xs = [usdtry_excess(c, d, 31.0, 3.625) for c, d in ((0.9, 1), (3.1, 7), (8.4, 30))]
    s_fx2 = fx_leg(*xs)
    contrast = {"global_score": 31.0, "global_band": band_of(31.0),
                "fx_excess_pct": [round(v, 3) for v in xs], "s_fx": s_fx2,
                "gram_score": gram_score(31.0, s_fx2, 1.0),
                "gram_band": band_of(gram_score(31.0, s_fx2, 1.0))}

    return {"gram_contrast_case": contrast, "components_detail": out, "aggregate": agg, "confidence": conf,
            "panic_trigger": trig, "regime_candidate": reg,
            "gram": {"xauusd": xau, "usdtry": usdtry_,
                     "gram_try": round(gram_gold_try(xau, usdtry_), 2),
                     "fx_excess_pct": [round(v, 3) for v in x], "s_fx": s_fx,
                     "score": g_score, "raw_band": band_of(g_score), "confidence": g_conf}}


def run_hysteresis_demo() -> list[tuple]:
    st = HysteresisState("HOLD")
    rows = []
    for day, score in enumerate([58.0, 61.5, 64.2, 62.8, 63.4, 65.1, 66.0, 71.0, 59.0, 56.5, 47.0], 1):
        st = step_hysteresis(st, score)
        rows.append((day, score, band_of(score), st.signal, st.pending_dir, st.pending_days))
    # decisive move: from HOLD, a single print of 72 (12 points beyond 60) confirms at once
    st2 = step_hysteresis(HysteresisState("HOLD"), 72.0)
    rows.append(("decisive", 72.0, band_of(72.0), st2.signal, st2.pending_dir, st2.pending_days))
    return rows


if __name__ == "__main__":
    import json
    res = run_example()
    print(json.dumps(res, indent=2))
    print("\nHysteresis demo (day, score, raw band, confirmed, pending dir, pending days):")
    for row in run_hysteresis_demo():
        print("  ", row)
