"""End-to-end run: (import previous state) -> ingest -> evaluate due days -> render documents."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.db import models as m
from app.engine import load_params
from app.ingestion.jobs import run_ingest
from app.pipeline.documents import build_documents, save_documents
from app.pipeline.evaluation import latest_due_date, load_state, run_evaluations
from app.pipeline.export import import_state
from app.pipeline.store import SeriesStore, trading_days
from app.providers import build_providers
from app.providers.base import Http

log = logging.getLogger("gold_signal.run")
WARMUP_DAYS = 500


@dataclass
class RunSummary:
    ingested: dict = field(default_factory=dict)
    errors: dict = field(default_factory=dict)
    issues: int = 0
    evaluated_through: str | None = None
    backfilled_days: int = 0
    live_days: int = 0
    documents: int = 0
    imported: dict = field(default_factory=dict)


def run(session: Session, settings: Settings, now: datetime, previous_state: Path | None = None,
        providers: list | None = None, http: Http | None = None, ingest: bool = True) -> RunSummary:
    params = load_params()
    summary = RunSummary()
    if previous_state is not None and previous_state.exists():
        summary.imported = import_state(session, params, previous_state)

    if ingest:
        providers = providers if providers is not None else build_providers(settings)
        last = session.execute(select(func.max(m.MarketData.observation_date))).scalar()
        start = (last - timedelta(days=45)) if last else settings.history_start - timedelta(days=WARMUP_DAYS)
        own_http = http is None and settings.providers != "mock"
        if own_http:
            http = Http(settings.http_timeout, settings.user_agent)
        try:
            rep = run_ingest(session, providers, http, start, now.date(), now)
        finally:
            if own_http:
                http.close()
        summary.ingested, summary.errors, summary.issues = rep.rows, rep.errors, rep.issues

    store = SeriesStore.load(session)
    due = latest_due_date(now)
    if due is None:
        return summary
    state = load_state(session, params)
    if state is None:
        # Bootstrap: reconstruct history point-in-time, then evaluate the latest day live.
        days = trading_days(settings.history_start, due)
        if len(days) > 1:
            run_evaluations(session, store, params, days[-2], "BACKFILL", now, start=settings.history_start)
            summary.backfilled_days = len(days) - 1
        before = session.execute(select(func.count(m.Signal.id))).scalar()
        run_evaluations(session, store, params, due, "LIVE", now, start=due)
    else:
        before = session.execute(select(func.count(m.Signal.id))).scalar()
        run_evaluations(session, store, params, due, "LIVE", now)
    summary.live_days = session.execute(select(func.count(m.Signal.id))).scalar() - before
    summary.evaluated_through = due.isoformat()

    docs = build_documents(session, store, params, now, "mock" if settings.providers == "mock" else "live")
    save_documents(session, docs, now)
    summary.documents = len(docs)
    return summary


def latest_documents(session: Session) -> dict:
    return {d.path: d.body for d in session.execute(select(m.Document)).scalars()}


__all__ = ["run", "RunSummary", "latest_documents", "date"]
