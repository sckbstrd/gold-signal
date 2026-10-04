"""Runtime configuration from environment variables (all optional).

GS_DATABASE_URL     SQLAlchemy URL. Default: SQLite file data/gold_signal.db.
                    PostgreSQL: postgresql+psycopg://user:pass@host/db
GS_PROVIDERS        "live" (default) or "mock" (deterministic demo data, no network).
GS_HISTORY_START    First evaluation date for the historical backfill (default 2008-01-02).
GS_IMPORT_DIR       Folder with optional CSV imports (ETF holdings, central banks, events).
GS_HTTP_TIMEOUT     Seconds per HTTP request (default 30).
GS_USER_AGENT       User-Agent sent to data providers.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Settings:
    database_url: str = field(default_factory=lambda: os.environ.get(
        "GS_DATABASE_URL", f"sqlite:///{(BACKEND_DIR / 'data' / 'gold_signal.db').as_posix()}"))
    providers: str = field(default_factory=lambda: os.environ.get("GS_PROVIDERS", "live"))
    history_start: date = field(default_factory=lambda: date.fromisoformat(
        os.environ.get("GS_HISTORY_START", "2008-01-02")))
    import_dir: Path = field(default_factory=lambda: Path(os.environ.get(
        "GS_IMPORT_DIR", str(BACKEND_DIR / "data" / "imports"))))
    http_timeout: float = field(default_factory=lambda: float(os.environ.get("GS_HTTP_TIMEOUT", "30")))
    user_agent: str = field(default_factory=lambda: os.environ.get(
        "GS_USER_AGENT", "GoldSignal/0.3 (+https://github.com/sckbstrd/gold-signal)"))


def get_settings() -> Settings:
    return Settings()
