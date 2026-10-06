"""Gold ETF holdings and central-bank gold, from the two free primary sources that publish history.

SPDR Gold Shares (GLD)  daily tonnes in the trust since 2004-11 (historical-archive workbook).
    GLD is the largest physically backed gold ETF (roughly a third of global holdings) and is used as
    the proxy for "combined ETF holdings". Its percentage moves are about twice as volatile as the
    global aggregate, so the ETF component saturates more often than the model's sigmas assume.
IMF International Liquidity (IL)  monthly official gold holdings (fine troy ounces) of all reporting
    countries, since 2004. Net purchases = month-over-month change, in tonnes. These are holdings
    *reported* to the IMF: purchases that the World Gold Council estimates but that are not reported
    (large since 2022) are not included, and some countries disclose accumulated buying in lumps.
"""
from __future__ import annotations

import io
import re
import zipfile
from datetime import date, datetime, time, timedelta, timezone

from app.providers.base import CbRow, EtfRow, FetchResult, Http, SERIES

GLD_URL = "https://api.spdrgoldshares.com/api/v1/historical-archive?product=gld&exchange=NYSE&lang=en"
IMF_URL = ("https://api.imf.org/external/sdmx/2.1/data/IMF.STA,IL/GX010.RGV_REVS.FTO.M"
           "?startPeriod=2004&dimensionAtObservation=AllDimensions")
TROY_OUNCE_G = 31.1034768
_MONTHS = {m: i for i, m in enumerate(("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct",
                                       "Nov", "Dec"), start=1)}


# ------------------------------------------------------------------ SPDR GLD
def _xlsx_rows(data: bytes, sheet_name_contains: str) -> list[dict[str, str]]:
    """Minimal .xlsx reader (stdlib only): rows of {column letter: text} for one worksheet."""
    z = zipfile.ZipFile(io.BytesIO(data))
    shared = re.findall(r"<si>(.*?)</si>", z.read("xl/sharedStrings.xml").decode("utf-8", "ignore"), re.S)
    shared = ["".join(re.findall(r"<t[^>]*>([^<]*)</t>", s)) for s in shared]
    wb = z.read("xl/workbook.xml").decode("utf-8", "ignore")
    rels = z.read("xl/_rels/workbook.xml.rels").decode("utf-8", "ignore")
    sheet = next(m for m in re.finditer(r'<sheet\b[^>]*name="([^"]*)"[^>]*r:id="([^"]+)"', wb)
                 if sheet_name_contains.lower() in m.group(1).lower())
    target = re.search(r'<Relationship\b[^>]*Id="%s"[^>]*Target="([^"]+)"' % re.escape(sheet.group(2)), rels)
    if target is None:                                   # attribute order may differ
        target = re.search(r'<Relationship\b[^>]*Target="([^"]+)"[^>]*Id="%s"' % re.escape(sheet.group(2)), rels)
    path = "xl/" + target.group(1).lstrip("/").removeprefix("xl/")
    xml = z.read(path).decode("utf-8", "ignore")
    rows = []
    for row in re.findall(r"<row\b[^>]*>(.*?)</row>", xml, re.S):
        cells = {}
        for col, attrs, inner in re.findall(r'<c r="([A-Z]+)\d+"([^>]*?)(?:/>|>(.*?)</c>)', row, re.S):
            v = re.search(r"<v>([^<]*)</v>", inner or "")
            if 't="s"' in attrs and v:
                cells[col] = shared[int(v.group(1))]
            elif 't="inlineStr"' in attrs:
                cells[col] = "".join(re.findall(r"<t[^>]*>([^<]*)</t>", inner or ""))
            elif v:
                cells[col] = v.group(1)
        rows.append(cells)
    return rows


def parse_gld_archive(data: bytes, source: str) -> list[EtfRow]:
    rows = _xlsx_rows(data, "Historical Archive")
    header = next(r for r in rows if "Date" in r.values())
    date_col = next(k for k, v in header.items() if v == "Date")
    tonnes_col = next(k for k, v in header.items() if v.strip().lower() == "tonnes of gold")
    spec = SERIES["ETF_HOLDINGS_T"]
    out = []
    for r in rows:
        try:
            dd, mon, yyyy = r.get(date_col, "").split("-")
            d = date(int(yyyy), _MONTHS[mon[:3].title()], int(dd))
            t = float(r[tonnes_col])
        except (ValueError, KeyError):
            continue                                     # header, holidays ("US Holiday"), blanks
        out.append(EtfRow(d, t, spec.available_at(d), source))
    return out


class SpdrGldProvider:
    code, name, url = "spdr", "SPDR Gold Shares daily holdings", "https://www.spdrgoldshares.com/usa/historical-data/"

    def fetch(self, http: Http, start: date, end: date, now: datetime) -> FetchResult:
        rows = parse_gld_archive(http.get(GLD_URL).content, self.code)
        return FetchResult(etf=[r for r in rows if start <= r.as_of_date <= end])


# ------------------------------------------------------------------ IMF official gold holdings
def imf_available_at(period: date, now: datetime | None = None) -> datetime:
    """IMF publishes month M in the second half of M+1 or in M+2; the model treats it as public on
    the 15th of M+2 (conservative). For the most recent months (rule date within the last 45 days,
    or in the future) a row first seen at ``now`` is dated ``max(rule, now)``, so a late IMF release
    can never enter the live record before it was actually seen. Older months keep the rule."""
    y, mo = period.year, period.month + 2
    if mo > 12:
        y, mo = y + 1, mo - 12
    rule = datetime.combine(date(y, mo, 15), time(12, 0), tzinfo=timezone.utc)
    if now is not None and rule > now - timedelta(days=45):
        return max(rule, now)
    return rule


def parse_imf_gold(xml: str, source: str, now: datetime) -> list[CbRow]:
    ounces: dict[date, float] = {}
    for attrs in re.findall(r"<Obs\b([^>]*)/>", xml):
        a = dict(re.findall(r'(\w+)="([^"]*)"', attrs))
        m = re.fullmatch(r"(\d{4})-M(\d{2})", a.get("TIME_PERIOD", ""))
        if m and a.get("OBS_VALUE") not in (None, "", "NaN"):
            ounces[date(int(m.group(1)), int(m.group(2)), 1)] = float(a["OBS_VALUE"])
    months = sorted(ounces)
    out = []
    for prev, cur in zip(months, months[1:]):
        if (cur.year * 12 + cur.month) - (prev.year * 12 + prev.month) != 1:
            continue                                     # gap: no month-over-month change
        net_t = (ounces[cur] - ounces[prev]) * TROY_OUNCE_G / 1_000_000
        out.append(CbRow(cur, round(net_t, 3), imf_available_at(cur, now), source))
    return out


class ImfReservesProvider:
    code, name, url = "imf", "IMF International Liquidity: official gold holdings", "https://data.imf.org"

    def fetch(self, http: Http, start: date, end: date, now: datetime) -> FetchResult:
        return FetchResult(cb=parse_imf_gold(http.get(IMF_URL).text, self.code, now))
