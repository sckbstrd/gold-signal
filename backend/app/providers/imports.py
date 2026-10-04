"""Optional CSV imports for data without a free feed, and the mock provider.

Put files in GS_IMPORT_DIR (default backend/data/imports):

  etf_holdings.csv      date,tonnes[,available_at]            combined physically backed ETF holdings
  central_banks.csv     month,net_tonnes,published            month = YYYY-MM, published = YYYY-MM-DD
  econ_events.csv       code,reference_period,scheduled_at,consensus,actual,previous

Without them the ETF / central-bank components are MISSING (neutral), and the app says so.
"""
from __future__ import annotations

import csv
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

from app.providers.base import CbRow, EtfRow, EventRow, FetchResult, Http, Observation, SERIES


def _dt(text: str) -> datetime:
    dt = datetime.fromisoformat(text.strip())
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


class CsvImportProvider:
    code, name, url = "csv", "Manual CSV imports", ""

    def __init__(self, folder: Path):
        self.folder = folder

    def fetch(self, http: Http | None, start: date, end: date, now: datetime) -> FetchResult:
        res = FetchResult()
        f = self.folder / "etf_holdings.csv"
        if f.exists():
            for r in csv.DictReader(f.open(encoding="utf-8")):
                d = date.fromisoformat(r["date"])
                avail = _dt(r["available_at"]) if r.get("available_at") else SERIES["ETF_HOLDINGS_T"].available_at(d)
                res.etf.append(EtfRow(d, float(r["tonnes"]), avail, self.code))
        f = self.folder / "central_banks.csv"
        if f.exists():
            for r in csv.DictReader(f.open(encoding="utf-8")):
                period = date.fromisoformat(r["month"] + "-01")
                published = datetime.combine(date.fromisoformat(r["published"]), time(12), tzinfo=timezone.utc)
                res.cb.append(CbRow(period, float(r["net_tonnes"]), published, self.code))
        f = self.folder / "econ_events.csv"
        if f.exists():
            for r in csv.DictReader(f.open(encoding="utf-8")):
                sched = _dt(r["scheduled_at"])
                num = lambda k: float(r[k]) if r.get(k) not in (None, "") else None  # noqa: E731
                res.events.append(EventRow(
                    r["code"], r["reference_period"], sched, self.code, previous=num("previous"),
                    consensus=num("consensus"), consensus_captured_at=sched - timedelta(days=1),
                    released_at=sched if num("actual") is not None else None, actual=num("actual")))
        return res


class MockProvider:
    """The documented worked example as rows: deterministic, offline, clearly labelled 'mock'."""
    code, name, url = "mock", "Illustrative demo data (worked example)", ""

    def fetch(self, http: Http | None, start: date, end: date, now: datetime) -> FetchResult:
        from app.demo.worked_example import build_snapshot
        snap = build_snapshot()
        mapping = {"real_10y": "US_REAL_10Y", "nominal_10y": "US_NOM_10Y", "dxy": "DXY", "tbill_3m": "US_TBILL_3M",
                   "tbill_6m": "US_TBILL_6M", "tbill_1y": "US_TBILL_1Y", "fed_lower": "FED_TARGET_LOWER",
                   "fed_upper": "FED_TARGET_UPPER", "effr": "EFFR", "vix": "VIX", "gold": "XAUUSD",
                   "usdtry": "USDTRY", "try_policy_rate": "TCMB_POLICY_RATE"}
        res = FetchResult()
        for attr, code in mapping.items():
            for o in getattr(snap, attr).obs:
                res.observations.append(Observation(code, o.date, o.value, self.code,
                                                    SERIES[code].available_at(o.date)))
        for o in snap.etf_holdings.obs:
            res.etf.append(EtfRow(o.date, o.value, SERIES["ETF_HOLDINGS_T"].available_at(o.date), self.code))
        for m in snap.cb_months:
            res.cb.append(CbRow(m.period, m.net_tonnes, m.available_at, self.code))
        for r in snap.releases:
            res.events.append(EventRow(r.code, r.reference_period, r.scheduled_at, self.code, r.previous,
                                       r.consensus, r.consensus_captured_at, r.released_at, r.actual))
        return res
