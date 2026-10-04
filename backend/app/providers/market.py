"""Keyless market-data providers.

US Treasury   real 10Y, nominal 10Y and 3M/6M/1Y bills (daily curves, one CSV per year)
NY Fed        Fed target range and EFFR (reference rates API)
Yahoo chart   DXY, VIX, COMEX gold futures (GC=F) daily closes; USD/TRY latest quote
Frankfurter   ECB USD/TRY reference rate
TCMB          one-week repo (policy) rate decisions, forward-filled daily
gold-api.com  latest XAU spot quote (display only)
"""
from __future__ import annotations

import csv
import io
import re
from datetime import date, datetime, timedelta, timezone

from app.engine import calendars
from app.providers.base import FetchResult, Http, Quote, obs

TREASURY_URL = ("https://home.treasury.gov/resource-center/data-chart-center/interest-rates/"
                "daily-treasury-rates.csv/{year}/all?type={kind}&field_tdr_date_value={year}&page&_format=csv")


# ------------------------------------------------------------------ US Treasury
def parse_treasury_csv(text: str, columns: dict[str, str], source: str) -> list:
    """columns: CSV header (case-insensitive) -> series code."""
    reader = csv.DictReader(io.StringIO(text))
    header = {h.strip().lower(): h for h in (reader.fieldnames or [])}
    out = []
    for row in reader:
        d = datetime.strptime(row["Date"].strip(), "%m/%d/%Y").date()
        for col, code in columns.items():
            raw = row.get(header.get(col.lower(), ""), "")
            if raw is None or raw.strip() in ("", "N/A"):
                continue
            out.append(obs(code, d, float(raw), source))
    return out


class TreasuryProvider:
    code, name, url = "treasury", "US Treasury daily yield curves", "https://home.treasury.gov"

    def _year(self, http: Http, year: int) -> list:
        real = http.get(TREASURY_URL.format(year=year, kind="daily_treasury_real_yield_curve")).text
        nom = http.get(TREASURY_URL.format(year=year, kind="daily_treasury_yield_curve")).text
        return (parse_treasury_csv(real, {"10 YR": "US_REAL_10Y"}, self.code) +
                parse_treasury_csv(nom, {"10 Yr": "US_NOM_10Y", "3 Mo": "US_TBILL_3M", "6 Mo": "US_TBILL_6M",
                                         "1 Yr": "US_TBILL_1Y"}, self.code))

    def fetch(self, http: Http, start: date, end: date, now: datetime) -> FetchResult:
        # One CSV per year and ~15-20 s per request: fetch years concurrently (modest parallelism).
        from concurrent.futures import ThreadPoolExecutor
        years = list(range(start.year, end.year + 1))
        with ThreadPoolExecutor(max_workers=min(6, len(years))) as pool:
            chunks = list(pool.map(lambda y: self._year(http, y), years))
        rows = [o for chunk in chunks for o in chunk]
        return FetchResult(observations=[o for o in rows if start <= o.observation_date <= end])


# ------------------------------------------------------------------ NY Fed
def parse_nyfed_effr(payload: dict, source: str) -> list:
    out = []
    for r in payload.get("refRates", []):
        d = date.fromisoformat(r["effectiveDate"])
        lower = r.get("targetRateFrom")
        upper = r.get("targetRateTo", lower)      # single-target era (pre-2008): lower == upper
        if r.get("percentRate") is not None:
            out.append(obs("EFFR", d, r["percentRate"], source))
        if lower is not None:
            out.append(obs("FED_TARGET_LOWER", d, lower, source))
            out.append(obs("FED_TARGET_UPPER", d, upper if upper is not None else lower, source))
    return out


class NyFedProvider:
    code, name, url = "nyfed", "Federal Reserve Bank of New York reference rates", "https://markets.newyorkfed.org"

    def fetch(self, http: Http, start: date, end: date, now: datetime) -> FetchResult:
        res = FetchResult()
        cur = start
        while cur <= end:                         # chunk by 5 years to keep responses small
            stop = min(end, date(cur.year + 4, 12, 31))
            url = (f"https://markets.newyorkfed.org/api/rates/unsecured/effr/search.json"
                   f"?startDate={cur.isoformat()}&endDate={stop.isoformat()}")
            res.observations += parse_nyfed_effr(http.get(url).json(), self.code)
            cur = stop + timedelta(days=1)
        return res


# ------------------------------------------------------------------ Yahoo chart API
def parse_yahoo_chart(payload: dict, code: str, source: str) -> tuple[list, Quote | None]:
    result = payload["chart"]["result"][0]
    meta = result.get("meta", {})
    offset = int(meta.get("gmtoffset", 0))
    closes = result["indicators"]["quote"][0].get("close", [])
    by_date: dict[date, float] = {}
    for ts, close in zip(result.get("timestamp", []) or [], closes):
        if close is None:
            continue
        d = datetime.fromtimestamp(ts + offset, tz=timezone.utc).date()
        if d.weekday() >= 5:                      # futures/FX bars stamped on weekends belong to no session
            continue
        by_date[d] = float(close)                 # last bar of a date wins
    rows = [obs(code, d, v, source) for d, v in sorted(by_date.items())]
    quote = None
    if meta.get("regularMarketPrice") is not None and meta.get("regularMarketTime"):
        quote = Quote(code, float(meta["regularMarketPrice"]),
                      datetime.fromtimestamp(meta["regularMarketTime"], tz=timezone.utc), source)
    return rows, quote


class YahooProvider:
    code, name, url = "yahoo", "Yahoo Finance chart API (unofficial)", "https://finance.yahoo.com"
    SYMBOLS = {"DXY": "DX-Y.NYB", "VIX": "%5EVIX", "XAUUSD": "GC=F"}

    def fetch(self, http: Http, start: date, end: date, now: datetime) -> FetchResult:
        res = FetchResult()
        p1 = int(datetime.combine(start, datetime.min.time(), tzinfo=timezone.utc).timestamp())
        p2 = int(datetime.combine(end + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc).timestamp())
        for code, symbol in self.SYMBOLS.items():
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?period1={p1}&period2={p2}&interval=1d"
            rows, quote = parse_yahoo_chart(http.get(url).json(), code, self.code)
            res.observations += [r for r in rows if start <= r.observation_date <= end]
            if quote:
                res.quotes.append(Quote(f"{code}_LIVE", quote.value, quote.observed_at, self.code))
        fx = http.get("https://query1.finance.yahoo.com/v8/finance/chart/TRY=X?range=5d&interval=1d").json()
        _, q = parse_yahoo_chart(fx, "USDTRY", self.code)
        if q:
            res.quotes.append(Quote("USDTRY_LIVE", q.value, q.observed_at, self.code))
        return res


# ------------------------------------------------------------------ ECB via Frankfurter
def parse_frankfurter(payload: dict, source: str) -> list:
    return [obs("USDTRY", date.fromisoformat(d), v["TRY"], source)
            for d, v in sorted(payload.get("rates", {}).items()) if "TRY" in v]


class FrankfurterProvider:
    code, name, url = "frankfurter", "ECB reference rates via Frankfurter", "https://frankfurter.dev"

    def fetch(self, http: Http, start: date, end: date, now: datetime) -> FetchResult:
        res = FetchResult()
        cur = max(start, date(2005, 1, 3))         # new Turkish lira (TRY) reference rates start 2005
        while cur <= end:
            stop = min(end, date(cur.year + 4, 12, 31))
            url = f"https://api.frankfurter.app/{cur.isoformat()}..{stop.isoformat()}?from=USD&to=TRY"
            res.observations += parse_frankfurter(http.get(url).json(), self.code)
            cur = stop + timedelta(days=1)
        return res


# ------------------------------------------------------------------ TCMB policy rate
TCMB_URL = ("https://www.tcmb.gov.tr/wps/wcm/connect/EN/TCMB+EN/Main+Menu/Core+Functions/Monetary+Policy/"
            "Central+Bank+Interest+Rates/1+Week+Repo")


def parse_tcmb_decisions(html: str) -> list[tuple[date, float]]:
    out = []
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.S):
        cells = [re.sub(r"<[^>]+>|&nbsp;", "", c).strip() for c in re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)]
        if len(cells) >= 3 and re.fullmatch(r"\d{2}\.\d{2}\.\d{4}", cells[0]):
            value = cells[2].replace(",", ".")
            if re.fullmatch(r"\d+(\.\d+)?", value):
                out.append((datetime.strptime(cells[0], "%d.%m.%Y").date(), float(value)))
    return sorted(out)


def forward_fill_daily(decisions: list[tuple[date, float]], start: date, end: date, source: str) -> list:
    """Step series -> one observation per FX business day (the rate in force that day)."""
    out = []
    if not decisions:
        return out
    i, current = 0, None
    for d in calendars.business_days(max(start, decisions[0][0]), end, calendars.FX):
        while i < len(decisions) and decisions[i][0] <= d:
            current = decisions[i][1]
            i += 1
        if current is not None:
            out.append(obs("TCMB_POLICY_RATE", d, current, source))
    return out


class TcmbProvider:
    code, name, url = "tcmb", "Central Bank of the Republic of Türkiye", TCMB_URL

    def fetch(self, http: Http, start: date, end: date, now: datetime) -> FetchResult:
        decisions = parse_tcmb_decisions(http.get(TCMB_URL).text)
        if not decisions:
            raise RuntimeError("TCMB page parsed but no rate decisions found (layout change?)")
        return FetchResult(observations=forward_fill_daily(decisions, start, end, self.code))


# ------------------------------------------------------------------ spot gold quote
class GoldApiProvider:
    code, name, url = "goldapi", "gold-api.com spot quote", "https://gold-api.com"

    def fetch(self, http: Http, start: date, end: date, now: datetime) -> FetchResult:
        j = http.get("https://api.gold-api.com/price/XAU").json()
        observed = datetime.fromisoformat(j["updatedAt"].replace("Z", "+00:00")) if j.get("updatedAt") else now
        return FetchResult(quotes=[Quote("XAUUSD_SPOT", float(j["price"]), observed, self.code)])
