"""Phase 3/5 pipeline on mock data: validation, point-in-time store, append-only history,
state carry-over between runs, documents and the REST API."""
from __future__ import annotations

import json
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api import create_app
from app.config import Settings
from app.db import models as m
from app.db.session import make_engine, make_sessionmaker
from app.engine import evaluate, load_params
from app.pipeline.export import export_site, import_state
from app.pipeline.run import latest_documents, run
from app.pipeline.store import SeriesStore, evaluation_time
from app.providers.base import Observation, SERIES
from app.validation.rules import validate

NOW = datetime(2026, 10, 2, 23, 45, tzinfo=timezone.utc)


def _settings(tmp_path, name="db"):
    return Settings(database_url=f"sqlite:///{(tmp_path / f'{name}.sqlite').as_posix()}", providers="mock",
                    history_start=date(2026, 6, 1), import_dir=tmp_path)


@pytest.fixture()
def mock_db(tmp_path):
    settings = _settings(tmp_path)
    sessions = make_sessionmaker(make_engine(settings.database_url))
    with sessions() as s:
        summary = run(s, settings, NOW)
    return settings, sessions, summary


# ------------------------------------------------------------------ validation
def _o(code, d, v):
    return Observation(code, d, v, "t", SERIES[code].available_at(d))


def test_validation_range_future_and_spike():
    d0 = date(2026, 9, 1)
    rows = [_o("US_REAL_10Y", d0 + timedelta(days=i), v) for i, v in enumerate([1.8, 1.81, 9.5, 1.82, 1.83])]
    rows.append(_o("US_REAL_10Y", date(2026, 12, 1), 1.8))                               # future
    rows += [_o("DXY", d0, 98.0), _o("DXY", d0 + timedelta(days=1), 150.0)]           # out of range
    rows += [_o("XAUUSD", d0, 4000.0), _o("XAUUSD", d0 + timedelta(days=1), 5200.0),  # one-day spike, reverts
             _o("XAUUSD", d0 + timedelta(days=2), 4010.0)]
    checked, issues = validate(rows, NOW)
    rules = sorted(i.rule for i in issues)
    assert rules == ["RANGE", "RANGE", "SPIKE", "TIMESTAMP"]   # 9.5% real yield is out of range
    q = {(c.observation.series_code, c.observation.value): c.quality for c in checked}
    assert q[("XAUUSD", 5200.0)] == "SUSPECT" and q[("XAUUSD", 4010.0)] == "OK"


def test_real_crashes_are_kept():
    """April 2013: gold fell ~9% and the next day stayed down. Lehman: T-bills collapsed."""
    rows = [_o("XAUUSD", date(2013, 4, 12), 1501.0), _o("XAUUSD", date(2013, 4, 15), 1360.6),
            _o("XAUUSD", date(2013, 4, 16), 1368.0),
            _o("US_TBILL_3M", date(2008, 9, 16), 0.84), _o("US_TBILL_3M", date(2008, 9, 17), 0.03),
            _o("US_TBILL_3M", date(2008, 9, 18), 0.25)]
    checked, issues = validate(rows, NOW)
    assert all(c.quality == "OK" for c in checked) and issues == []


def test_unconfirmed_latest_spike_is_kept_but_logged():
    rows = [_o("XAUUSD", date(2026, 9, 30), 4000.0), _o("XAUUSD", date(2026, 10, 1), 3500.0)]
    checked, issues = validate(rows, NOW)
    assert all(c.quality == "OK" for c in checked)
    assert [(i.rule, i.severity) for i in issues] == [("SPIKE", "INFO")]


def test_genuine_regime_shift_is_not_a_spike():
    d0 = date(2026, 9, 1)
    rows = [_o("XAUUSD", d0, 4000.0), _o("XAUUSD", d0 + timedelta(days=1), 4500.0),
            _o("XAUUSD", d0 + timedelta(days=2), 4520.0)]        # +12.5% and it stays there
    checked, issues = validate(rows, NOW)
    assert all(c.quality == "OK" for c in checked) and issues == []


# ------------------------------------------------------------------ pipeline
def test_pipeline_reproduces_engine_through_the_database(mock_db):
    settings, sessions, summary = mock_db
    assert summary.errors == {}
    assert summary.evaluated_through == "2026-10-02"
    assert summary.live_days == 1 and summary.backfilled_days > 50
    with sessions() as s:
        docs = latest_documents(s)
    comps = {c["code"]: c["points"] for c in docs["gold/signal"]["global"]["components"]}
    assert comps == {"REAL_YIELD": 20.04, "FED": 12.95, "DXY": 9.36, "NOMINAL_10Y": 4.09, "ECON": 5.72,
                     "ETF": 5.83, "CENTRAL_BANKS": 3.2}
    assert docs["gold/signal"]["global"]["score"] == 61.2
    assert "warnings_internal" not in docs["gold/signal"]
    for path in ["gold/current", "gold/indicators", "gold/indicators/FED", "gold/indicators/GRAM_TRY",
                 "economic-events", "fed-expectations", "gold/history", "gold/history/report", "health/data",
                 "meta/model"]:
        assert path in docs, path


def test_store_is_point_in_time(mock_db):
    _, sessions, _ = mock_db
    with sessions() as s:
        store = SeriesStore.load(s)
    t = evaluation_time(date(2026, 9, 15))
    snap = store.snapshot(t)
    assert snap.real_10y.last.date <= date(2026, 9, 15)
    assert snap.fed_upper.last.date == date(2026, 9, 14)           # NY Fed publishes next morning
    assert all(r.released_at is None or r.released_at <= t for r in snap.visible().releases)
    # and the engine on that snapshot equals the engine on a snapshot truncated by hand
    params = load_params()
    a = evaluate(snap, None, params, official=False).result
    b = evaluate(replace(snap, as_of=t), None, params, official=False).result
    assert a.global_.score == b.global_.score


def test_history_is_append_only_and_runs_are_idempotent(mock_db):
    settings, sessions, _ = mock_db
    with sessions() as s:
        before = [(r.as_of_date, r.score, r.inputs_sha256) for r in s.execute(select(m.Signal)).scalars()]
        again = run(s, settings, NOW + timedelta(minutes=30), ingest=False)
        after = [(r.as_of_date, r.score, r.inputs_sha256) for r in s.execute(select(m.Signal)).scalars()]
    assert again.live_days == 0
    assert before == after


def test_state_carries_over_to_a_fresh_database(mock_db, tmp_path):
    settings, sessions, _ = mock_db
    site = tmp_path / "site"
    with sessions() as s:
        export_site(s, load_params(), latest_documents(s), site, "x/y", NOW)
        original = latest_documents(s)
    assert (site / "api/v1/gold/signal.json").exists() and (site / "state/signals.json").exists()
    assert json.loads((site / "api/v1/gold/signal.json").read_text(encoding="utf-8"))["global"]["score"] == 61.2

    fresh = _settings(tmp_path, "fresh")
    fresh_sessions = make_sessionmaker(make_engine(fresh.database_url))
    with fresh_sessions() as s:
        counts = import_state(s, load_params(), site / "state")
        assert counts["signals"] == len(original["gold/history"]["points"]) and counts["state"] == 1
        assert counts["market_rows"] > 1000
        summary = run(s, fresh, NOW + timedelta(hours=1), ingest=False)
        assert summary.live_days == 0 and summary.backfilled_days == 0      # nothing re-evaluated
        docs = latest_documents(s)
    assert docs["gold/signal"]["global"] == original["gold/signal"]["global"]


def test_api_serves_documents(mock_db):
    settings, sessions, _ = mock_db
    client = TestClient(create_app(settings, sessions))
    assert client.get("/health").json()["status"] == "ok"
    r = client.get("/api/v1/gold/signal")
    assert r.status_code == 200 and r.json()["global"]["score"] == 61.2
    assert client.get("/api/v1/gold/signal.json").json() == r.json()
    assert client.get("/api/v1/gold/indicators/FED.json").json()["code"] == "FED"
    h = client.get("/api/v1/gold/history", params={"from": "2026-09-01"}).json()
    assert h["points"] and all(p[0] >= "2026-09-01" for p in h["points"])
    nf = client.get("/api/v1/nope")
    assert nf.status_code == 404 and nf.headers["content-type"].startswith("application/problem+json")
    assert client.get("/api/v1/backtest").status_code == 501
