"""Engine output and carried state."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

FRESH, AGING, STALE, MISSING = "FRESH", "AGING", "STALE", "MISSING"


def status_for(freshness: float, has_data: bool) -> str:
    if not has_data:
        return MISSING
    if freshness >= 1.0:
        return FRESH
    if freshness > 0.0:
        return AGING
    return STALE


@dataclass(frozen=True)
class ComponentResult:
    """One scored component. ``s`` is the raw score in (-1, 1) before freshness."""
    code: str
    weight: float
    s: float
    freshness: float
    s_eff: float
    points: float
    tilt: float
    impact: str                       # BULLISH | BEARISH | NEUTRAL (|s_eff| vs neutral threshold)
    status: str
    age_bdays: int | None
    inputs: dict[str, Any] = field(default_factory=dict)
    sub_scores: list[dict[str, Any]] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RawComponent:
    """What a component engine returns before aggregation."""
    s: float
    has_data: bool
    age_bdays: int | None
    freshness: float
    inputs: dict[str, Any] = field(default_factory=dict)
    sub_scores: list[dict[str, Any]] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SignalState:
    signal: str | None = None
    previous: str | None = None      # signal before the last confirmed change
    since: date | None = None        # date the current signal was confirmed
    pending_dir: int = 0             # +1 upgrade pending, -1 downgrade pending
    pending_days: int = 0
    days_in_band: int = 0            # consecutive official evals with raw band == signal


@dataclass(frozen=True)
class RegimeState:
    regime: str | None = None
    candidate: str | None = None
    candidate_days: int = 0
    calm_days: int = 0               # consecutive non-trigger evals while in PANIC


@dataclass(frozen=True)
class EngineState:
    model_version: str
    global_: SignalState = SignalState()
    gram: SignalState = SignalState()
    regime: RegimeState = RegimeState()
    score_history: tuple[float, ...] = ()   # previous official global scores, oldest first
    last_official_date: date | None = None


@dataclass(frozen=True)
class SignalBlock:
    kind: str                         # GLOBAL | GRAM_TRY
    score: float
    raw_band: str
    signal: str
    previous_signal: str | None
    signal_since: date | None
    pending: dict[str, Any] | None
    confidence: int
    confidence_parts: dict[str, float]
    explanation: dict[str, Any]


@dataclass(frozen=True)
class SignalResult:
    model_version: str
    params_sha256: str
    inputs_sha256: str
    as_of: str                        # ISO timestamp of the evaluation
    as_of_date: date
    is_official: bool
    data_status: str                  # OK | DEGRADED | DELAYED
    regime: str
    regime_candidate: str
    regime_pending: dict[str, Any] | None
    panic_trigger: dict[str, Any]
    components: dict[str, ComponentResult]
    global_: SignalBlock
    gram: SignalBlock
    gram_detail: dict[str, Any]
    warnings: list[dict[str, Any]]


@dataclass(frozen=True)
class Evaluation:
    result: SignalResult
    state: EngineState
