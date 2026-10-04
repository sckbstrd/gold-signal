"""fetch -> validate -> upsert. One failing provider never stops the others; failures are
recorded on data_sources and as API_FAILURE issues (and the engine sees the data as aging)."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import models as m
from app.providers.base import EventRow, FetchResult, Http
from app.providers.econ_sources import BlsProvider, TRACKED
from app.validation.rules import Issue, cross_check_spot, validate

log = logging.getLogger("gold_signal.ingest")


@dataclass
class IngestReport:
    rows: dict[str, int] = field(default_factory=dict)
    errors: dict[str, str] = field(default_factory=dict)
    issues: int = 0


def _upsert(session: Session, model, key: dict, values: dict) -> None:
    row = session.execute(select(model).filter_by(**key)).scalar_one_or_none()
    if row is None:
        session.add(model(**key, **values))
    else:
        for k, v in values.items():
            setattr(row, k, v)


def store_observations(session: Session, result: FetchResult, now: datetime) -> tuple[int, list[Issue]]:
    checked, issues = validate(result.observations, now)
    existing = {}
    codes = {c.observation.series_code for c in checked}
    for code in codes:
        for row in session.execute(select(m.MarketData).where(m.MarketData.series_code == code)).scalars():
            existing[(row.series_code, row.observation_date, row.source)] = row
    for c in checked:
        o = c.observation
        row = existing.get((o.series_code, o.observation_date, o.source))
        if row is None:
            session.add(m.MarketData(series_code=o.series_code, observation_date=o.observation_date, value=o.value,
                                     source=o.source, available_at=o.available_at, ingested_at=now,
                                     quality=c.quality))
        else:
            row.value, row.quality = o.value, c.quality
    return len(checked), issues


def store_events(session: Session, events: list[EventRow]) -> int:
    """Consensus may be refreshed until release; the first-print actual is never overwritten."""
    n = 0
    for e in events:
        row = session.execute(select(m.EconomicEvent).filter_by(
            event_code=e.event_code, reference_period=e.reference_period)).scalar_one_or_none()
        if row is None:
            session.add(m.EconomicEvent(
                event_code=e.event_code, reference_period=e.reference_period, scheduled_at=e.scheduled_at,
                released_at=e.released_at, previous=e.previous, consensus=e.consensus,
                consensus_captured_at=e.consensus_captured_at, actual=e.actual, source=e.source))
            n += 1
            continue
        if row.actual is None:
            row.scheduled_at = e.scheduled_at
            if e.previous is not None:
                row.previous = e.previous
            if e.consensus is not None and e.consensus_captured_at is not None:
                row.consensus, row.consensus_captured_at = e.consensus, e.consensus_captured_at
            if e.actual is not None:
                row.actual, row.released_at = e.actual, e.released_at
            n += 1
    return n


def _record_source(session: Session, provider, now: datetime, rows: int, error: str | None) -> None:
    kind = "MOCK" if provider.code == "mock" else "CSV" if provider.code == "csv" else "API"
    values = {"name": provider.name, "kind": kind, "url": provider.url or None, "rows_last_run": rows}
    if error:
        values.update(last_error_at=now, last_error=error[:500])
    else:
        values.update(last_success_at=now, last_error=None)
    _upsert(session, m.DataSource, {"code": provider.code}, values)


def _add_issues(session: Session, issues: list[Issue], now: datetime) -> None:
    for i in issues:
        session.add(m.DataQualityIssue(detected_at=now, source=i.source, series_code=i.series_code,
                                       rule=i.rule, severity=i.severity, details=i.details))


def run_ingest(session: Session, providers: list, http: Http | None, start: date, end: date,
               now: datetime) -> IngestReport:
    report = IngestReport()
    for p in providers:
        try:
            result = p.fetch(http, start, end, now)
            n, issues = store_observations(session, result, now)
            n += store_events(session, [e for e in result.events if e.event_code in TRACKED or p.code == "mock"])
            for q in result.quotes:
                _upsert(session, m.LatestQuote, {"code": q.code},
                        {"value": q.value, "observed_at": q.observed_at, "source": q.source})
            for r in result.etf:
                _upsert(session, m.EtfHolding, {"as_of_date": r.as_of_date},
                        {"tonnes": r.tonnes, "source": r.source, "available_at": r.available_at})
                n += 1
            for r in result.cb:
                _upsert(session, m.CentralBankPurchase, {"period_month": r.period_month},
                        {"net_tonnes": r.net_tonnes, "source": r.source, "available_at": r.available_at})
                n += 1
            _add_issues(session, issues, now)
            report.issues += len(issues)
            report.rows[p.code] = n
            _record_source(session, p, now, n, None)
            session.commit()
            log.info("%s: %d rows, %d issues", p.code, n, len(issues))
        except Exception as e:  # noqa: BLE001 - one source failing must not stop the rest
            session.rollback()
            report.errors[p.code] = str(e)
            _record_source(session, p, now, 0, str(e))
            _add_issues(session, [Issue("API_FAILURE", "CRITICAL", None, p.code, {"error": str(e)[:300]})], now)
            session.commit()
            log.warning("%s failed: %s", p.code, e)

    if http is not None and any(p.code == "ffcal" for p in providers):
        try:
            pending = [EventRow(r.event_code, r.reference_period, r.scheduled_at, r.source, r.previous, r.consensus,
                                r.consensus_captured_at, r.released_at, r.actual)
                       for r in session.execute(select(m.EconomicEvent).where(m.EconomicEvent.actual.is_(None))).scalars()]
            bls = BlsProvider()
            updated = bls.fetch_actuals(http, pending, now)
            report.rows["bls"] = store_events(session, updated)
            _record_source(session, bls, now, len(updated), None)
            session.commit()
        except Exception as e:  # noqa: BLE001
            session.rollback()
            report.errors["bls"] = str(e)
            _record_source(session, BlsProvider(), now, 0, str(e))
            session.commit()

    spot = session.get(m.LatestQuote, "XAUUSD_SPOT")
    fut = session.execute(select(m.MarketData).where(m.MarketData.series_code == "XAUUSD")
                          .order_by(m.MarketData.observation_date.desc()).limit(1)).scalar_one_or_none()
    if spot is not None and fut is not None:
        from app.providers.base import Quote
        cross = cross_check_spot(Quote(spot.code, spot.value, spot.observed_at, spot.source), fut.value)
        _add_issues(session, cross, now)
        report.issues += len(cross)
        session.commit()
    return report
