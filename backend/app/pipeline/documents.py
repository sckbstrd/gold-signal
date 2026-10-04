"""Render every API response once per run and store it in the ``documents`` table.

The REST API (app/api.py) and the static site (app/pipeline/export.py) both serve these
documents, so the two delivery paths can never disagree.
"""
from __future__ import annotations

import statistics
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import presenters
from app.db import models as m
from app.engine import calendars
from app.engine.params import ModelParams
from app.pipeline.evaluation import latest_due_date, reproduce_latest
from app.pipeline.store import SeriesStore, evaluation_time, trading_days
from app.providers.base import SERIES

HISTORY_COLUMNS = ["date", "score", "signal", "raw_band", "confidence", "regime", "gram_score",
                   "gram_signal", "origin", "missing"]
INDICATORS = ["REAL_YIELD", "FED", "DXY", "NOMINAL_10Y", "ECON", "ETF", "CENTRAL_BANKS", "GRAM_TRY"]


def _next_official(after: date) -> str:
    d = after + timedelta(days=1)
    while not calendars.is_business_day(d, calendars.NYSE):
        d += timedelta(days=1)
    return evaluation_time(d).isoformat()


def history_rows(session: Session, params: ModelParams) -> list[list]:
    q = select(m.Signal).where(m.Signal.model_version == params.version).order_by(m.Signal.as_of_date)
    return [[s.as_of_date.isoformat(), s.score, s.signal, s.raw_band, s.confidence, s.regime, s.gram_score,
             s.gram_signal, s.origin, (s.points or {}).get("_missing", [])]
            for s in session.execute(q).scalars()]


def history_report(rows: list[list], params: ModelParams) -> dict[str, Any]:
    """Phase 5 sanity report: how often each band/regime occurred and data coverage.
    Descriptive only -- it is never used to tune the model."""
    if not rows:
        return {"model_version": params.version, "days": 0}
    n = len(rows)
    share = lambda c: {k: round(100 * v / n, 1) for k, v in sorted(c.items())}  # noqa: E731
    changes, runs, run = 0, [], 1
    for a, b in zip(rows, rows[1:]):
        if a[2] != b[2]:
            changes += 1
            runs.append(run)
            run = 1
        else:
            run += 1
    runs.append(run)
    missing = Counter(code for r in rows for code in r[9])
    scores = [r[1] for r in rows]
    by_year: dict[str, list] = defaultdict(list)
    for r in rows:
        by_year[r[0][:4]].append(r)
    years = {}
    for y, rs in sorted(by_year.items()):
        ch = sum(1 for a, b in zip(rs, rs[1:]) if a[2] != b[2])
        years[y] = {"days": len(rs), "mean_score": round(statistics.fmean(r[1] for r in rs), 1),
                    "buy_share": round(100 * sum(r[2] in ("BUY", "STRONG_BUY") for r in rs) / len(rs), 1),
                    "sell_share": round(100 * sum(r[2] in ("REDUCE", "SELL") for r in rs) / len(rs), 1),
                    "signal_changes": ch}
    span_years = max((date.fromisoformat(rows[-1][0]) - date.fromisoformat(rows[0][0])).days / 365.25, 1e-9)
    deciles = statistics.quantiles(scores, n=10) if len(scores) >= 10 else [statistics.fmean(scores)] * 9
    return {
        "model_version": params.version, "params_sha256": params.sha256,
        "first_date": rows[0][0], "last_date": rows[-1][0], "days": n,
        "origin_share": share(Counter(r[8] for r in rows)),
        "signal_share": share(Counter(r[2] for r in rows)),
        "raw_band_share": share(Counter(r[3] for r in rows)),
        "regime_share": share(Counter(r[5] for r in rows)),
        "gram_signal_share": share(Counter(r[7] for r in rows)),
        "signal_changes": changes, "changes_per_year": round(changes / span_years, 1),
        "mean_run_days": round(statistics.fmean(runs), 1),
        "score": {"mean": round(statistics.fmean(scores), 1), "p10": round(deciles[0], 1),
                  "p50": round(statistics.median(scores), 1), "p90": round(deciles[-1], 1),
                  "min": min(scores), "max": max(scores)},
        "component_coverage": {c: round(100 * (1 - missing.get(c, 0) / n), 1) for c in params.weights},
        "by_year": years,
        "notes": ["BACKFILL_IS_RECONSTRUCTED"] if any(r[8] == "BACKFILL" for r in rows) else [],
    }


def health(session: Session, store: SeriesStore, now: datetime, data_status: str | None) -> dict[str, Any]:
    series = []
    for code, spec in SERIES.items():
        last = store.last_date(code)
        age = calendars.business_days_between(last, now.date(), spec.calendar) if last else None
        series.append({"code": code, "source": spec.label, "first_observation": _iso(store.first_date(code)),
                       "last_observation": _iso(last), "age_bdays": age,
                       "status": "MISSING" if last is None else "FRESH" if age <= 2 else "AGING" if age < 7 else "STALE"})
    sources = [{"code": s.code, "name": s.name, "kind": s.kind, "last_success_at": _iso(s.last_success_at),
                "last_error_at": _iso(s.last_error_at), "last_error": s.last_error, "rows_last_run": s.rows_last_run}
               for s in session.execute(select(m.DataSource).order_by(m.DataSource.code)).scalars()]
    issues = [{"detected_at": _iso(i.detected_at), "rule": i.rule, "severity": i.severity, "source": i.source,
               "series_code": i.series_code, "details": i.details}
              for i in session.execute(select(m.DataQualityIssue).order_by(m.DataQualityIssue.id.desc())
                                       .limit(40)).scalars()]
    return {"generated_at": now.isoformat(), "data_status": data_status, "sources": sources,
            "series": series, "recent_issues": issues}


def _iso(x) -> str | None:
    return None if x is None else x.isoformat()


def _quotes(session: Session, now: datetime) -> dict[str, tuple]:
    out = {}
    for q in session.execute(select(m.LatestQuote)).scalars():
        if now - q.observed_at <= timedelta(days=4):
            out[q.code] = (q.value, q.observed_at.isoformat(), q.source)
    return out


def build_documents(session: Session, store: SeriesStore, params: ModelParams, now: datetime,
                    source: str) -> dict[str, Any]:
    docs: dict[str, Any] = {}
    rows = history_rows(session, params)
    docs["gold/history"] = {"model_version": params.version, "columns": HISTORY_COLUMNS, "points": rows}
    docs["gold/history/report"] = history_report(rows, params)
    docs["meta/model"] = {"version": params.version, "params_sha256": params.sha256, "params": _plain(params.raw)}

    reproduced = reproduce_latest(session, store, params)
    if reproduced is None:
        docs["health/data"] = health(session, store, now, None)
        return docs
    ev, snap, matches = reproduced
    r = ev.result
    sig = presenters.signal_response(r, _next_official(r.as_of_date))
    if not matches:
        sig["warnings_internal"] = ["REPRODUCTION_HASH_MISMATCH"]
    docs["gold/signal"] = sig
    docs["gold/current"] = presenters.current_response(snap, r, source, _quotes(session, now) if source != "mock" else None)
    docs["gold/indicators"] = presenters.indicators_response(snap, r, source)
    for code in INDICATORS:
        docs[f"gold/indicators/{code}"] = presenters.indicator_detail(code, snap, r, source)
    docs["economic-events"] = presenters.events_response(snap, r, params)
    fed = docs["gold/indicators/FED"]["extra"]
    docs["fed-expectations"] = {"current_policy": fed.get("current_policy"),
                                "market_implied": {**fed.get("market_implied", {}),
                                                   "path_change_bp": docs["gold/indicators/FED"]["changes"]},
                                "history": fed.get("implied_series")}
    docs["health/data"] = health(session, store, now, r.data_status)
    due = latest_due_date(now)
    docs["health/data"]["latest_official_date"] = r.as_of_date.isoformat()
    docs["health/data"]["signal_overdue"] = bool(due and due > r.as_of_date)
    return docs


def _plain(x):
    if hasattr(x, "items"):
        return {k: _plain(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_plain(v) for v in x]
    return x


def save_documents(session: Session, docs: dict[str, Any], now: datetime) -> None:
    for path, body in docs.items():
        row = session.get(m.Document, path)
        if row is None:
            session.add(m.Document(path=path, body=body, generated_at=now))
        else:
            row.body, row.generated_at = body, now
    session.commit()


__all__ = ["build_documents", "save_documents", "history_report", "HISTORY_COLUMNS", "trading_days"]
