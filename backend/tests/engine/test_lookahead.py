"""Information from the future must never change a signal."""
from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime, timedelta, timezone

from app.engine import evaluate
from app.engine.snapshot import CbMonth, MarketSnapshot, Obs, Release, Series


def _with_future_obs(s: Series, after: date) -> Series:
    if not s.obs:
        return s
    extra = tuple(Obs(after + timedelta(days=i), s.obs[-1].value * (3.0 if i % 2 else 0.2))
                  for i in range(1, 15))
    return replace(s, obs=s.obs + extra)


def test_future_observations_and_actuals_are_invisible(snapshot, prior, params):
    """Identical result *including the reproducibility hash*."""
    base = evaluate(snapshot, prior, params).result
    as_of = snapshot.as_of
    future_actuals = tuple(
        replace(r, released_at=as_of + timedelta(hours=1), actual=99.0) if r.released_at is None else r
        for r in snapshot.releases
    )
    polluted = replace(
        snapshot,
        **{name: _with_future_obs(getattr(snapshot, name), as_of.date())
           for name in MarketSnapshot.SERIES_FIELDS},
        releases=future_actuals,
        cb_months=snapshot.cb_months + (CbMonth(date(2026, 8, 1), -900.0, as_of + timedelta(minutes=1)),),
    )
    assert evaluate(polluted, prior, params).result == base


def test_future_releases_do_not_change_the_model_output(snapshot, prior, params):
    base = evaluate(snapshot, prior, params).result
    as_of = snapshot.as_of
    polluted = replace(
        snapshot,
        **{name: _with_future_obs(getattr(snapshot, name), as_of.date())
           for name in MarketSnapshot.SERIES_FIELDS},
        releases=snapshot.releases + (
            Release("NFP", "2026-10", as_of + timedelta(days=30), as_of + timedelta(days=30),
                    30.0, 100.0, -900.0, as_of),
            Release("CORE_CPI_MOM", "2026-09", as_of + timedelta(hours=1), as_of + timedelta(hours=1),
                    0.3, 0.3, 1.5, as_of - timedelta(days=1)),
        ),
        cb_months=snapshot.cb_months + (
            CbMonth(date(2026, 8, 1), -900.0, as_of + timedelta(minutes=1)),
        ),
    )
    got = evaluate(polluted, prior, params).result
    # The public release *schedule* legitimately enters the input hash; nothing else may differ.
    assert replace(got, inputs_sha256="") == replace(base, inputs_sha256="")


def test_consensus_recorded_after_release_is_not_used(snapshot, prior, params):
    released = datetime(2026, 10, 2, 12, 30, tzinfo=timezone.utc)
    contaminated = Release("CORE_CPI_MOM", "2026-09-x", released, released, 0.3, 0.9, 0.9,
                           consensus_captured_at=released + timedelta(minutes=5))
    snap = replace(snapshot, releases=snapshot.releases + (contaminated,))
    events = evaluate(snap, prior, params).result.components["ECON"].extra["events"]
    assert all(e["reference_period"] != "2026-09-x" for e in events)


def test_release_becomes_visible_only_at_release_time(snapshot, prior, params):
    nfp_time = datetime(2026, 10, 2, 12, 30, tzinfo=timezone.utc)
    before = replace(snapshot, as_of=nfp_time - timedelta(minutes=1))
    after = replace(snapshot, as_of=nfp_time + timedelta(minutes=1))
    codes = lambda snap: {e["code"] + e["reference_period"]  # noqa: E731
                          for e in evaluate(snap, prior, params, official=False)
                          .result.components["ECON"].extra["events"]}
    assert "NFP2026-09" not in codes(before)
    assert "NFP2026-09" in codes(after)
