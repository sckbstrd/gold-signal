"""Engine input: an immutable, point-in-time bundle of market data.

The snapshot builder (backend/app/db/asof.py, Phase 3) fills this only with rows
whose ``available_at <= as_of``. ``MarketSnapshot.visible()`` is a second,
independent guard that drops anything dated after the evaluation time, so the
engine cannot see the future even if it is handed a careless snapshot.
"""
from __future__ import annotations

import bisect
import math
from dataclasses import dataclass, field, replace
from datetime import date, datetime, timedelta, timezone

from . import calendars


@dataclass(frozen=True, slots=True)
class Obs:
    date: date
    value: float


@dataclass(frozen=True)
class HorizonChange:
    horizon_days: int
    from_date: date
    from_value: float
    to_date: date
    to_value: float
    delta: float          # bp for kind="bp", % (100*ln) for kind="logpct"
    days: int             # calendar days between the two observations


@dataclass(frozen=True)
class Series:
    code: str
    calendar: str
    obs: tuple[Obs, ...] = ()

    def __post_init__(self) -> None:
        for a, b in zip(self.obs, self.obs[1:]):
            if not a.date < b.date:
                raise ValueError(f"{self.code}: observations must be strictly ascending ({a.date} >= {b.date})")
        for o in self.obs:
            if not math.isfinite(o.value):
                raise ValueError(f"{self.code}: non-finite value on {o.date}")

    @staticmethod
    def of(code: str, calendar: str, points) -> "Series":
        return Series(code, calendar, tuple(Obs(d, float(v)) for d, v in points))

    def __len__(self) -> int:
        return len(self.obs)

    @property
    def last(self) -> Obs | None:
        return self.obs[-1] if self.obs else None

    def upto(self, d: date) -> "Series":
        idx = bisect.bisect_right([o.date for o in self.obs], d)
        return self if idx == len(self.obs) else replace(self, obs=self.obs[:idx])

    def at_or_before(self, d: date) -> Obs | None:
        idx = bisect.bisect_right([o.date for o in self.obs], d)
        return self.obs[idx - 1] if idx else None

    def back(self, n: int) -> Obs | None:
        """The observation n steps before the last one."""
        return self.obs[-1 - n] if len(self.obs) > n else None

    def anchor(self, horizon_days: int) -> Obs | None:
        """Start point of a horizon: previous observation for 1D, else the latest
        observation on or before (last date - horizon)."""
        last = self.last
        if last is None:
            return None
        if horizon_days == 1:
            return self.back(1)
        return self.at_or_before(last.date - timedelta(days=horizon_days))

    def change(self, horizon_days: int, kind: str) -> HorizonChange | None:
        last, start = self.last, self.anchor(horizon_days)
        if last is None or start is None:
            return None
        if kind == "bp":
            delta = (last.value - start.value) * 100.0
        elif kind == "logpct":
            delta = 100.0 * math.log(last.value / start.value)
        else:
            raise ValueError(kind)
        return HorizonChange(horizon_days, start.date, start.value, last.date, last.value,
                             delta, (last.date - start.date).days)

    def tail(self, n: int) -> tuple[float, ...]:
        return tuple(o.value for o in self.obs[-n:])

    def age_bdays(self, as_of: date) -> int | None:
        if self.last is None:
            return None
        return calendars.business_days_between(self.last.date, as_of, self.calendar)


@dataclass(frozen=True)
class Release:
    code: str
    reference_period: str
    scheduled_at: datetime
    released_at: datetime | None = None
    previous: float | None = None
    consensus: float | None = None
    actual: float | None = None
    consensus_captured_at: datetime | None = None

    def usable_at(self, t: datetime) -> bool:
        """True if a fair observer at time t could compute the surprise."""
        if self.released_at is None or self.released_at > t:
            return False
        if self.actual is None or self.consensus is None:
            return False
        # A consensus recorded after the release could be contaminated by the actual.
        if self.consensus_captured_at is not None and self.consensus_captured_at >= self.released_at:
            return False
        return True


@dataclass(frozen=True)
class CbMonth:
    period: date          # first day of the reference month
    net_tonnes: float
    available_at: datetime


@dataclass(frozen=True)
class MarketSnapshot:
    as_of: datetime
    real_10y: Series = field(default_factory=lambda: Series("US_REAL_10Y", calendars.US_GOVT))
    nominal_10y: Series = field(default_factory=lambda: Series("US_NOM_10Y", calendars.US_GOVT))
    dxy: Series = field(default_factory=lambda: Series("DXY", calendars.FX))
    tbill_3m: Series = field(default_factory=lambda: Series("US_TBILL_3M", calendars.US_GOVT))
    tbill_6m: Series = field(default_factory=lambda: Series("US_TBILL_6M", calendars.US_GOVT))
    tbill_1y: Series = field(default_factory=lambda: Series("US_TBILL_1Y", calendars.US_GOVT))
    fed_lower: Series = field(default_factory=lambda: Series("FED_TARGET_LOWER", calendars.US_GOVT))
    fed_upper: Series = field(default_factory=lambda: Series("FED_TARGET_UPPER", calendars.US_GOVT))
    effr: Series = field(default_factory=lambda: Series("EFFR", calendars.US_GOVT))
    etf_holdings: Series = field(default_factory=lambda: Series("ETF_HOLDINGS_T", calendars.NYSE))
    vix: Series = field(default_factory=lambda: Series("VIX", calendars.NYSE))
    gold: Series = field(default_factory=lambda: Series("XAUUSD", calendars.FX))
    usdtry: Series = field(default_factory=lambda: Series("USDTRY", calendars.FX))
    try_policy_rate: Series = field(default_factory=lambda: Series("TCMB_POLICY_RATE", calendars.FX))
    releases: tuple[Release, ...] = ()
    cb_months: tuple[CbMonth, ...] = ()
    # False when no consensus/actual source covered this date: ECON is then MISSING, not "quiet".
    econ_covered: bool = True

    SERIES_FIELDS = (
        "real_10y", "nominal_10y", "dxy", "tbill_3m", "tbill_6m", "tbill_1y", "fed_lower", "fed_upper",
        "effr", "etf_holdings", "vix", "gold", "usdtry", "try_policy_rate",
    )

    def __post_init__(self) -> None:
        if self.as_of.tzinfo is None:
            raise ValueError("as_of must be timezone-aware (UTC)")

    @property
    def as_of_date(self) -> date:
        return self.as_of.astimezone(timezone.utc).date()

    def visible(self) -> "MarketSnapshot":
        """Drop everything that was not knowable at ``as_of``."""
        d = self.as_of_date
        changes = {name: getattr(self, name).upto(d) for name in self.SERIES_FIELDS}
        # The release *schedule* is public in advance (needed to detect delays), but actuals
        # and late-captured consensus are blanked until they were knowable.
        releases = []
        for r in self.releases:
            if r.released_at is not None and r.released_at > self.as_of:
                r = replace(r, released_at=None, actual=None)
            if r.consensus_captured_at is not None and r.consensus_captured_at > self.as_of:
                r = replace(r, consensus=None, consensus_captured_at=None)
            releases.append(r)
        cb = tuple(sorted((m for m in self.cb_months if m.available_at <= self.as_of), key=lambda m: m.period))
        return replace(self, releases=tuple(releases), cb_months=cb, **changes)

    def canonical(self) -> dict:
        """Stable, JSON-serialisable form used for the reproducibility hash."""
        out: dict = {"as_of": self.as_of.isoformat()}
        for name in self.SERIES_FIELDS:
            s: Series = getattr(self, name)
            out[name] = [[o.date.isoformat(), repr(o.value)] for o in s.obs]
        out["releases"] = [
            [r.code, r.reference_period, r.scheduled_at.isoformat(),
             r.released_at.isoformat() if r.released_at else None,
             repr(r.previous), repr(r.consensus), repr(r.actual),
             r.consensus_captured_at.isoformat() if r.consensus_captured_at else None]
            for r in sorted(self.releases, key=lambda r: (r.scheduled_at, r.code))
        ]
        out["cb_months"] = [[m.period.isoformat(), repr(m.net_tonnes), m.available_at.isoformat()]
                            for m in self.cb_months]
        if not self.econ_covered:
            out["econ_covered"] = False      # key omitted when True so existing hashes are unchanged
        return out
