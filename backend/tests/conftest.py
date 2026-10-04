from __future__ import annotations

import importlib.util
import math
import sys
from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
REPO = BACKEND.parent
sys.path.insert(0, str(BACKEND))

from app.demo import worked_example as wx  # noqa: E402
from app.engine import load_params  # noqa: E402
from app.engine.snapshot import Series  # noqa: E402


def _load_reference():
    path = REPO / "docs" / "scoring_v1_reference.py"
    spec = importlib.util.spec_from_file_location("scoring_v1_reference", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["scoring_v1_reference"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="session")
def ref():
    """docs/scoring_v1_reference.py: the executable specification."""
    return _load_reference()


@pytest.fixture(scope="session")
def params():
    return load_params("1.0.0")


@pytest.fixture()
def snapshot():
    return wx.build_snapshot()


@pytest.fixture()
def prior():
    return wx.prior_state()


def series_with_changes(code: str, calendar: str, end: date, value: float,
                        changes: dict[int, float], kind: str) -> Series:
    """Synthetic series ending at ``value`` whose horizon changes equal ``changes``
    (bp for kind='bp', log-% for kind='logpct')."""
    from app.engine import calendars
    days = calendars.business_days(wx.HISTORY_START, end, calendar)
    anchors_at = wx._anchor_dates(days, end)
    anchors = {anchors_at["t"]: value}
    for h, delta in changes.items():
        key = f"d{h}"
        start = value - delta / 100 if kind == "bp" else value / math.exp(delta / 100)
        anchors[anchors_at[key]] = start
    return wx.pinned_series(code, calendar, end, anchors, 0.0, 0.0)


def shift_as_of(snap, days: int):
    """Same data, evaluated ``days`` calendar days later (data gets older)."""
    return replace(snap, as_of=snap.as_of + timedelta(days=days))
