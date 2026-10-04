"""US economic releases: consensus from the ForexFactory weekly feed, first-print actuals from BLS.

Only releases where BOTH a consensus and an official actual are freely available are
tracked (CPI y/y, core CPI m/m, nonfarm payrolls, unemployment rate). Tracking a release
whose actual can never arrive would make it look permanently "delayed".

The weekly feed has no history, so consensus is captured going forward: each run stores
this week's forecasts *before* release (consensus_captured_at), and the published
state carries them across runs.
"""
from __future__ import annotations

from datetime import date, datetime, timezone

from app.providers.base import EventRow, FetchResult, Http

FF_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
BLS_URL = "https://api.bls.gov/publicAPI/v1/timeseries/data/"

FF_TITLES = {
    "CPI y/y": "CPI_YOY",
    "Core CPI m/m": "CORE_CPI_MOM",
    "Non-Farm Employment Change": "NFP",
    "Unemployment Rate": "UNEMPLOYMENT",
}
TRACKED = set(FF_TITLES.values())
BLS_SERIES = {"CPI": "CUUR0000SA0", "CORE_CPI_SA": "CUSR0000SA0L1E", "PAYROLLS": "CES0000000001",
              "UNRATE": "LNS14000000"}


def parse_number(text: str | None) -> float | None:
    if text is None:
        return None
    t = text.strip().replace("%", "").replace(",", "")
    if not t:
        return None
    mult = 1.0
    if t[-1] in "KMB":
        mult = {"K": 1.0, "M": 1000.0, "B": 1_000_000.0}[t[-1]]       # payrolls are stored in thousands
        t = t[:-1]
    try:
        return float(t) * mult
    except ValueError:
        return None


def reference_period(release: datetime) -> str:
    """CPI and the jobs report published in month M describe month M-1."""
    y, m = release.year, release.month - 1
    if m == 0:
        y, m = y - 1, 12
    return f"{y:04d}-{m:02d}"


def parse_ff_week(payload: list, captured_at: datetime, source: str) -> list[EventRow]:
    out = []
    for e in payload:
        if e.get("country") != "USD" or e.get("title") not in FF_TITLES:
            continue
        when = datetime.fromisoformat(e["date"]).astimezone(timezone.utc)
        out.append(EventRow(
            event_code=FF_TITLES[e["title"]], reference_period=reference_period(when), scheduled_at=when,
            source=source, previous=parse_number(e.get("previous")), consensus=parse_number(e.get("forecast")),
            consensus_captured_at=captured_at if captured_at < when else None,
        ))
    return out


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


class ForexFactoryCalendarProvider:
    code, name, url = "ffcal", "ForexFactory weekly calendar (consensus)", FF_URL

    def fetch(self, http: Http, start: date, end: date, now: datetime) -> FetchResult:
        return FetchResult(events=parse_ff_week(http.get(FF_URL).json(), now, self.code))


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
