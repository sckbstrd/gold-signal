"""Engine result -> API JSON shapes (docs/04_API.md).

Phase 3 wraps these dicts in Pydantic response models; Phase 1 uses them to
generate the Android mock fixtures, so the app is built against real engine output.
"""
from __future__ import annotations

import math
from datetime import date, timedelta
from typing import Any

from app.engine.components.fed import path_series
from app.engine.components.nominal import breakeven_series
from app.engine.result import ComponentResult, SignalBlock, SignalResult
from app.engine.snapshot import MarketSnapshot, Series

DISCLAIMER_CODE = "NOT_FINANCIAL_ADVICE"


def _iso(d: date | None) -> str | None:
    return None if d is None else d.isoformat()


def _pct_change(s: Series, horizon: int) -> float | None:
    """Simple % change for display (the engine itself uses log changes)."""
    last, start = s.last, s.anchor(horizon)
    if last is None or start is None:
        return None
    return round(100 * (last.value / start.value - 1), 2)


def _trend_word(c: ComponentResult) -> str:
    d30 = c.inputs.get("changes", {}).get("d30")
    if d30 is None:
        return "FLAT"
    sub = next((x for x in c.sub_scores if x.get("key") == "d30"), None)
    if sub and sub.get("z") is not None and abs(sub["z"]) < 0.25:
        return "FLAT"
    return "RISING" if d30 > 0 else "FALLING"


def component_summary(c: ComponentResult) -> dict[str, Any]:
    return {"code": c.code, "weight": c.weight, "s": c.s, "freshness": round(c.freshness, 4),
            "points": c.points, "tilt": c.tilt, "impact": c.impact, "status": c.status}


def _block(b: SignalBlock) -> dict[str, Any]:
    return {
        "score": b.score, "raw_band": b.raw_band, "signal": b.signal, "previous_signal": b.previous_signal,
        "signal_since": _iso(b.signal_since), "pending": b.pending, "confidence": b.confidence,
        "confidence_parts": b.confidence_parts, "explanation": b.explanation,
    }


def signal_response(r: SignalResult, next_official: str | None) -> dict[str, Any]:
    g = _block(r.global_)
    g.update({"regime": r.regime, "regime_pending": r.regime_pending,
              "components": [component_summary(c) for c in r.components.values()]})
    gram = _block(r.gram)
    gram.update({"global_score": r.gram_detail["global_score"],
                 "fx_leg": {k: v for k, v in r.gram_detail["fx_leg"].items() if k != "sub_scores"}})
    return {
        "model_version": r.model_version, "params_sha256": r.params_sha256, "inputs_sha256": r.inputs_sha256,
        "evaluated_at": r.as_of, "as_of_date": _iso(r.as_of_date), "is_official": r.is_official,
        "next_official_evaluation": next_official, "data_status": r.data_status,
        "global": g, "gram_try": gram, "disclaimer_code": DISCLAIMER_CODE,
    }


SOURCE_LABELS = {
    "REAL_YIELD": "US Treasury", "FED": "US Treasury · NY Fed", "DXY": "ICE via Yahoo",
    "NOMINAL_10Y": "US Treasury", "ECON": "BLS · ForexFactory", "ETF": "CSV import",
    "CENTRAL_BANKS": "CSV import", "GRAM_TRY": "COMEX · ECB · TCMB",
}


def _label(code: str, source: str) -> str:
    return "mock" if source == "mock" else SOURCE_LABELS.get(code, source)


def current_response(snap: MarketSnapshot, r: SignalResult, source: str,
                     quotes: dict[str, Any] | None = None) -> dict[str, Any]:
    """quotes: optional latest intraday quotes {"XAUUSD_SPOT": (value, iso_time, source), "USDTRY_LIVE": ...}.
    Headline price and gram gold use the spot quote when available; changes, 52-week high and charts
    always come from the daily closes the model uses."""
    gold, fx = snap.gold, snap.usdtry
    quotes = quotes or {}
    year = [o for o in gold.obs if o.date > gold.last.date - timedelta(days=365)]
    high = max(year, key=lambda o: o.value)
    gram_changes = {}
    for h in (1, 7, 30):
        g, f = gold.change(h, "logpct"), fx.change(h, "logpct")
        gram_changes[f"d{h}"] = None if g is None or f is None else round(100 * (math.exp((g.delta + f.delta) / 100) - 1), 2)
    stamp = r.as_of
    spot = quotes.get("XAUUSD_SPOT")
    fx_live = quotes.get("USDTRY_LIVE")
    price, price_time, price_src = (spot if spot else (gold.last.value, stamp, source))
    rate, rate_time, rate_src = (fx_live if fx_live else (fx.last.value, stamp, source))
    status = "MOCK" if source == "mock" else "FRESH"
    return {
        "as_of": stamp,
        "gold": {
            "symbol": "XAUUSD", "price_usd": round(price, 2), "observed_at": price_time,
            "change_pct": {f"d{h}": _pct_change(gold, h) for h in (1, 7, 30)},
            "high_52w": round(high.value, 2), "high_52w_date": high.date.isoformat(),
            "distance_from_high_pct": round(100 * (price / high.value - 1), 2),
            "futures_ref": None if source == "mock" else round(gold.last.value, 2),
            "status": status, "source": "mock" if source == "mock" else price_src,
            "series": [[o.date.isoformat(), round(o.value, 2)] for o in year],
        },
        "usdtry": {
            "rate": round(rate, 4), "observed_at": rate_time,
            "change_pct": {f"d{h}": _pct_change(fx, h) for h in (1, 7, 30)},
            "status": status, "source": "mock" if source == "mock" else rate_src,
        },
        "gram_gold": {
            "theoretical_try": round(price / 31.1034768 * rate, 2) if (spot or fx_live)
            else r.gram_detail["theoretical_try"],
            "formula": "XAUUSD / 31.1034768 * USDTRY",
            "change_pct": gram_changes,
            "decomposition_30d_pct": {"gold": _pct_change(gold, 30), "usdtry": _pct_change(fx, 30)},
            "market_try": None, "market_premium_pct": None, "market_source": None,
        },
        "data_status": r.data_status,
    }


def _series_points(s: Series, since: date, digits: int = 4) -> list[list]:
    return [[o.date.isoformat(), round(o.value, digits)] for o in s.obs if o.date >= since]


def indicator_detail(code: str, snap: MarketSnapshot, r: SignalResult, source: str) -> dict[str, Any]:
    since = snap.as_of_date - timedelta(days=365)
    if code == "GRAM_TRY":
        fx = r.gram_detail["fx_leg"]
        gram_series = [[o.date.isoformat(), round(o.value / 31.1034768 * snap.usdtry.at_or_before(o.date).value, 2)]
                       for o in snap.gold.obs if o.date >= since and snap.usdtry.at_or_before(o.date)]
        return {
            "code": code, "value": r.gram_detail["theoretical_try"], "unit": "try_per_gram",
            "changes": fx["usdtry_change_pct"], "change_unit": "pct",
            "trend": None, "impact": None,
            "contribution": {"points": fx["tilt_points"], "weight": fx["max_tilt"], "tilt": fx["tilt_points"],
                             "s": fx["s"]},
            "sub_scores": fx.get("sub_scores", []),
            "series": gram_series,
            "observation_date": fx.get("observation_date"), "age_bdays": fx["age_bdays"],
            "status": "MOCK" if source == "mock" else fx["status"], "source": _label("GRAM_TRY", source),
            "extra": {
                "gram": current_response(snap, r, source)["gram_gold"],
                "fx_leg": {k: v for k, v in fx.items() if k != "sub_scores"},
                "gram_signal": _block(r.gram),
            },
        }

    c = r.components[code]
    unit = {"REAL_YIELD": "pct", "FED": "pct", "DXY": "index", "NOMINAL_10Y": "pct",
            "ECON": None, "ETF": "tonnes", "CENTRAL_BANKS": "tonnes"}[code]
    series = {
        "REAL_YIELD": lambda: _series_points(snap.real_10y, since),
        "FED": lambda: _series_points(path_series(snap), since),
        "DXY": lambda: _series_points(snap.dxy, since, 3),
        "NOMINAL_10Y": lambda: _series_points(snap.nominal_10y, since),
        "ECON": lambda: [],
        "ETF": lambda: _series_points(snap.etf_holdings, since, 1),
        "CENTRAL_BANKS": lambda: [],
    }[code]()
    extra: dict[str, Any] = dict(c.extra)
    if code == "NOMINAL_10Y":
        extra["breakeven_series"] = _series_points(breakeven_series(snap), since)
        extra["real_series"] = _series_points(snap.real_10y, since)
    if code == "FED":
        extra["implied_series"] = {
            "r3m": _series_points(snap.tbill_3m, since), "r6m": _series_points(snap.tbill_6m, since),
            "r12m": _series_points(snap.tbill_1y, since),
        }
        extra["current_policy"]["last_decision"] = _last_decision(snap)
    return {
        "code": code, "value": c.inputs.get("value"), "unit": unit,
        "changes": c.inputs.get("changes", {}), "change_unit": c.inputs.get("change_unit"),
        "trend": _trend_word(c), "impact": c.impact,
        "contribution": {"points": c.points, "weight": c.weight, "tilt": c.tilt, "s": c.s,
                         "freshness": round(c.freshness, 4), "s_eff": c.s_eff},
        "sub_scores": c.sub_scores, "series": series,
        "observation_date": c.inputs.get("observation_date"), "age_bdays": c.age_bdays,
        "status": "MOCK" if source == "mock" and c.status == "FRESH" else c.status, "source": _label(code, source),
        "extra": extra,
    }


def _last_decision(snap: MarketSnapshot) -> dict | None:
    obs = snap.fed_upper.obs
    for prev, cur in zip(reversed(obs[:-1]), reversed(obs)):
        if cur.value != prev.value:
            return {"date": cur.date.isoformat(), "change_bp": round((cur.value - prev.value) * 100)}
    return None


def indicators_response(snap: MarketSnapshot, r: SignalResult, source: str) -> dict[str, Any]:
    items = []
    for code, c in r.components.items():
        items.append({
            "code": code, "value": c.inputs.get("value"), "changes": c.inputs.get("changes", {}),
            "change_unit": c.inputs.get("change_unit"), "trend": _trend_word(c), "impact": c.impact,
            "points": c.points, "weight": c.weight, "tilt": c.tilt,
            "observation_date": c.inputs.get("observation_date"), "age_bdays": c.age_bdays,
            "status": "MOCK" if source == "mock" and c.status == "FRESH" else c.status, "source": _label(code, source),
        })
    return {"as_of": r.as_of, "indicators": items}


def events_response(snap: MarketSnapshot, r: SignalResult, params) -> dict[str, Any]:
    spec = params.component("ECON")["events"]
    scored = {(e["code"], e["reference_period"]): e for e in r.components["ECON"].extra["events"]}
    delayed = {(d["code"], d["reference_period"]) for d in r.components["ECON"].extra["delayed"]}
    out = []
    for i, rel in enumerate(sorted(snap.releases, key=lambda x: x.scheduled_at, reverse=True), start=800):
        visible = rel.released_at is not None and rel.released_at <= snap.as_of
        e = scored.get((rel.code, rel.reference_period))
        sp = spec.get(rel.code, {})
        status = ("RELEASED" if visible else "DELAYED" if (rel.code, rel.reference_period) in delayed
                  else "SCHEDULED")
        impact = e["impact"] if e else None
        out.append({
            "id": i, "code": rel.code, "reference_period": rel.reference_period,
            "scheduled_at": rel.scheduled_at.isoformat(),
            "released_at": rel.released_at.isoformat() if visible else None, "status": status,
            "previous": rel.previous, "consensus": rel.consensus,
            "actual": rel.actual if visible else None,
            "surprise": e["surprise"] if e else None, "surprise_z": e["surprise_z"] if e else None,
            "gold_direction": sp.get("direction"), "importance": sp.get("importance"),
            "impact": impact,
            "impact_label": None if impact is None else
            ("BULLISH" if impact >= 0.05 else "BEARISH" if impact <= -0.05 else "NEUTRAL"),
        })
    return {"events": out}
