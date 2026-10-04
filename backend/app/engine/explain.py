"""Section 8: explanations as structured reason codes.

Nothing here is free text. Every reason is ``{code, magnitude?, params}`` built
from the actual model inputs; the Android app renders it in EN / TR / RU.
"""
from __future__ import annotations

from typing import Any

from .params import ModelParams
from .primitives import magnitude_word, rnd
from .result import ComponentResult

BULLISH_SIGNALS = ("BUY", "STRONG_BUY")
BEARISH_SIGNALS = ("REDUCE", "SELL")


def reason(code: str, magnitude: str | None = None, **params: Any) -> dict:
    out: dict[str, Any] = {"code": code}
    if magnitude is not None:
        out["magnitude"] = magnitude
    out["params"] = params
    return out


def _r(x: float | None, digits: int) -> float | None:
    return None if x is None else rnd(x, digits)


def _component_reason(c: ComponentResult, direction: int, params: ModelParams) -> dict:
    """direction: +1 bullish, -1 bearish, 0 neutral."""
    mag = magnitude_word(abs(c.s_eff), params["magnitude_words"]) if direction else None
    ch = c.inputs.get("changes", {})
    pick = lambda pos, neg, flat: pos if direction > 0 else neg if direction < 0 else flat  # noqa: E731

    if c.code == "REAL_YIELD":
        return reason(pick("REAL_YIELD_FALLING", "REAL_YIELD_RISING", "REAL_YIELD_FLAT"), mag,
                      value_pct=c.inputs.get("value"), d30_bp=_r(ch.get("d30"), 1), d7_bp=_r(ch.get("d7"), 1))
    if c.code == "FED":
        mi = c.extra.get("market_implied", {})
        return reason(pick("FED_PATH_LOWER", "FED_PATH_HIGHER", "FED_PATH_STABLE"), mag,
                      d30_bp=_r(ch.get("d30"), 1), priced_12m_bp=mi.get("priced_12m_bp"))
    if c.code == "DXY":
        return reason(pick("DXY_FALLING", "DXY_RISING", "DXY_FLAT"), mag,
                      value=c.inputs.get("value"), d30_pct=_r(ch.get("d30"), 2))
    if c.code == "NOMINAL_10Y":
        x = c.extra
        be30 = _r(c.inputs.get("breakeven_changes", {}).get("d30"), 1)
        level_args = {"level_pct": x.get("nominal"), "z_level": _r(x.get("z_level"), 2)}
        level_dominates = abs(x.get("level_part", 0.0)) >= abs(x.get("be_part", 0.0))
        if direction < 0:
            if level_dominates:
                return reason("NOMINAL_LEVEL_ELEVATED", mag, **level_args)
            return reason("BREAKEVENS_FALLING", mag, be_d30_bp=be30)
        if direction > 0:
            if level_dominates:
                return reason("NOMINAL_LEVEL_LOW", mag, **level_args)
            return reason("BREAKEVENS_RISING", mag, be_d30_bp=be30)
        return reason("NOMINAL_NEUTRAL", None, level_pct=x.get("nominal"), be_d30_bp=be30)
    if c.code == "ECON":
        events = c.extra.get("events", [])
        if not events:
            return reason("ECON_QUIET")
        top_pos = max(events, key=lambda e: e["weighted"])
        top_neg = min(events, key=lambda e: e["weighted"])
        ev_args = lambda e: {"event": e["code"], "actual": e["actual"], "consensus": e["consensus"],  # noqa: E731
                             "surprise": e["surprise"]}
        if direction > 0:
            return reason("ECON_DOVISH_SURPRISES", mag, **ev_args(top_pos))
        if direction < 0:
            return reason("ECON_HAWKISH_SURPRISES", mag, **ev_args(top_neg))
        return reason("ECON_MIXED", None,
                      top_positive=top_pos["code"] if top_pos["weighted"] > 0 else None,
                      top_negative=top_neg["code"] if top_neg["weighted"] < 0 else None)
    if c.code == "ETF":
        return reason(pick("ETF_INFLOWS", "ETF_OUTFLOWS", "ETF_STABLE"), mag, d30_pct=_r(ch.get("d30"), 2))
    if c.code == "CENTRAL_BANKS":
        return reason(pick("CB_BUYING_STRONG", "CB_BUYING_WEAK", "CB_BUYING_NORMAL"), mag,
                      t12_tonnes=c.extra.get("t12_tonnes"))
    raise ValueError(c.code)


def data_warnings(components: dict[str, ComponentResult], delayed_releases: list[dict],
                  regime: str) -> list[dict]:
    out = []
    for c in components.values():
        if c.status == "AGING":
            out.append(reason("COMPONENT_AGING", component=c.code, age_bdays=c.age_bdays))
        elif c.status == "STALE":
            out.append(reason("COMPONENT_STALE", component=c.code, age_bdays=c.age_bdays))
        elif c.status == "MISSING":
            out.append(reason("COMPONENT_MISSING", component=c.code))
    for r in delayed_releases:
        out.append(reason("RELEASE_DELAYED", event=r["code"], scheduled=r["scheduled_at"][:10]))
    if regime == "PANIC":
        out.append(reason("PANIC_REGIME"))
    return out


def explain_global(components: dict[str, ComponentResult], signal: str, regime: str,
                   warnings: list[dict], params: ModelParams) -> dict:
    th = params.neutral
    # Missing/stale components are reported only as data warnings, never as "little changed".
    usable = [c for c in components.values() if c.status not in ("MISSING", "STALE")]
    pos = sorted((c for c in usable if c.s_eff >= th), key=lambda c: -c.tilt)
    neg = sorted((c for c in usable if c.s_eff <= -th), key=lambda c: c.tilt)
    neu = sorted((c for c in usable if -th < c.s_eff < th), key=lambda c: -c.weight)

    if regime == "PANIC":
        conclusion = reason("PANIC_CAUTION")
    elif signal in BULLISH_SIGNALS:
        conclusion = (reason("MOST_FAVOR_WITH_RISK", risk=neg[0].code) if neg else reason("MOST_FAVOR"))
    elif signal in BEARISH_SIGNALS:
        conclusion = (reason("MOST_OPPOSE_WITH_SUPPORT", support=pos[0].code) if pos else reason("MOST_OPPOSE"))
    elif pos and neg:
        conclusion = reason("HOLD_MIXED", support=pos[0].code, risk=neg[0].code)
    elif pos or neg:
        conclusion = reason("HOLD_LEANING", direction="POSITIVE" if pos else "NEGATIVE")
    else:
        conclusion = reason("HOLD_QUIET")

    return {
        "headline": reason("WHY_SIGNAL", signal=signal),
        "positive": [_component_reason(c, +1, params) for c in pos],
        "neutral": [_component_reason(c, 0, params) for c in neu],
        "negative": [_component_reason(c, -1, params) for c in neg],
        "warnings": warnings,
        "conclusion": conclusion,
    }


def explain_gram(global_score: float, global_signal: str, gram_signal: str, fx: dict,
                 params: ModelParams) -> dict:
    band = params["gram"]["global_neutral_band"]
    pos, neu, neg, warnings = [], [], [], []
    g_reason = reason("GRAM_GLOBAL_DRIVER", global_signal=global_signal, global_score=global_score)
    g_dir = 0 if abs(global_score - 50) < band else (1 if global_score > 50 else -1)
    (pos if g_dir > 0 else neg if g_dir < 0 else neu).append(g_reason)

    s = fx["s"] * fx["freshness"]
    x_dir = 0 if abs(s) < params.neutral else (1 if s > 0 else -1)
    if fx["status"] == "MISSING":
        warnings.append(reason("COMPONENT_MISSING", component="FX_USDTRY"))
    else:
        fx_args = {"d30_pct": (fx.get("usdtry_change_pct") or {}).get("d30"),
                   "carry_30d_pct": (fx.get("carry_pct") or {}).get("d30"),
                   "excess_30d_pct": (fx.get("excess_pct") or {}).get("d30")}
        mag = magnitude_word(abs(s), params["magnitude_words"]) if x_dir else None
        if x_dir > 0:
            pos.append(reason("GRAM_FX_TRY_WEAKER_THAN_CARRY", mag, **fx_args))
        elif x_dir < 0:
            neg.append(reason("GRAM_FX_TRY_STRONGER_THAN_CARRY", mag, **fx_args))
        else:
            neu.append(reason("GRAM_FX_IN_LINE_WITH_CARRY", None, **fx_args))
        if fx["status"] in ("AGING", "STALE"):
            warnings.append(reason(f"COMPONENT_{fx['status']}", component="FX_USDTRY", age_bdays=fx["age_bdays"]))

    if x_dir == 0:
        conclusion = reason("GRAM_FOLLOWS_GLOBAL")
    elif g_dir == 0:
        conclusion = reason("GRAM_FX_DRIVEN", direction="POSITIVE" if x_dir > 0 else "NEGATIVE")
    elif g_dir == x_dir:
        conclusion = reason("GRAM_DRIVERS_ALIGNED", direction="POSITIVE" if x_dir > 0 else "NEGATIVE")
    else:
        conclusion = reason("GRAM_DRIVERS_OFFSET", fx_direction="POSITIVE" if x_dir > 0 else "NEGATIVE")
    return {
        "headline": reason("WHY_GRAM_SIGNAL", signal=gram_signal),
        "positive": pos, "neutral": neu, "negative": neg, "warnings": warnings,
        "conclusion": conclusion,
    }
