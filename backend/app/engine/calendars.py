"""Deterministic holiday calendars used for data-age (freshness) calculations.

US_GOVT  US federal holidays (Treasury / H.15 data: no prints on these days),
         Saturday holidays observed Friday, Sunday holidays observed Monday.
NYSE     NYSE full-day closures (gold ETF holdings, VIX, backtest trading days).
FX       24x5 markets (XAU/USD, DXY, USD/TRY): weekdays except Jan 1 and Dec 25.

Rules are computed, not looked up, so the calendars work for any year.
"""
from __future__ import annotations

from datetime import date, timedelta
from functools import lru_cache

US_GOVT = "US_GOVT"
NYSE = "NYSE"
FX = "FX"


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    d = date(year, month, 1)
    d += timedelta(days=(weekday - d.weekday()) % 7)
    return d + timedelta(weeks=n - 1)


def _last_weekday(year: int, month: int, weekday: int) -> date:
    d = date(year, month + 1, 1) - timedelta(days=1) if month < 12 else date(year, 12, 31)
    return d - timedelta(days=(d.weekday() - weekday) % 7)


def _easter(year: int) -> date:
    """Anonymous Gregorian algorithm."""
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month, day = divmod(h + l - 7 * m + 114, 31)
    return date(year, month, day + 1)


def _observed(d: date) -> date:
    if d.weekday() == 5:
        return d - timedelta(days=1)
    if d.weekday() == 6:
        return d + timedelta(days=1)
    return d


@lru_cache(maxsize=256)
def holidays(calendar: str, year: int) -> frozenset[date]:
    if calendar == FX:
        return frozenset({date(year, 1, 1), date(year, 12, 25)})

    mon, thu = 0, 3
    days: set[date] = {
        _nth_weekday(year, 1, mon, 3),    # Martin Luther King Jr. Day
        _nth_weekday(year, 2, mon, 3),    # Washington's Birthday
        _last_weekday(year, 5, mon),      # Memorial Day
        _observed(date(year, 7, 4)),      # Independence Day
        _nth_weekday(year, 9, mon, 1),    # Labor Day
        _nth_weekday(year, 11, thu, 4),   # Thanksgiving
        _observed(date(year, 12, 25)),    # Christmas
    }
    if calendar == US_GOVT:
        days.add(_observed(date(year, 1, 1)))
        days.add(_observed(date(year + 1, 1, 1)))     # Saturday New Year is observed Dec 31
        days.add(_nth_weekday(year, 10, mon, 2))      # Columbus Day
        days.add(_observed(date(year, 11, 11)))       # Veterans Day
        if year >= 2021:
            days.add(_observed(date(year, 6, 19)))    # Juneteenth
    elif calendar == NYSE:
        new_year = date(year, 1, 1)
        if new_year.weekday() != 5:                   # NYSE does not close Dec 31 for a Saturday New Year
            days.add(_observed(new_year))
        days.add(_easter(year) - timedelta(days=2))   # Good Friday
        if year >= 2022:
            days.add(_observed(date(year, 6, 19)))
    else:
        raise ValueError(f"unknown calendar {calendar!r}")
    # Observed dates can spill into the neighbouring year (e.g. Jan 1 on a Saturday).
    return frozenset(d for d in days if d.year == year)


def is_business_day(d: date, calendar: str) -> bool:
    return d.weekday() < 5 and d not in holidays(calendar, d.year)


def business_days_between(start: date, end: date, calendar: str) -> int:
    """Number of business days d with start < d <= end (0 if end <= start)."""
    if end <= start:
        return 0
    count = 0
    d = start + timedelta(days=1)
    while d <= end:
        if is_business_day(d, calendar):
            count += 1
        d += timedelta(days=1)
    return count


def business_days(start: date, end: date, calendar: str) -> list[date]:
    """All business days in [start, end]."""
    out = []
    d = start
    while d <= end:
        if is_business_day(d, calendar):
            out.append(d)
        d += timedelta(days=1)
    return out
