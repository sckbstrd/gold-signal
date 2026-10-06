"""Intraday provisional view: moves the score with live quotes, never the official signal."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select

from app.db import models as m
from app.engine import load_params
from app.pipeline.evaluation import load_state, state_to_dict
from app.pipeline.provisional import overlay_quotes, provisional_document
from app.pipeline.run import latest_documents, run
from app.pipeline.store import SeriesStore
from tests.test_pipeline import NOW, mock_db  # noqa: F401  (fixture)

MON = datetime(2026, 10, 5, 15, 0, tzinfo=timezone.utc)


def test_overlay_appends_today_and_replaces_same_day(snapshot):
    last = snapshot.dxy.last
    snap, moved = overlay_quotes(snapshot, {"DXY_LIVE": (99.0, MON)}, MON)
    assert moved == ["DXY"] and snap.dxy.last.date == date(2026, 10, 5) and snap.dxy.last.value == 99.0
    assert snap.dxy.obs[-2] == last                           # Friday's close kept
    same, _ = overlay_quotes(snapshot, {"DXY_LIVE": (98.0, NOW - timedelta(hours=3))}, NOW)
    assert same.dxy.last.date == last.date and same.dxy.last.value == 98.0 and len(same.dxy) == len(snapshot.dxy)


def test_overlay_ignores_stale_and_weekend_quotes(snapshot):
    sat = datetime(2026, 10, 3, 12, 0, tzinfo=timezone.utc)
    _, moved = overlay_quotes(snapshot, {"DXY_LIVE": (99.0, sat)}, sat)
    assert moved == []
    old = datetime(2026, 9, 20, tzinfo=timezone.utc)
    _, moved = overlay_quotes(snapshot, {"DXY_LIVE": (99.0, old)}, MON)
    assert moved == []


def test_dollar_shock_moves_provisional_score_not_the_signal(snapshot, prior, params):
    calm, _ = provisional_document(snapshot, prior, params, {}, None, MON)
    shock, _ = provisional_document(snapshot, prior, params,
                                    {"DXY_LIVE": (snapshot.dxy.last.value * 1.02, MON)}, None, MON)
    assert shock["moved_inputs"] == ["DXY"]
    assert shock["score"] < calm["score"]                     # stronger dollar: bearish for gold
    dxy = {c["code"]: c["points"] for c in shock["components"]}["DXY"]
    assert dxy < {c["code"]: c["points"] for c in calm["components"]}["DXY"]


def test_pipeline_publishes_provisional_without_touching_official(mock_db):  # noqa: F811
    settings, sessions, _ = mock_db
    with sessions() as s:
        before_state = state_to_dict(load_state(s, load_params()))
        before = latest_documents(s)
        s.add(m.LatestQuote(code="DXY_LIVE", value=95.0, observed_at=NOW - timedelta(minutes=10), source="t"))
        s.commit()
        settings_live = type(settings)(**{**settings.__dict__, "providers": "live"})
        run(s, settings_live, NOW, ingest=False)
        after = latest_documents(s)
        after_state = state_to_dict(load_state(s, load_params()))
        signals = s.execute(select(m.Signal)).scalars().all()
    assert after["gold/signal"]["global"] == before["gold/signal"]["global"]   # official untouched
    assert before_state == after_state
    assert len(signals) == len(before["gold/history"]["points"])
    p = after["gold/provisional"]
    assert p["moved_inputs"] == ["DXY"] and p["market_open"] is True
    assert p["official"]["signal"] == before["gold/signal"]["global"]["signal"]
    assert p["score"] != before["gold/signal"]["global"]["score"]


def test_mock_provisional_equals_official(mock_db):  # noqa: F811
    _, sessions, _ = mock_db
    with sessions() as s:
        docs = latest_documents(s)
    p = docs["gold/provisional"]
    assert p["moved_inputs"] == [] and p["market_open"] is False
    assert p["score"] == docs["gold/signal"]["global"]["score"]
