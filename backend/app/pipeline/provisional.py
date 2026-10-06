"""Intraday (provisional) view.

Between official evaluations, live quotes are laid over the daily series and the engine is
run with ``official=False``: the score moves, but the confirmed signal, hysteresis and regime
state never change (spec: one official signal per US trading day).

Only instruments with a free intraday quote move: DXY (a model input), gold and USD/TRY
(prices, gram gold, panic check) and VIX (panic check). Treasury yields and the bill curve
publish end-of-day only, so those components keep the last official close.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from typing import Any

from app.engine import evaluate
from app.engine.params import ModelParams
from app.engine.result import EngineState
from app.engine.snapshot import MarketSnapshot, Obs, Series

# snapshot field -> latest-quote code (see providers: YahooProvider quotes, GoldApiProvider)
OVERLAY = {"dxy": "DXY_LIVE", "gold": "XAUUSD_LIVE", "usdtry": "USDTRY_LIVE", "vix": "VIX_LIVE"}
MAX_QUOTE_AGE = timedelta(days=3)
OPEN_IF_WITHIN = timedelta(minutes=45)


def overlay_quotes(snap: MarketSnapshot, quotes: dict[str, tuple[float, datetime]], now: datetime) -> tuple[MarketSnapshot, list[str]]:
    """Return a snapshot whose last observation per instrument is the live quote, and the list
    of instruments that were moved. Quotes older than MAX_QUOTE_AGE are ignored."""
    changes, moved = {}, []
    for attr, code in OVERLAY.items():
        q = quotes.get(code)
        series: Series = getattr(snap, attr)
        if q is None or series.last is None:
            continue
        value, observed = q
        if now - observed > MAX_QUOTE_AGE or observed.date() < series.last.date:
            continue
        d = observed.astimezone(timezone.utc).date()
        if d.weekday() >= 5:                       # weekend tick belongs to Friday's session
            continue
        obs = list(series.obs)
        if obs[-1].date == d:
            obs[-1] = Obs(d, value)
        else:
            obs.append(Obs(d, value))
        changes[attr] = replace(series, obs=tuple(obs))
        moved.append(attr.upper() if attr != "gold" else "XAUUSD")
    return replace(snap, as_of=now, **changes), moved


def provisional_document(snap: MarketSnapshot, state: EngineState, params: ModelParams,
                         quotes: dict[str, tuple[float, datetime]], official: dict[str, Any] | None,
                         now: datetime) -> tuple[dict[str, Any], MarketSnapshot]:
    live, moved = overlay_quotes(snap, quotes, now)
    r = evaluate(live, state, params, official=False).result
    newest = max((t for _, t in quotes.values()), default=None)
    g = official.get("global", {}) if official else {}
    doc = {
        "as_of": now.isoformat(),
        "quotes_as_of": newest.isoformat() if newest else None,
        "market_open": bool(newest and now - newest <= OPEN_IF_WITHIN),
        "moved_inputs": moved,
        "score": r.global_.score,
        "raw_band": r.global_.raw_band,
        "gram_score": r.gram.score,
        "gram_raw_band": r.gram.raw_band,
        "regime_candidate": r.regime_candidate,
        "panic_trigger": r.panic_trigger.get("triggered", False),
        "components": [{"code": c.code, "points": c.points, "s": c.s, "status": c.status}
                       for c in r.components.values()],
        "official": {"as_of_date": official.get("as_of_date") if official else None,
                     "score": g.get("score"), "signal": g.get("signal"),
                     "gram_signal": official.get("gram_try", {}).get("signal") if official else None,
                     "next_official_evaluation": official.get("next_official_evaluation") if official else None},
        "model_version": params.version,
    }
    return doc, live
