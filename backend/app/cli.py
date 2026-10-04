"""Command line.

  python -m app.cli run [--now ISO] [--previous-state DIR] [--export DIR] [--repo owner/name]
  python -m app.cli serve [--host 0.0.0.0] [--port 8000] [--schedule]
  python -m app.cli report

GS_PROVIDERS=mock runs everything offline on the documented demo data.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import asdict, replace
from datetime import date, datetime, timezone
from pathlib import Path

from app.config import get_settings
from app.db.session import make_engine, make_sessionmaker


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    p = argparse.ArgumentParser(prog="gold-signal")
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="ingest, evaluate due days, render documents")
    r.add_argument("--now", help="evaluation clock (ISO, UTC); default: current time")
    r.add_argument("--previous-state", type=Path, help="folder with a previous run's state/*.json")
    r.add_argument("--export", type=Path, help="write the static site here")
    r.add_argument("--repo", default="sckbstrd/gold-signal")
    r.add_argument("--history-start", type=date.fromisoformat)
    r.add_argument("--no-ingest", action="store_true")
    s = sub.add_parser("serve", help="run the REST API")
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=8000)
    s.add_argument("--schedule", action="store_true", help="refresh data every 15 minutes in-process")
    sub.add_parser("report", help="print the history report")
    args = p.parse_args(argv)

    settings = get_settings()
    if getattr(args, "history_start", None):
        settings = replace(settings, history_start=args.history_start)
    sessions = make_sessionmaker(make_engine(settings.database_url))

    if args.cmd == "run":
        from app.engine import load_params
        from app.pipeline.export import export_site
        from app.pipeline.run import latest_documents, run
        now = datetime.fromisoformat(args.now) if args.now else datetime.now(timezone.utc)
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        with sessions() as session:
            summary = run(session, settings, now, args.previous_state, ingest=not args.no_ingest)
            print(json.dumps(asdict(summary), indent=1, default=str))
            if args.export:
                n = export_site(session, load_params(), latest_documents(session), args.export, args.repo, now)
                print(f"exported {n} documents to {args.export}")
        return 1 if summary.errors and not summary.evaluated_through else 0

    if args.cmd == "serve":
        import uvicorn
        from app.api import create_app
        uvicorn.run(create_app(settings, sessions, schedule=args.schedule), host=args.host, port=args.port)
        return 0

    if args.cmd == "report":
        from app.pipeline.run import latest_documents
        with sessions() as session:
            print(json.dumps(latest_documents(session).get("gold/history/report", {}), indent=1))
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
