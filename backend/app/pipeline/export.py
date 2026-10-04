"""Static site export + state carry-over between runs.

site/
  index.html                      landing page (APK link, status)
  api/v1/<document>.json          the same documents the REST API serves
  state/engine_state.json         hysteresis/regime state (current + prior)
  state/signals.json              every official signal ever produced (append-only log)
  state/econ_events.json          captured consensus/actuals (consensus has no free history)
"""
from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import models as m
from app.pipeline.evaluation import PRIOR, save_state, state_from_dict, state_to_dict, load_state

SIGNAL_FIELDS = ["as_of_date", "evaluated_at", "origin", "score", "raw_band", "signal", "confidence", "regime",
                 "gram_score", "gram_signal", "data_status", "inputs_sha256", "points"]
EVENT_FIELDS = ["event_code", "reference_period", "scheduled_at", "released_at", "previous", "consensus",
                "consensus_captured_at", "actual", "source"]


def _enc(v):
    return v.isoformat() if isinstance(v, (date, datetime)) else v


def _dt(v):
    return datetime.fromisoformat(v) if v else None


MARKET_FIELDS = ["series_code", "observation_date", "value", "source", "available_at", "quality"]


def export_market_cache(session: Session, folder: Path) -> None:
    """Compressed market history so the next run only fetches recent days (and the free
    sources are not re-downloaded in full every day)."""
    import gzip
    rows = session.execute(select(m.MarketData).order_by(m.MarketData.series_code,
                                                         m.MarketData.observation_date)).scalars()
    payload = {"fields": MARKET_FIELDS, "rows": [[_enc(getattr(r, f)) for f in MARKET_FIELDS] for r in rows],
               "etf": [[_enc(r.as_of_date), r.tonnes, r.source, _enc(r.available_at)]
                       for r in session.execute(select(m.EtfHolding)).scalars()],
               "cb": [[_enc(r.period_month), r.net_tonnes, r.source, _enc(r.available_at)]
                      for r in session.execute(select(m.CentralBankPurchase)).scalars()]}
    with gzip.open(folder / "market.json.gz", "wt", encoding="utf-8") as fh:
        json.dump(payload, fh, separators=(",", ":"))


def import_market_cache(session: Session, folder: Path) -> int:
    import gzip
    f = folder / "market.json.gz"
    if not f.exists() or session.execute(select(m.MarketData.id).limit(1)).first() is not None:
        return 0
    with gzip.open(f, "rt", encoding="utf-8") as fh:
        data = json.load(fh)
    objs = []
    for row in data["rows"]:
        r = dict(zip(data["fields"], row))
        objs.append(m.MarketData(series_code=r["series_code"], observation_date=date.fromisoformat(r["observation_date"]),
                                 value=r["value"], source=r["source"], available_at=_dt(r["available_at"]),
                                 quality=r["quality"]))
    for d, tonnes, source, avail in data.get("etf", []):
        objs.append(m.EtfHolding(as_of_date=date.fromisoformat(d), tonnes=tonnes, source=source,
                                 available_at=_dt(avail)))
    for d, tonnes, source, avail in data.get("cb", []):
        objs.append(m.CentralBankPurchase(period_month=date.fromisoformat(d), net_tonnes=tonnes, source=source,
                                          available_at=_dt(avail)))
    session.add_all(objs)
    session.commit()
    return len(objs)


def export_state(session: Session, params, folder: Path) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    export_market_cache(session, folder)
    cur, prior = load_state(session, params), load_state(session, params, PRIOR)
    (folder / "engine_state.json").write_text(json.dumps({
        "current": state_to_dict(cur) if cur else None, "prior": state_to_dict(prior) if prior else None}),
        encoding="utf-8")
    rows = session.execute(select(m.Signal).where(m.Signal.model_version == params.version)
                           .order_by(m.Signal.as_of_date)).scalars()
    (folder / "signals.json").write_text(json.dumps(
        {"model_version": params.version, "fields": SIGNAL_FIELDS,
         "rows": [[_enc(getattr(r, f)) for f in SIGNAL_FIELDS] for r in rows]}, separators=(",", ":")),
        encoding="utf-8")
    events = session.execute(select(m.EconomicEvent).order_by(m.EconomicEvent.scheduled_at)).scalars()
    (folder / "econ_events.json").write_text(json.dumps(
        {"fields": EVENT_FIELDS, "rows": [[_enc(getattr(e, f)) for f in EVENT_FIELDS] for e in events]}),
        encoding="utf-8")


def import_state(session: Session, params, folder: Path) -> dict[str, int]:
    """Load a previous run's state into an empty database. Existing rows are kept."""
    counts = {"signals": 0, "events": 0, "state": 0, "market_rows": import_market_cache(session, folder)}
    f = folder / "engine_state.json"
    if f.exists():
        data = json.loads(f.read_text(encoding="utf-8"))
        if data.get("current") and data["current"]["model_version"] == params.version and \
                load_state(session, params) is None:
            save_state(session, state_from_dict(data["current"]))
            if data.get("prior"):
                save_state(session, state_from_dict(data["prior"]), PRIOR)
            counts["state"] = 1
    f = folder / "signals.json"
    if f.exists():
        data = json.loads(f.read_text(encoding="utf-8"))
        if data.get("model_version") == params.version:
            have = set(session.execute(select(m.Signal.as_of_date)).scalars())
            for row in data["rows"]:
                r = dict(zip(data["fields"], row))
                d = date.fromisoformat(r["as_of_date"])
                if d in have:
                    continue
                session.add(m.Signal(model_version=params.version, as_of_date=d, evaluated_at=_dt(r["evaluated_at"]),
                                     origin=r["origin"], score=r["score"], raw_band=r["raw_band"], signal=r["signal"],
                                     confidence=r["confidence"], regime=r["regime"], gram_score=r["gram_score"],
                                     gram_signal=r["gram_signal"], data_status=r["data_status"],
                                     inputs_sha256=r["inputs_sha256"], points=r["points"]))
                counts["signals"] += 1
    f = folder / "econ_events.json"
    if f.exists():
        data = json.loads(f.read_text(encoding="utf-8"))
        have = {(e.event_code, e.reference_period) for e in session.execute(select(m.EconomicEvent)).scalars()}
        for row in data["rows"]:
            r = dict(zip(data["fields"], row))
            if (r["event_code"], r["reference_period"]) in have:
                continue
            session.add(m.EconomicEvent(**{**r, "scheduled_at": _dt(r["scheduled_at"]),
                                           "released_at": _dt(r["released_at"]),
                                           "consensus_captured_at": _dt(r["consensus_captured_at"])}))
            counts["events"] += 1
    session.commit()
    return counts


INDEX_HTML = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Gold Signal</title>
<style>body{{font-family:system-ui,sans-serif;margin:0;padding:24px;background:#fbf8f1;color:#1d1b16;max-width:640px}}
a.btn{{display:inline-block;padding:14px 22px;background:#7d5a0c;color:#fff;border-radius:12px;text-decoration:none}}
code{{background:#efe8d8;padding:2px 6px;border-radius:6px}}
@media (prefers-color-scheme:dark){{body{{background:#15140f;color:#e8e2d6}}code{{background:#2c2a25}}}}</style></head>
<body><h1>Gold Signal</h1>
<p>Transparent macro signal for gold and Turkish gram gold. Model v{version}. Analytical tool, not financial advice.</p>
<p>Latest official evaluation: <b>{latest}</b> &middot; score <b>{score}</b> &middot; <b>{signal}</b></p>
<p><a class="btn" href="https://github.com/{repo}/releases/latest">Download the Android app (APK)</a></p>
<p>API: <code>api/v1/gold/signal.json</code>, <code>api/v1/gold/history.json</code>,
<code>api/v1/health/data.json</code>. Generated {generated}.</p></body></html>"""


def export_site(session: Session, params, docs: dict, out: Path, repo: str, now: datetime) -> int:
    api = out / "api" / "v1"
    for path, body in docs.items():
        target = api / f"{path}.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(body, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    export_state(session, params, out / "state")
    sig = docs.get("gold/signal", {}).get("global", {})
    (out / "index.html").write_text(INDEX_HTML.format(
        version=params.version, latest=docs.get("gold/signal", {}).get("as_of_date", "—"),
        score=sig.get("score", "—"), signal=sig.get("signal", "—"), repo=repo, generated=now.isoformat()),
        encoding="utf-8")
    (out / ".nojekyll").write_text("", encoding="utf-8")
    return len(docs)
