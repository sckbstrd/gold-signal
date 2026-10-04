"""The documented worked example (02_SCORING_MODEL_V1.md section 11) as a full MarketSnapshot.

All values are ILLUSTRATIVE MOCK DATA, not real market history. Each series is a
deterministic synthetic path pinned to "anchor" observations so that the engine,
computing horizon changes from raw series exactly as it does in production,
sees precisely the inputs listed in the documentation.
"""
from __future__ import annotations

import math
import statistics
from datetime import date, datetime, timedelta, timezone

from app.engine import calendars
from app.engine.result import EngineState, RegimeState, SignalState
from app.engine.snapshot import CbMonth, MarketSnapshot, Obs, Release, Series

AS_OF = datetime(2026, 10, 2, 23, 30, tzinfo=timezone.utc)
HISTORY_START = date(2025, 7, 1)


def _utc(y, m, d, hh=12, mm=30) -> datetime:
    return datetime(y, m, d, hh, mm, tzinfo=timezone.utc)


def _anchor_dates(days: list[date], end: date) -> dict[str, date]:
    """Observation dates the engine will use for 1D / 7D / 30D / 90D horizons."""
    upto = [d for d in days if d <= end]
    pick = lambda limit: max(d for d in upto if d <= limit)  # noqa: E731
    return {"t": upto[-1], "d1": upto[-2], "d7": pick(end - timedelta(days=7)),
            "d30": pick(end - timedelta(days=30)), "d90": pick(end - timedelta(days=90))}


def _noise(k: int, phase: float) -> float:
    """Deterministic, irregular wiggle in roughly [-1, 1]: incommensurate sines plus a hashed jitter."""
    jitter = ((k * 2654435761 + int(phase * 1000)) % 1000) / 500.0 - 1.0
    return (0.45 * math.sin(0.21 * k + phase) + 0.30 * math.sin(0.057 * k + 2 * phase)
            + 0.25 * jitter)


def pinned_series(code: str, calendar: str, end: date, anchors: dict[date, float],
                  amp: float, phase: float) -> Series:
    """Piecewise-linear path through anchors + a smooth wiggle that is zero at every anchor."""
    days = calendars.business_days(HISTORY_START, end, calendar)
    keys = sorted(anchors)
    if keys[0] != days[0]:
        anchors = {days[0]: anchors[keys[0]], **anchors}
        keys = sorted(anchors)
    idx = {d: i for i, d in enumerate(days)}
    values = [0.0] * len(days)
    for a, b in zip(keys, keys[1:]):
        i, j = idx[a], idx[b]
        for k in range(i, j + 1):
            u = (k - i) / (j - i)
            base = anchors[a] + (anchors[b] - anchors[a]) * u
            wiggle = amp * math.sin(math.pi * u) * _noise(k, phase)
            values[k] = base + wiggle
    for d in keys:
        values[idx[d]] = anchors[d]
    # Round away last-bit libm differences (sin/exp differ across OSes) so the demo snapshot -- and
    # its reproducibility hash -- are identical on Windows, Linux and macOS.
    return Series(code, calendar, tuple(Obs(d, round(v, 9)) for d, v in zip(days, values)))


def with_window_stats(series: Series, n: int, mean: float, std: float, fixed: set[date]) -> Series:
    """Affinely rescale the non-anchor values of the last n observations so the
    window has exactly the requested population mean and standard deviation."""
    obs = list(series.obs)
    win = obs[-n:]
    free = [o for o in win if o.date not in fixed]
    pinned = [o.value for o in win if o.date in fixed]
    m_free = statistics.fmean(o.value for o in free)
    dev = [o.value - m_free for o in free]
    c = (n * mean - sum(pinned)) / len(free)
    target_sq = n * (std ** 2 + mean ** 2)
    a = math.sqrt((target_sq - sum(v * v for v in pinned) - len(free) * c * c) / sum(x * x for x in dev))
    new_vals = {o.date: round(a * x + c, 9) for o, x in zip(free, dev)}
    obs = [Obs(o.date, new_vals.get(o.date, o.value)) for o in obs]
    return Series(series.code, series.calendar, tuple(obs))


def _log_anchor(value: float, pct: float) -> float:
    """Start value such that 100*ln(value/start) == pct."""
    return value / math.exp(pct / 100)


def build_snapshot() -> MarketSnapshot:
    govt, nyse, fx = calendars.US_GOVT, calendars.NYSE, calendars.FX
    rates_end = date(2026, 10, 1)                       # Treasury/FRED data lag by one day
    g_days = calendars.business_days(HISTORY_START, rates_end, govt)
    ga = _anchor_dates(g_days, rates_end)

    def rates(code, t, d1, d7, d30, older, amp, phase):
        anchors = {ga["t"]: t, ga["d1"]: d1, ga["d7"]: d7, ga["d30"]: d30}
        anchors.update(older)
        return pinned_series(code, govt, rates_end, anchors, amp, phase)

    real = rates("US_REAL_10Y", 1.74, 1.77, 1.85, 2.02,
                 {date(2025, 10, 1): 1.78, date(2026, 3, 2): 1.95, date(2026, 6, 1): 2.08}, 0.035, 0.3)
    nominal = rates("US_NOM_10Y", 4.45, 4.47, 4.52, 4.61,
                    {date(2025, 10, 1): 4.12, date(2026, 3, 2): 4.02, date(2026, 6, 1): 4.18}, 0.03, 1.1)
    nominal = with_window_stats(nominal, 252, 4.15, 0.14, {ga["t"], ga["d1"], ga["d7"], ga["d30"]})
    tb3 = rates("US_TBILL_3M", 3.55, 3.56, 3.60, 3.78,
                {date(2025, 10, 1): 4.02, date(2026, 6, 1): 3.84}, 0.01, 2.0)
    tb6 = rates("US_TBILL_6M", 3.40, 3.41, 3.46, 3.55,
                {date(2025, 10, 1): 3.90, date(2026, 6, 1): 3.70}, 0.012, 2.5)
    tb1 = rates("US_TBILL_1Y", 3.18, 3.21, 3.30, 3.45,
                {date(2025, 10, 1): 3.75, date(2026, 6, 1): 3.58}, 0.015, 0.7)

    cut = date(2026, 9, 17)
    lower = Series.of("FED_TARGET_LOWER", govt, [(d, 3.50 if d >= cut else 3.75) for d in g_days])
    upper = Series.of("FED_TARGET_UPPER", govt, [(d, 3.75 if d >= cut else 4.00) for d in g_days])
    effr = Series.of("EFFR", govt, [(d, 3.58 if d >= cut else 3.83) for d in g_days])

    fx_end = AS_OF.date()
    f_days = calendars.business_days(HISTORY_START, fx_end, fx)
    fa = _anchor_dates(f_days, fx_end)
    dxy = pinned_series("DXY", fx, fx_end, {
        fa["t"]: 97.40, fa["d1"]: _log_anchor(97.40, -0.22), fa["d7"]: _log_anchor(97.40, -0.85),
        fa["d30"]: _log_anchor(97.40, -1.70), date(2025, 10, 2): 98.10, date(2026, 4, 1): 100.20,
    }, 0.25, 0.4)
    gold_t = 4180.50
    gold = pinned_series("XAUUSD", fx, fx_end, {
        fa["t"]: gold_t, fa["d1"]: gold_t / 1.0060, fa["d7"]: gold_t / 1.0194, fa["d30"]: gold_t / 1.0212,
        date(2026, 8, 21): 4265.00, date(2026, 5, 1): 3940.0, date(2026, 1, 2): 3880.0,
        date(2025, 10, 2): 3790.0,
    }, 18.0, 0.9)
    usdtry = pinned_series("USDTRY", fx, fx_end, {
        fa["t"]: 49.85, fa["d1"]: _log_anchor(49.85, 0.05), fa["d7"]: _log_anchor(49.85, 0.42),
        fa["d30"]: _log_anchor(49.85, 1.85), date(2025, 10, 2): 41.70, date(2026, 4, 1): 45.60,
    }, 0.04, 1.7)
    try_rate = Series.of("TCMB_POLICY_RATE", fx, [(d, 31.0 if d >= date(2026, 9, 11) else 32.5)
                                                    for d in f_days])

    n_end = date(2026, 10, 1)
    n_days = calendars.business_days(HISTORY_START, n_end, nyse)
    na = _anchor_dates(n_days, n_end)
    etf_t = 1500.5
    etf = pinned_series("ETF_HOLDINGS_T", nyse, n_end, {
        na["t"]: etf_t, na["d1"]: etf_t - 0.9, na["d7"]: _log_anchor(etf_t, 0.35),
        na["d30"]: _log_anchor(etf_t, 1.6), na["d90"]: _log_anchor(etf_t, 2.9),
        date(2025, 10, 1): 1392.0, date(2026, 3, 2): 1428.0,
    }, 1.2, 0.2)
    vix_days = calendars.business_days(HISTORY_START, fx_end, nyse)
    vix = pinned_series("VIX", nyse, fx_end, {
        vix_days[-1]: 17.8, vix_days[-6]: 18.54, date(2026, 4, 1): 22.5, date(2025, 10, 1): 16.4,
    }, 1.1, 0.6)

    releases = (
        Release("NFP", "2026-09", _utc(2026, 10, 2), _utc(2026, 10, 2), 22.0, 100.0, 30.0, _utc(2026, 10, 1, 20)),
        Release("UNEMPLOYMENT", "2026-09", _utc(2026, 10, 2), _utc(2026, 10, 2), 4.3, 4.3, 4.4, _utc(2026, 10, 1, 20)),
        Release("INITIAL_CLAIMS", "2026-W39", _utc(2026, 10, 1), _utc(2026, 10, 1), 226.0, 228.0, 241.0, _utc(2026, 9, 30, 20)),
        Release("ISM_MFG", "2026-09", _utc(2026, 10, 1, 14, 0), _utc(2026, 10, 1, 14, 0), 49.1, 49.6, 48.9, _utc(2026, 9, 30, 20)),
        Release("CORE_PCE_MOM", "2026-08", _utc(2026, 9, 25), _utc(2026, 9, 25), 0.3, 0.2, 0.2, _utc(2026, 9, 24, 20)),
        Release("PCE_YOY", "2026-08", _utc(2026, 9, 25), _utc(2026, 9, 25), 2.8, 2.7, 2.7, _utc(2026, 9, 24, 20)),
        Release("INITIAL_CLAIMS", "2026-W38", _utc(2026, 9, 24), _utc(2026, 9, 24), 233.0, 232.0, 226.0, _utc(2026, 9, 23, 20)),
        Release("CPI_YOY", "2026-08", _utc(2026, 9, 11), _utc(2026, 9, 11), 2.9, 2.9, 3.0, _utc(2026, 9, 10, 20)),
        Release("CORE_CPI_MOM", "2026-08", _utc(2026, 9, 11), _utc(2026, 9, 11), 0.2, 0.3, 0.3, _utc(2026, 9, 10, 20)),
        Release("ISM_SERVICES", "2026-09", _utc(2026, 10, 5, 14, 0), None, 51.2, 51.0, None, _utc(2026, 10, 2, 20)),
        Release("INITIAL_CLAIMS", "2026-W40", _utc(2026, 10, 8), None, 241.0, 235.0, None, None),
        Release("CPI_YOY", "2026-09", _utc(2026, 10, 14), None, 3.0, 2.9, None, None),
        Release("CORE_CPI_MOM", "2026-09", _utc(2026, 10, 14), None, 0.3, 0.3, None, None),
    )

    monthly = [58, 61, 70, 65, 72, 68, 75, 66, 64, 70, 65, 50, 60, 55]   # Jun 2025 .. Jul 2026
    cb = []
    for i, t in enumerate(monthly):
        y, m = divmod(2025 * 12 + 5 + i, 12)
        period = date(y, m + 1, 1)
        ny, nm = divmod(y * 12 + m + 2, 12)
        published = datetime(ny, nm + 1, 1, 12, 0, tzinfo=timezone.utc) - timedelta(days=1)
        cb.append(CbMonth(period, float(t), published))

    return MarketSnapshot(
        as_of=AS_OF, real_10y=real, nominal_10y=nominal, dxy=dxy, tbill_3m=tb3, tbill_6m=tb6, tbill_1y=tb1,
        fed_lower=lower, fed_upper=upper, effr=effr, etf_holdings=etf, vix=vix, gold=gold, usdtry=usdtry,
        try_policy_rate=try_rate, releases=releases, cb_months=tuple(cb),
    )


SCORE_HISTORY = (51.7, 52.4, 53.0, 54.1, 55.2, 56.0, 55.4, 56.3, 57.5, 58.0, 59.1, 59.4, 58.6, 57.2,
                 56.0, 72.0, 70.5, 66.8, 63.0, 62.4)   # official scores 2026-09-03 .. 2026-10-01


def prior_state(model_version: str = "1.0.0") -> EngineState:
    """Engine state as of the 2026-10-01 official evaluation."""
    return EngineState(
        model_version=model_version,
        global_=SignalState(signal="BUY", previous="HOLD", since=date(2026, 9, 25), days_in_band=5),
        gram=SignalState(signal="BUY", previous="HOLD", since=date(2026, 9, 18), days_in_band=11),
        regime=RegimeState(regime="GOLD_BULL"),
        score_history=SCORE_HISTORY,
        last_official_date=date(2026, 10, 1),
    )
