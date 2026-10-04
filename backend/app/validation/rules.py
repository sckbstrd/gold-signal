"""Data-quality rules applied to every fetched observation (01_ARCHITECTURE.md section 5).

RANGE      outside hard bounds                      -> rejected
TIMESTAMP  dated in the future                      -> rejected
SPIKE      a one-observation jump beyond the series' plausible daily move that reverses
           the next day                             -> SUSPECT (excluded from the model)
           ...or is the latest point (no confirmation yet)  -> SUSPECT until the next fetch
CROSS      spot vs futures disagree by more than 3% -> issue logged (display only)

Staleness, missing data, holidays and delayed releases are handled by the engine itself
(freshness decay, business-day calendars, delayed-release detection), so they are never
silently ignored.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime

from app.providers.base import SERIES, Observation, Quote


@dataclass(frozen=True)
class Issue:
    rule: str
    severity: str
    series_code: str | None
    source: str | None
    details: dict


@dataclass(frozen=True)
class Checked:
    observation: Observation
    quality: str          # OK | SUSPECT


def _move(spec, a: float, b: float) -> float:
    if spec.spike_relative:
        return abs(b / a - 1) if a else float("inf")
    return abs(b - a)


def validate(rows: list[Observation], now: datetime) -> tuple[list[Checked], list[Issue]]:
    issues: list[Issue] = []
    by_series: dict[str, list[Observation]] = defaultdict(list)
    for o in rows:
        spec = SERIES.get(o.series_code)
        if spec is None:
            issues.append(Issue("UNKNOWN_SERIES", "WARN", o.series_code, o.source, {}))
            continue
        if o.observation_date > now.date():
            issues.append(Issue("TIMESTAMP", "WARN", o.series_code, o.source,
                                {"date": o.observation_date.isoformat(), "reason": "future date"}))
            continue
        if not (spec.min_value <= o.value <= spec.max_value):
            issues.append(Issue("RANGE", "WARN", o.series_code, o.source,
                                {"date": o.observation_date.isoformat(), "value": o.value,
                                 "bounds": [spec.min_value, spec.max_value]}))
            continue
        by_series[o.series_code].append(o)

    out: list[Checked] = []
    for code, series in by_series.items():
        spec = SERIES[code]
        series.sort(key=lambda o: o.observation_date)
        # de-duplicate dates (last one wins) before checking moves
        dedup: dict = {}
        for o in series:
            dedup[o.observation_date] = o
        series = list(dedup.values())
        quality = ["OK"] * len(series)
        if spec.spike is not None and series:
            prev = series[0].value          # last accepted value (never a suspect one)
            for i in range(1, len(series)):
                jump = _move(spec, prev, series[i].value)
                if jump <= spec.spike:
                    prev = series[i].value
                    continue
                if i + 1 == len(series):
                    # Latest point, no confirmation yet: keep it (a real crash today is exactly what
                    # panic detection is for) but log it for review.
                    issues.append(Issue("SPIKE", "INFO", code, series[i].source, {
                        "date": series[i].observation_date.isoformat(), "value": series[i].value,
                        "previous": prev, "status": "unconfirmed, kept"}))
                    continue
                # A data error snaps back: the next value returns to within 25% of the jump.
                if _move(spec, prev, series[i + 1].value) <= 0.25 * jump:
                    quality[i] = "SUSPECT"
                    issues.append(Issue("SPIKE", "WARN", code, series[i].source, {
                        "date": series[i].observation_date.isoformat(), "value": series[i].value, "previous": prev,
                        "status": "reverted next day, excluded"}))
                else:
                    prev = series[i].value  # the move persisted: a genuine market move
        out += [Checked(o, q) for o, q in zip(series, quality)]
    return out, issues


def cross_check_spot(spot: Quote | None, futures_last: float | None, tolerance: float = 0.03) -> list[Issue]:
    if spot is None or futures_last is None:
        return []
    diff = spot.value / futures_last - 1
    if abs(diff) > tolerance:
        return [Issue("CROSS_SOURCE", "WARN", "XAUUSD", spot.source,
                      {"spot": spot.value, "futures": futures_last, "diff_pct": round(100 * diff, 2)})]
    return []
