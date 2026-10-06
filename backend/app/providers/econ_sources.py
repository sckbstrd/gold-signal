"""US economic releases: consensus, previous and first-print actuals from the FXStreet calendar API
(public JSON used by their calendar page; history since 2007), cross-checked against BLS for the
releases BLS publishes.

Point-in-time rule for the consensus:
  * a release still in the future is stored with ``consensus_captured_at = now`` (captured live;
    refreshed on every run until the release);
  * a release already out when first seen (history backfill, or a week this service missed) keeps the
    calendar's archived pre-release consensus with ``consensus_captured_at = scheduled - 1 day``.
    FXStreet freezes the consensus at release time, so this is the figure the market expected, but
    it was not captured by this service and the pipeline never lets it overwrite a live capture.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from app.providers.base import EventRow, FetchResult, Http

FX_URL = "https://calendar-api.fxstreet.com/en/api/v1/eventDates/{start}/{end}?countries=US"
FX_HISTORY_START = date(2007, 1, 1)
FX_HEADERS = {"Referer": "https://www.fxstreet.com/", "Origin": "https://www.fxstreet.com"}
BLS_URL = "https://api.bls.gov/publicAPI/v1/timeseries/data/"

# FXStreet event ids are stable across renames (e.g. "ISM Non-Manufacturing" -> "ISM Services PMI").
FX_EVENTS = {
    "6f846eaa-9a12-43ab-930d-f059069c6646": "CPI_YOY",          # Consumer Price Index (YoY)
    "4abee304-9984-47cf-80ab-dca1114165f5": "CORE_CPI_MOM",     # Consumer Price Index ex Food & Energy (MoM)
    "f3ea3723-c2de-4332-b7a5-1ba539bea3f4": "PCE_YOY",          # PCE - Price Index (YoY)
    "5d9ff5c8-1e0e-44b8-8d06-4ac39d217bf3": "CORE_PCE_MOM",     # Core PCE - Price Index (MoM)
    "9cdf56fd-99e4-4026-aa99-2b6c0ca92811": "NFP",              # Nonfarm Payrolls (thousands)
    "932c21fa-f664-40e1-a921-dbeb452f0081": "UNEMPLOYMENT",     # Unemployment Rate
    "9c689bbf-af2a-4f65-81a8-c5f5e2b78d70": "INITIAL_CLAIMS",   # Initial Jobless Claims (thousands)
    "2e1d69f3-8273-4096-b01b-8d2034d4fade": "ISM_MFG",          # ISM Manufacturing PMI
    "6c5853c1-a409-4722-bdea-17ad5d8a193f": "ISM_SERVICES",     # ISM Services PMI
}
EVENT_CODES = set(FX_EVENTS.values())
# Releases whose official first print BLS publishes through its public API (cross-check / fallback).
TRACKED = {"CPI_YOY", "CORE_CPI_MOM", "NFP", "UNEMPLOYMENT"}
BLS_SERIES = {"CPI": "CUUR0000SA0", "CORE_CPI_SA": "CUSR0000SA0L1E", "PAYROLLS": "CES0000000001",
              "UNRATE": "LNS14000000"}


def _utc(text: str) -> datetime:
    dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    return (dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)).astimezone(timezone.utc)


def reference_period(code: str, period_iso: str | None, release: datetime) -> str:
    """Monthly releases -> "YYYY-MM" of the month they describe; weekly claims -> week-ending date."""
    if code == "INITIAL_CLAIMS":
        return (_utc(period_iso) if period_iso else release - timedelta(days=6)).date().isoformat()
    if period_iso:
        return _utc(period_iso).strftime("%Y-%m")
    y, m = release.year, release.month - 1           # CPI / jobs report in month M describe month M-1
    return f"{y - 1}-12" if m == 0 else f"{y:04d}-{m:02d}"


def parse_fxstreet(payload: list, now: datetime, source: str) -> list[EventRow]:
    out = []
    for e in payload:
        code = FX_EVENTS.get(e.get("eventId"))
        if code is None or e.get("countryCode") != "US":
            continue
        when = _utc(e["dateUtc"])
        released = when <= now and e.get("actual") is not None
        captured = now if when > now else when - timedelta(days=1)
        out.append(EventRow(
            event_code=code, reference_period=reference_period(code, e.get("periodDateUtc"), when),
            scheduled_at=when, source=source, previous=e.get("previous"), consensus=e.get("consensus"),
            consensus_captured_at=captured if e.get("consensus") is not None else None,
            released_at=when if released else None, actual=e.get("actual") if released else None,
        ))
    return out


class FxStreetCalendarProvider:
    code, name, url = "fxstreet", "FXStreet economic calendar (US releases)", "https://www.fxstreet.com/economic-calendar"

    def fetch(self, http: Http, start: date, end: date, now: datetime) -> FetchResult:
        res = FetchResult()
        cur = max(start, FX_HISTORY_START)
        stop_all = end + timedelta(days=35)                 # the snapshot shows releases 35 days ahead
        while cur <= stop_all:
            stop = min(stop_all, date(cur.year, 12, 31))
            url = FX_URL.format(start=f"{cur.isoformat()}T00:00:00Z", end=f"{stop.isoformat()}T23:59:59Z")
            res.events += parse_fxstreet(http.get(url, headers=FX_HEADERS).json(), now, self.code)
            cur = stop + timedelta(days=1)
        return res


def bls_values(payload: dict) -> dict[str, dict[str, float]]:
    """series id -> {"YYYY-MM": value}"""
    out: dict[str, dict[str, float]] = {}
    for s in payload.get("Results", {}).get("series", []):
        vals = {}
        for p in s.get("data", []):
            if p.get("period", "").startswith("M") and p["period"] != "M13":
                try:
                    vals[f"{p['year']}-{p['period'][1:]}"] = float(p["value"])
                except (ValueError, KeyError):
                    continue
        out[s["seriesID"]] = vals
    return out


def _shift(period: str, months: int) -> str:
    y, m = map(int, period.split("-"))
    k = y * 12 + (m - 1) + months
    return f"{k // 12:04d}-{k % 12 + 1:02d}"


def bls_actual(code: str, period: str, series: dict[str, dict[str, float]]) -> float | None:
    """Headline numbers as reported (rounded the way the release reports them)."""
    try:
        if code == "CPI_YOY":
            s = series[BLS_SERIES["CPI"]]
            return round(100 * (s[period] / s[_shift(period, -12)] - 1), 1)
        if code == "CORE_CPI_MOM":
            s = series[BLS_SERIES["CORE_CPI_SA"]]
            return round(100 * (s[period] / s[_shift(period, -1)] - 1), 1)
        if code == "NFP":
            s = series[BLS_SERIES["PAYROLLS"]]
            return round(s[period] - s[_shift(period, -1)], 0)
        if code == "UNEMPLOYMENT":
            return series[BLS_SERIES["UNRATE"]][period]
    except KeyError:
        return None
    return None


class BlsProvider:
    """Actuals for the given scheduled events; the pipeline passes the events it knows about."""
    code, name, url = "bls", "US Bureau of Labor Statistics public API v1", BLS_URL

    def fetch_actuals(self, http: Http, events: list[EventRow], now: datetime) -> list[EventRow]:
        due = [e for e in events if e.actual is None and e.scheduled_at <= now and e.event_code in TRACKED]
        if not due:
            return []
        years = sorted({int(e.reference_period[:4]) for e in due})
        body = {"seriesid": list(BLS_SERIES.values()), "startyear": str(years[0] - 1), "endyear": str(years[-1])}
        payload = http.post(BLS_URL, json=body).json()
        if payload.get("status") != "REQUEST_SUCCEEDED":
            raise RuntimeError(f"BLS: {payload.get('status')} {payload.get('message')}")
        series = bls_values(payload)
        out = []
        for e in due:
            actual = bls_actual(e.event_code, e.reference_period, series)
            if actual is not None:
                out.append(EventRow(e.event_code, e.reference_period, e.scheduled_at, e.source, e.previous,
                                    e.consensus, e.consensus_captured_at, released_at=e.scheduled_at, actual=actual))
        return out
