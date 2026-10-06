"""Parsers against the real response formats (trimmed samples captured 2026-10-04)."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from app.providers.econ_sources import bls_actual, bls_values, parse_fxstreet, reference_period
from app.providers.etf_cb import imf_available_at, parse_gld_archive, parse_imf_gold
from app.providers.market import (forward_fill_daily, parse_frankfurter, parse_nyfed_effr, parse_tcmb_decisions,
                                  parse_treasury_csv, parse_yahoo_chart)

REAL_CSV = 'Date,"5 YR","7 YR","10 YR","20 YR","30 YR"\n10/02/2026,2.69,2.80,2.92,3.19,3.34\n10/01/2026,2.65,2.76,2.88,3.16,3.31\n'
NOM_CSV = ('Date,"1 Mo","1.5 Month","2 Mo","3 Mo","4 Mo","6 Mo","1 Yr","2 Yr","10 Yr"\n'
           '10/02/2026,4.04,4.09,4.11,4.19,4.26,4.27,4.46,4.83,5.28\n')


def test_treasury_real_and_nominal():
    real = parse_treasury_csv(REAL_CSV, {"10 YR": "US_REAL_10Y"}, "treasury")
    assert [(o.observation_date, o.value) for o in real] == [(date(2026, 10, 2), 2.92), (date(2026, 10, 1), 2.88)]
    assert real[0].available_at == datetime(2026, 10, 2, 22, 0, tzinfo=timezone.utc)
    nom = parse_treasury_csv(NOM_CSV, {"10 Yr": "US_NOM_10Y", "3 Mo": "US_TBILL_3M", "6 Mo": "US_TBILL_6M",
                                       "1 Yr": "US_TBILL_1Y"}, "treasury")
    assert {o.series_code: o.value for o in nom} == {"US_NOM_10Y": 5.28, "US_TBILL_3M": 4.19,
                                                     "US_TBILL_6M": 4.27, "US_TBILL_1Y": 4.46}


def test_nyfed_target_range_and_single_target_era():
    payload = {"refRates": [
        {"effectiveDate": "2026-10-01", "type": "EFFR", "percentRate": 3.88, "targetRateFrom": 3.75, "targetRateTo": 4.00},
        {"effectiveDate": "2006-01-10", "type": "EFFR", "percentRate": 4.24, "targetRateFrom": 4.25},
    ]}
    rows = {(o.series_code, o.observation_date): o for o in parse_nyfed_effr(payload, "nyfed")}
    assert rows[("FED_TARGET_UPPER", date(2026, 10, 1))].value == 4.00
    assert rows[("FED_TARGET_LOWER", date(2006, 1, 10))].value == rows[("FED_TARGET_UPPER", date(2006, 1, 10))].value
    # published the next morning
    assert rows[("EFFR", date(2026, 10, 1))].available_at == datetime(2026, 10, 2, 13, 0, tzinfo=timezone.utc)


def test_yahoo_chart_daily_bars_and_quote():
    payload = {"chart": {"result": [{
        "meta": {"gmtoffset": -14400, "regularMarketPrice": 4141.8, "regularMarketTime": 1791057600},
        "timestamp": [1790740800, 1790827200, 1790913600],      # Wed 30 Sep .. Fri 2 Oct 2026 (NY time)
        "indicators": {"quote": [{"close": [4100.5, None, 4141.8]}]}}]}}
    rows, quote = parse_yahoo_chart(payload, "XAUUSD", "yahoo")
    assert len(rows) == 2 and rows[-1].value == 4141.8
    assert quote is not None and quote.value == 4141.8


def test_frankfurter():
    rows = parse_frankfurter({"rates": {"2026-09-01": {"TRY": 48.274}, "2026-09-02": {"TRY": 48.293}}}, "frankfurter")
    assert [o.value for o in rows] == [48.274, 48.293]


def test_tcmb_table_and_forward_fill():
    html = ("<table><tr><td>DATE</td><td>Borrowing</td><td>Lending</td></tr>"
            "<tr><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td></tr>"
            "<tr class='zebra1'><td>17.04.2013</td><td>-</td><td>5,00</td></tr>"
            "<tr><td>23.01.2026</td><td>-</td><td>37.00</td></tr></table>")
    decisions = parse_tcmb_decisions(html)
    assert decisions == [(date(2013, 4, 17), 5.0), (date(2026, 1, 23), 37.0)]
    filled = forward_fill_daily(decisions, date(2026, 1, 21), date(2026, 1, 27), "tcmb")
    assert [(o.observation_date.day, o.value) for o in filled] == [(21, 5.0), (22, 5.0), (23, 37.0), (26, 37.0), (27, 37.0)]


def test_fxstreet_consensus_capture_rules():
    now = datetime(2026, 10, 1, tzinfo=timezone.utc)
    feed = [
        {"eventId": "9cdf56fd-99e4-4026-aa99-2b6c0ca92811", "name": "Nonfarm Payrolls", "countryCode": "US",
         "dateUtc": "2026-10-02T12:30:00Z", "periodDateUtc": "2026-09-01T00:00:00Z", "consensus": 90.0,
         "previous": 162.0, "actual": None},
        {"eventId": "9c689bbf-af2a-4f65-81a8-c5f5e2b78d70", "name": "Initial Jobless Claims", "countryCode": "US",
         "dateUtc": "2026-09-24T12:30:00Z", "periodDateUtc": "2026-09-18T00:00:00Z", "consensus": 201.0,
         "previous": 196.0, "actual": 197.0},
        {"eventId": "6c5853c1-a409-4722-bdea-17ad5d8a193f", "name": "ISM Services PMI", "countryCode": "US",
         "dateUtc": "2026-09-03T14:00:00Z", "periodDateUtc": "2026-08-01T00:00:00Z", "consensus": None,
         "previous": 54.1, "actual": 55.4},
        {"eventId": "0ba3bb41-ebb9-4a54-89f3-36346484dcfb", "name": "ISM Manufacturing Employment Index",
         "countryCode": "US", "dateUtc": "2026-09-01T14:00:00Z", "consensus": None, "previous": 52.8, "actual": 51.2},
        {"eventId": "9cdf56fd-99e4-4026-aa99-2b6c0ca92811", "name": "Nonfarm Payrolls", "countryCode": "CA",
         "dateUtc": "2026-10-02T12:30:00Z", "periodDateUtc": "2026-09-01T00:00:00Z", "consensus": 1.0},
    ]
    events = parse_fxstreet(feed, now, "fxstreet")
    assert [e.event_code for e in events] == ["NFP", "INITIAL_CLAIMS", "ISM_SERVICES"]   # unknown id / other country dropped
    nfp, claims, ism = events
    assert (nfp.reference_period, nfp.consensus, nfp.actual, nfp.released_at) == ("2026-09", 90.0, None, None)
    assert nfp.consensus_captured_at == now                     # future release: captured live
    assert (claims.reference_period, claims.actual) == ("2026-09-18", 197.0)
    assert claims.released_at == claims.scheduled_at
    assert claims.consensus_captured_at == claims.scheduled_at - timedelta(days=1)   # archived consensus
    assert ism.consensus is None and ism.consensus_captured_at is None               # never usable
    assert reference_period("CPI_YOY", None, datetime(2026, 1, 9, tzinfo=timezone.utc)) == "2025-12"


def _xlsx(rows: list[list]) -> bytes:
    """Tiny .xlsx writer for tests (shared strings for text, inline numbers)."""
    import io
    import zipfile
    strings: list[str] = []
    sheet = []
    for i, row in enumerate(rows, start=1):
        cells = []
        for j, v in enumerate(row):
            ref = f"{chr(65 + j)}{i}"
            if isinstance(v, str):
                strings.append(v)
                cells.append(f'<c r="{ref}" t="s"><v>{len(strings) - 1}</v></c>')
            else:
                cells.append(f'<c r="{ref}"><v>{v}</v></c>')
        sheet.append(f"<row r=\"{i}\">{''.join(cells)}</row>")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("xl/workbook.xml", '<workbook xmlns:r="x"><sheets><sheet name="Disclaimer" sheetId="1" r:id="rId4"/>'
                   '<sheet name="US GLD Historical Archive" sheetId="2" r:id="rId5"/></sheets></workbook>')
        z.writestr("xl/_rels/workbook.xml.rels", '<Relationships><Relationship Id="rId4" Target="worksheets/sheet1.xml"/>'
                   '<Relationship Id="rId5" Target="worksheets/sheet2.xml"/></Relationships>')
        z.writestr("xl/sharedStrings.xml", "<sst>" + "".join(f"<si><t>{s}</t></si>" for s in strings) + "</sst>")
        z.writestr("xl/worksheets/sheet1.xml", "<worksheet><sheetData/></worksheet>")
        z.writestr("xl/worksheets/sheet2.xml", "<worksheet><sheetData>" + "".join(sheet) + "</sheetData></worksheet>")
    return buf.getvalue()


def test_gld_archive_parses_tonnes_and_skips_holidays():
    data = _xlsx([["Date", "Closing Price", "Tonnes of Gold"],
                  ["01-Oct-2026", 382.76, 1056.55],
                  ["02-Oct-2026", 380.14, 1055.7],
                  ["25-Nov-2004", "US Holiday", "US Holiday"],
                  ["05-Oct-2026", 379.55, 1056.27]])
    rows = parse_gld_archive(data, "spdr")
    assert [(r.as_of_date.isoformat(), r.tonnes) for r in rows] ==         [("2026-10-01", 1056.55), ("2026-10-02", 1055.7), ("2026-10-05", 1056.27)]
    assert rows[0].available_at == datetime(2026, 10, 2, 12, tzinfo=timezone.utc)    # public the next day


def test_imf_gold_holdings_become_monthly_net_tonnes():
    oz = 1_000_000 / 31.1034768                           # 1 tonne
    xml = "".join(f'<Obs COUNTRY="GX010" INDICATOR="RGV_REVS" TIME_PERIOD="{p}" OBS_VALUE="{v}"/>' for p, v in [
        ("2026-M05", 1000 * oz), ("2026-M06", 1050 * oz), ("2026-M08", 1100 * oz), ("2026-A", 1.0)])
    now = datetime(2026, 10, 6, tzinfo=timezone.utc)
    rows = parse_imf_gold(xml, "imf", now)
    assert [(r.period_month.isoformat(), r.net_tonnes) for r in rows] == [("2026-06-01", 50.0)]   # gap -> skipped
    assert imf_available_at(date(2026, 6, 1)) == datetime(2026, 8, 15, 12, tzinfo=timezone.utc)
    assert rows[0].available_at == datetime(2026, 8, 15, 12, tzinfo=timezone.utc)   # rule date > 45 days ago: kept
    assert imf_available_at(date(2026, 8, 1), now) == datetime(2026, 10, 15, 12, tzinfo=timezone.utc)  # rule ahead
    assert imf_available_at(date(2026, 7, 1), now) == now                           # rule 3 weeks ago: first seen
    assert imf_available_at(date(2026, 9, 1), now) == datetime(2026, 11, 15, 12, tzinfo=timezone.utc)
    assert imf_available_at(date(2015, 1, 1), now) == datetime(2015, 3, 15, 12, tzinfo=timezone.utc)


def test_bls_actuals():
    payload = {"Results": {"series": [
        {"seriesID": "CES0000000001", "data": [{"year": "2026", "period": "M09", "value": "159800"},
                                               {"year": "2026", "period": "M08", "value": "159770"}]},
        {"seriesID": "CUUR0000SA0", "data": [{"year": "2026", "period": "M08", "value": "334.980"},
                                             {"year": "2025", "period": "M08", "value": "325.000"}]},
        {"seriesID": "LNS14000000", "data": [{"year": "2026", "period": "M09", "value": "4.4"}]}]}}
    series = bls_values(payload)
    assert bls_actual("NFP", "2026-09", series) == 30.0
    assert bls_actual("CPI_YOY", "2026-08", series) == 3.1
    assert bls_actual("UNEMPLOYMENT", "2026-09", series) == 4.4
    assert bls_actual("CORE_CPI_MOM", "2026-09", series) is None   # not published yet
