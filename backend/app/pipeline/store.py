"""Point-in-time snapshot builder.

All rows are loaded once; ``snapshot(t)`` then returns exactly what was public at t
(``available_at <= t``), so a historical backfill and a live evaluation go through the
same code. Only the most recent ``depth`` observations per series are handed to the
engine (it needs at most 252 + a 90-day horizon).
"""
from __future__ import annotations

import bisect
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import models as m
from app.engine import calendars
from app.engine.snapshot import CbMonth, MarketSnapshot, Obs, Release, Series
from app.providers.base import SERIES

FIELD_FOR = {
    "US_REAL_10Y": "real_10y", "US_NOM_10Y": "nominal_10y", "DXY": "dxy", "US_TBILL_3M": "tbill_3m",
    "US_TBILL_6M": "tbill_6m", "US_TBILL_1Y": "tbill_1y", "FED_TARGET_LOWER": "fed_lower",
    "FED_TARGET_UPPER": "fed_upper", "EFFR": "effr", "VIX": "vix", "XAUUSD": "gold", "USDTRY": "usdtry",
    "TCMB_POLICY_RATE": "try_policy_rate", "ETF_HOLDINGS_T": "etf_holdings",
}


@dataclass
class _Column:
    dates: list
    values: list
    available: list


class SeriesStore:
    def __init__(self, columns: dict[str, _Column], releases: list[Release], cb: list[CbMonth],
                 econ_start: datetime | None, sources: dict[str, str]):
        self.columns = columns
        self.releases = sorted(releases, key=lambda r: r.scheduled_at)
        self._release_times = [r.scheduled_at for r in self.releases]
        self.cb = sorted(cb, key=lambda c: c.period)
        self.econ_start = econ_start
        self.sources = sources

    @classmethod
    def load(cls, session: Session) -> "SeriesStore":
        rows: dict[str, dict] = {}
        sources: dict[str, str] = {}
        q = select(m.MarketData).where(m.MarketData.quality == "OK").order_by(m.MarketData.observation_date)
        for r in session.execute(q).scalars():
            rows.setdefault(r.series_code, {})[r.observation_date] = (r.value, r.available_at)
            sources[r.series_code] = r.source
        for r in session.execute(select(m.EtfHolding).order_by(m.EtfHolding.as_of_date)).scalars():
            rows.setdefault("ETF_HOLDINGS_T", {})[r.as_of_date] = (r.tonnes, r.available_at)
            sources["ETF_HOLDINGS_T"] = r.source
        columns = {}
        for code, by_date in rows.items():
            ds = sorted(by_date)
            avail = [by_date[d][1] for d in ds]
            # Availability must not go backwards in time for bisect; enforce monotonic (conservative).
            for i in range(1, len(avail)):
                if avail[i] < avail[i - 1]:
                    avail[i] = avail[i - 1]
            columns[code] = _Column(ds, [by_date[d][0] for d in ds], avail)
        releases, captured = [], []
        for e in session.execute(select(m.EconomicEvent)).scalars():
            releases.append(Release(e.event_code, e.reference_period, e.scheduled_at, e.released_at, e.previous,
                                    e.consensus, e.actual, e.consensus_captured_at))
            if e.consensus_captured_at is not None:
                captured.append(e.consensus_captured_at)
        cb = [CbMonth(r.period_month, r.net_tonnes, r.available_at)
              for r in session.execute(select(m.CentralBankPurchase)).scalars()]
        return cls(columns, releases, cb, min(captured) if captured else None, sources)

    def first_date(self, code: str):
        col = self.columns.get(code)
        return col.dates[0] if col and col.dates else None

    def last_date(self, code: str):
        col = self.columns.get(code)
        return col.dates[-1] if col and col.dates else None

    def snapshot(self, as_of: datetime, depth: int = 420) -> MarketSnapshot:
        fields = {}
        for code, attr in FIELD_FOR.items():
            col = self.columns.get(code)
            if col is None:
                continue
            k = bisect.bisect_right(col.available, as_of)
            lo = max(0, k - depth)
            fields[attr] = Series(code, SERIES[code].calendar,
                                  tuple(Obs(d, v) for d, v in zip(col.dates[lo:k], col.values[lo:k])))
        lo = bisect.bisect_left(self._release_times, as_of - timedelta(days=75))
        hi = bisect.bisect_right(self._release_times, as_of + timedelta(days=35))
        cb = tuple(c for c in self.cb if c.available_at <= as_of)[-24:]
        covered = self.econ_start is not None and as_of >= self.econ_start
        return MarketSnapshot(as_of=as_of, releases=tuple(self.releases[lo:hi]), cb_months=cb,
                              econ_covered=covered, **fields)


def evaluation_time(d) -> datetime:
    """The official evaluation for trading day d happens at 23:30 UTC."""
    from datetime import time, timezone
    return datetime.combine(d, time(23, 30), tzinfo=timezone.utc)


def trading_days(start, end) -> list:
    return calendars.business_days(start, end, calendars.NYSE)
