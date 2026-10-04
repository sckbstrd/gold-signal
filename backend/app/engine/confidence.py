"""Section 5: model confidence (NOT a probability of future return)."""
from __future__ import annotations

from .params import ModelParams
from .primitives import rnd
from .result import ComponentResult


def critical_delayed(components: dict[str, ComponentResult], params: ModelParams) -> bool:
    return any(components[k].freshness == 0.0 for k in params["critical"])


def global_confidence(components: dict[str, ComponentResult], days_in_band: int, panic: bool,
                      params: ModelParams) -> tuple[int, dict[str, float]]:
    cfg = params["confidence"]
    d = params.digits
    w_total = sum(params.weights.values())
    strength = sum(c.weight * abs(c.s_eff) for c in components.values())
    net = abs(sum(c.weight * c.s_eff for c in components.values()))
    agreement = net / strength if strength > 1e-9 else 0.0
    magnitude = min(1.0, (strength / w_total) / cfg["magnitude_full"])
    fresh = sum(c.weight * c.freshness for c in components.values()) / w_total
    persistence = min(1.0, days_in_band / cfg["persistence_full_days"])
    value = 100 * fresh * (cfg["w_agreement"] * agreement + cfg["w_magnitude"] * magnitude
                           + cfg["w_persistence"] * persistence)
    if panic:
        value *= cfg["panic_multiplier"]
    if critical_delayed(components, params):
        value = min(value, cfg["delayed_cap"])
    parts = {"agreement": rnd(agreement, d), "magnitude": rnd(magnitude, d),
             "freshness": rnd(fresh, d), "persistence": rnd(persistence, d)}
    return int(round(value)), parts
