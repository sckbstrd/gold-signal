"""Official evaluations: live (one per US trading day) and historical backfill.

Official rows are append-only: once a date has a stored signal it is never recomputed
(the model may not be quietly re-run over the past). The hysteresis/regime state is
persisted after every run so the next run continues exactly where this one stopped.
"""
from __future__ import annotations

import logging
from dataclasses import asdict
from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import presenters
from app.db import models as m
from app.engine import evaluate
from app.engine.params import ModelParams
from app.engine.result import EngineState, Evaluation, RegimeState, SignalState
from app.pipeline.store import SeriesStore, evaluation_time, trading_days

log = logging.getLogger("gold_signal.evaluate")


# ------------------------------------------------------------------ state (de)serialisation
def _ss_to(s: SignalState) -> dict:
    d = asdict(s)
    d["since"] = s.since.isoformat() if s.since else None
    return d


def _ss_from(d: dict) -> SignalState:
    return SignalState(**{**d, "since": date.fromisoformat(d["since"]) if d.get("since") else None})


def state_to_dict(s: EngineState) -> dict:
    return {"model_version": s.model_version, "global": _ss_to(s.global_), "gram": _ss_to(s.gram),
            "regime": asdict(s.regime), "score_history": list(s.score_history),
            "last_official_date": s.last_official_date.isoformat() if s.last_official_date else None}


def state_from_dict(d: dict) -> EngineState:
    return EngineState(
        model_version=d["model_version"], global_=_ss_from(d["global"]), gram=_ss_from(d["gram"]),
        regime=RegimeState(**d["regime"]), score_history=tuple(d["score_history"]),
        last_official_date=date.fromisoformat(d["last_official_date"]) if d.get("last_official_date") else None)


PRIOR = ":prior"   # state *before* the latest evaluation, used to reproduce it exactly


def load_state(session: Session, params: ModelParams, key_suffix: str = "") -> EngineState | None:
    row = session.get(m.EngineStateRow, params.version + key_suffix)
    return state_from_dict(row.state) if row else None


def save_state(session: Session, state: EngineState, key_suffix: str = "") -> None:
    key = state.model_version + key_suffix
    row = session.get(m.EngineStateRow, key)
    data = state_to_dict(state)
    if row is None:
        session.add(m.EngineStateRow(model_version=key, as_of_date=state.last_official_date, state=data))
    else:
        row.as_of_date, row.state = state.last_official_date, data


# ------------------------------------------------------------------ evaluation runs
def latest_due_date(now: datetime) -> date | None:
    """Most recent trading day whose 23:30 UTC evaluation time has passed."""
    for back in range(0, 10):
        d = (now - timedelta(days=back)).date()
        if d in set(trading_days(d, d)) and evaluation_time(d) <= now:
            return d
    return None


def _store_signal(session: Session, ev: Evaluation, origin: str, now: datetime, payload: dict | None) -> None:
    r = ev.result
    session.add(m.Signal(
        model_version=r.model_version, as_of_date=r.as_of_date, evaluated_at=now, origin=origin,
        score=r.global_.score, raw_band=r.global_.raw_band, signal=r.global_.signal,
        confidence=r.global_.confidence, regime=r.regime, gram_score=r.gram.score, gram_signal=r.gram.signal,
        data_status=r.data_status, inputs_sha256=r.inputs_sha256,
        points={c.code: c.points for c in r.components.values()} |
               {"_missing": [c.code for c in r.components.values() if c.status in ("MISSING", "STALE")]},
        payload=payload))


def run_evaluations(session: Session, store: SeriesStore, params: ModelParams, end: date, origin: str,
                    now: datetime, start: date | None = None) -> Evaluation | None:
    """Evaluate every trading day after the stored state up to ``end`` (inclusive)."""
    state = load_state(session, params) or EngineState(model_version=params.version)
    first = (state.last_official_date + timedelta(days=1)) if state.last_official_date else start
    if first is None or first > end:
        return None
    existing = set(session.execute(select(m.Signal.as_of_date).where(
        m.Signal.model_version == params.version)).scalars())
    days = trading_days(first, end)
    last: Evaluation | None = None
    prior = state
    for i, d in enumerate(days):
        snap = store.snapshot(evaluation_time(d))
        prior = state
        ev = evaluate(snap, state, params, official=True)
        state = ev.state
        if d not in existing:
            _store_signal(session, ev, origin, now, None)
        last = ev
        if i % 500 == 499:
            session.flush()
            log.info("evaluated through %s", d)
    save_state(session, state)
    save_state(session, prior, PRIOR)
    session.commit()
    return last


def latest_signal_row(session: Session, params: ModelParams) -> m.Signal | None:
    return session.execute(select(m.Signal).where(m.Signal.model_version == params.version)
                           .order_by(m.Signal.as_of_date.desc()).limit(1)).scalar_one_or_none()


def reproduce_latest(session: Session, store: SeriesStore, params: ModelParams):
    """Re-run the latest official evaluation from the saved prior state. The engine is
    deterministic, so this reproduces the stored signal exactly (checked via the input hash).
    Returns (evaluation, snapshot, matches_stored) or None."""
    row = latest_signal_row(session, params)
    prior = load_state(session, params, PRIOR)
    if row is None or prior is None:
        return None
    snap = store.snapshot(evaluation_time(row.as_of_date))
    ev = evaluate(snap, prior, params, official=True)
    return ev, snap, ev.result.inputs_sha256 == row.inputs_sha256
