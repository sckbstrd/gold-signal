"""Parsers against the real response formats (trimmed samples captured 2026-10-04)."""
from __future__ import annotations

from datetime import date, datetime, timezone

from app.providers.econ_sources import bls_actual, bls_values, parse_ff_week, parse_number, reference_period
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


def test_econ_consensus_capture_and_bls_actuals():
    assert parse_number("0.3%") == 0.3 and parse_number("150K") == 150 and parse_number("") is None
    captured = datetime(2026, 10, 1, tzinfo=timezone.utc)
    feed = [{"title": "Non-Farm Employment Change", "country": "USD", "date": "2026-10-02T08:30:00-04:00",
             "impact": "High", "forecast": "100K", "previous": "22K"},
            {"title": "ISM Services PMI", "country": "USD", "date": "2026-10-05T10:00:00-04:00",
             "impact": "Medium", "forecast": "55.1", "previous": "55.4"}]
    events = parse_ff_week(feed, captured, "ffcal")
    assert len(events) == 1                         # ISM: no free actual -> not tracked
    e = events[0]
    assert (e.event_code, e.reference_period, e.consensus) == ("NFP", "2026-09", 100.0)
    assert e.consensus_captured_at == captured       # captured before the release
    late = parse_ff_week(feed, datetime(2026, 10, 3, tzinfo=timezone.utc), "ffcal")[0]
    assert late.consensus_captured_at is None        # captured after release: unusable (look-ahead)
    assert reference_period(datetime(2026, 1, 9, tzinfo=timezone.utc)) == "2025-12"

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
