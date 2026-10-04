"""REST API v1 (docs/04_API.md). Read-only; serves the documents rendered by the pipeline.

Every path also answers with a ".json" suffix, so the app can use either this server or
the static GitHub Pages copy with the same client code.
"""
from __future__ import annotations

import logging
import threading
import time
from datetime import date, datetime, timezone

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import sessionmaker

from app.config import Settings, get_settings
from app.db import models as m
from app.db.session import make_engine, make_sessionmaker

log = logging.getLogger("gold_signal.api")


def problem(status: int, title: str, detail: str) -> JSONResponse:
    return JSONResponse({"type": "about:blank", "title": title, "status": status, "detail": detail},
                        status_code=status, media_type="application/problem+json")


def create_app(settings: Settings | None = None, sessions: sessionmaker | None = None,
               schedule: bool = False) -> FastAPI:
    settings = settings or get_settings()
    sessions = sessions or make_sessionmaker(make_engine(settings.database_url))
    app = FastAPI(title="Gold Signal API", version="1.0.0",
                  description="Transparent macro signal for gold. Analytical tool, not financial advice.",
                  openapi_url="/api/v1/openapi.json", docs_url="/api/v1/docs")
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET"], allow_headers=["*"])

    def doc(path: str):
        with sessions() as s:
            row = s.get(m.Document, path)
            return None if row is None else row.body

    @app.get("/health")
    def liveness():
        return {"status": "ok", "time": datetime.now(timezone.utc).isoformat()}

    @app.get("/api/v1/gold/history")
    @app.get("/api/v1/gold/history.json")
    def history(from_: date | None = Query(None, alias="from"), to: date | None = None):
        body = doc("gold/history")
        if body is None:
            return problem(503, "Not ready", "No evaluations have been run yet.")
        pts = [p for p in body["points"]
               if (from_ is None or p[0] >= from_.isoformat()) and (to is None or p[0] <= to.isoformat())]
        return {**body, "points": pts}

    @app.get("/api/v1/backtest")
    @app.get("/api/v1/backtest.json")
    def backtest():
        return problem(501, "Not implemented", "Backtesting is Phase 6.")

    @app.get("/api/v1/{path:path}")
    def document(path: str):
        path = path.removesuffix(".json").strip("/")
        body = doc(path)
        if body is None:
            return problem(404, "Not found", f"No document at /api/v1/{path}")
        return JSONResponse(body, headers={"Cache-Control": "max-age=60"})

    if schedule:
        threading.Thread(target=_scheduler, args=(settings, sessions), daemon=True).start()
    return app


def _scheduler(settings: Settings, sessions: sessionmaker) -> None:
    """Minimal in-process scheduler: refresh every 15 minutes; the pipeline itself decides
    whether a new official (23:30 UTC) evaluation is due, so repeated runs are idempotent."""
    from app.pipeline.run import run
    while True:
        try:
            with sessions() as s:
                summary = run(s, settings, datetime.now(timezone.utc))
                log.info("scheduled run: %s", summary)
        except Exception:  # noqa: BLE001
            log.exception("scheduled run failed")
        time.sleep(15 * 60)
