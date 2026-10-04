"""Scoring primitives (02_SCORING_MODEL_V1.md section 1)."""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence


def rnd(x: float, digits: int) -> float:
    """Round and normalise -0.0 so serialised output is byte-identical."""
    return round(x, digits) + 0.0


def soft(z: float, dead_zone: float) -> float:
    """Soft dead-zone: shrink |z| by ``dead_zone`` without crossing zero."""
    return math.copysign(max(abs(z) - dead_zone, 0.0), z)


def sq(z: float, dead_zone: float, kappa: float) -> float:
    """Squash a standardised move into (-1, 1), ignoring noise."""
    return math.tanh(soft(z, dead_zone) / kappa)


def freshness(age_bdays: int | None, fresh: int, hard: int) -> float:
    if age_bdays is None:
        return 0.0
    if age_bdays <= fresh:
        return 1.0
    if age_bdays >= hard:
        return 0.0
    return (hard - age_bdays) / (hard - fresh)


@dataclass(frozen=True)
class HorizonScore:
    key: str            # "d1", "d7", "d30", "d90"
    delta: float | None  # change over the horizon (bp or %), None if no anchor
    sigma: float
    z: float | None
    score: float        # sq(direction * z); 0 when delta is missing
    weight: float

    def as_dict(self, digits: int) -> dict:
        return {
            "key": self.key,
            "delta": None if self.delta is None else rnd(self.delta, digits),
            "sigma": self.sigma,
            "z": None if self.z is None else rnd(self.z, digits),
            "score": rnd(self.score, digits),
            "weight": self.weight,
            "missing": self.delta is None,
        }


def trend(
    deltas: Sequence[float | None],
    horizons: Sequence[int],
    sigmas: Sequence[float],
    weights: Sequence[float],
    direction: int,
    dead_zone: float,
    kappa: float,
) -> tuple[float, list[HorizonScore]]:
    """Multi-horizon trend score T(x; dir, sigma, omega) in (-1, 1).

    A missing horizon contributes 0 (neutral) and is flagged in the sub-scores.
    """
    total = 0.0
    parts: list[HorizonScore] = []
    for delta, h, sigma, w in zip(deltas, horizons, sigmas, weights):
        if delta is None:
            parts.append(HorizonScore(f"d{h}", None, sigma, None, 0.0, w))
            continue
        z = delta / sigma
        score = sq(direction * z, dead_zone, kappa)
        total += w * score
        parts.append(HorizonScore(f"d{h}", delta, sigma, z, score, w))
    return total, parts


def magnitude_word(abs_s: float, words: Sequence[Sequence]) -> str:
    for limit, word in words:
        if abs_s < limit:
            return word
    return "SHARP"
