"""Provider contract and the series catalog.

A provider turns one external source into normalized rows. Swapping a source means
writing one adapter; the engine, API and app never change.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import date, datetime, time as dtime, timedelta, timezone
from typing import Protocol

import httpx

from app.engine import calendars


@dataclass(frozen=True)
class SeriesSpec:
    code: str
    calendar: str
    lag_days: int                 # publication lag in calendar days after the observation date
    available_utc: dtime          # time of day (UTC) when the value becomes public
    min_value: float
    max_value: float
    spike: float | None           # max plausible 1-observation move (absolute, or relative if spike_relative)
    spike_relative: bool = False
    label: str = ""

    def available_at(self, d: date) -> datetime:
        return datetime.combine(d + timedelta(days=self.lag_days), self.available_utc, tzinfo=timezone.utc)


_22 = dtime(22, 0)
SERIES: dict[str, SeriesSpec] = {s.code: s for s in [
    SeriesSpec("US_REAL_10Y", calendars.US_GOVT, 0, _22, -3, 6, 0.6, label="US Treasury real yield curve"),
    SeriesSpec("US_NOM_10Y", calendars.US_GOVT, 0, _22, 0, 15, 0.6, label="US Treasury par yield curve"),
    SeriesSpec("US_TBILL_3M", calendars.US_GOVT, 0, _22, -1, 15, 0.8, label="US Treasury par yield curve"),
    SeriesSpec("US_TBILL_6M", calendars.US_GOVT, 0, _22, -1, 15, 0.8, label="US Treasury par yield curve"),
    SeriesSpec("US_TBILL_1Y", calendars.US_GOVT, 0, _22, -1, 15, 0.8, label="US Treasury par yield curve"),
    SeriesSpec("FED_TARGET_LOWER", calendars.US_GOVT, 1, dtime(13, 0), 0, 20, None, label="NY Fed reference rates"),
    SeriesSpec("FED_TARGET_UPPER", calendars.US_GOVT, 1, dtime(13, 0), 0, 20, None, label="NY Fed reference rates"),
    SeriesSpec("EFFR", calendars.US_GOVT, 1, dtime(13, 0), 0, 20, None, label="NY Fed reference rates"),
    SeriesSpec("DXY", calendars.FX, 0, dtime(22, 15), 70, 130, 0.04, True, label="ICE US Dollar Index via Yahoo"),
    SeriesSpec("VIX", calendars.NYSE, 0, dtime(22, 15), 5, 150, None, label="Cboe VIX via Yahoo"),
    SeriesSpec("XAUUSD", calendars.FX, 0, dtime(22, 15), 200, 20000, 0.09, True, label="COMEX gold futures (GC=F) via Yahoo"),
    SeriesSpec("USDTRY", calendars.FX, 0, dtime(16, 0), 0.5, 500, 0.30, True, label="ECB reference rate via Frankfurter"),
    SeriesSpec("TCMB_POLICY_RATE", calendars.FX, 0, dtime(11, 0), 0, 100, None, label="TCMB one-week repo"),
    SeriesSpec("ETF_HOLDINGS_T", calendars.NYSE, 1, dtime(12, 0), 0, 10000, 0.2, True, label="SPDR Gold Shares (GLD) holdings"),
]}


@dataclass(frozen=True)
class Observation:
    series_code: str
    observation_date: date
    value: float
    source: str
    available_at: datetime


@dataclass(frozen=True)
class EventRow:
    event_code: str
    reference_period: str
    scheduled_at: datetime
    source: str
    previous: float | None = None
    consensus: float | None = None
    consensus_captured_at: datetime | None = None
    released_at: datetime | None = None
    actual: float | None = None


@dataclass(frozen=True)
class Quote:
    """Latest intraday quote, for display only (never a model input)."""
    code: str
    value: float
    observed_at: datetime
    source: str


@dataclass(frozen=True)
class CbRow:
    period_month: date
    net_tonnes: float
    available_at: datetime
    source: str


@dataclass(frozen=True)
class EtfRow:
    as_of_date: date
    tonnes: float
    available_at: datetime
    source: str


@dataclass
class FetchResult:
    observations: list[Observation] = field(default_factory=list)
    events: list[EventRow] = field(default_factory=list)
    quotes: list[Quote] = field(default_factory=list)
    cb: list[CbRow] = field(default_factory=list)
    etf: list[EtfRow] = field(default_factory=list)


class Provider(Protocol):
    code: str
    name: str
    url: str

    def fetch(self, http: "Http", start: date, end: date, now: datetime) -> FetchResult: ...


def obs(code: str, d: date, value: float, source: str) -> Observation:
    return Observation(code, d, float(value), source, SERIES[code].available_at(d))


class Http:
    """Small httpx wrapper: user agent, timeout, 3 retries with exponential backoff."""

    def __init__(self, timeout: float = 30.0, user_agent: str = "GoldSignal"):
        self.client = httpx.Client(timeout=timeout, follow_redirects=True,
                                   headers={"User-Agent": user_agent, "Accept": "*/*"})

    def get(self, url: str, **kw) -> httpx.Response:
        return self._request("GET", url, **kw)

    def post(self, url: str, **kw) -> httpx.Response:
        return self._request("POST", url, **kw)

    def _request(self, method: str, url: str, **kw) -> httpx.Response:
        last: Exception | None = None
        for attempt in range(3):
            try:
                r = self.client.request(method, url, **kw)
                if r.status_code in (429, 500, 502, 503, 504):
                    raise httpx.HTTPStatusError(f"HTTP {r.status_code}", request=r.request, response=r)
                r.raise_for_status()
                return r
            except (httpx.HTTPError, httpx.TransportError) as e:
                last = e
                time.sleep(1.5 * 2 ** attempt)
        raise RuntimeError(f"{method} {url} failed after 3 attempts: {last}")

    def close(self) -> None:
        self.client.close()
