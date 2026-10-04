"""Gold Signal scoring engine (model v1.0.0). Pure functions only.

This package must never import from db/, providers/ or api/; tests enforce it.
"""
from .evaluate import evaluate, initial_state
from .params import ModelParams, load_params
from .result import EngineState, Evaluation, SignalResult
from .snapshot import CbMonth, MarketSnapshot, Obs, Release, Series

__all__ = [
    "evaluate", "initial_state", "load_params", "ModelParams", "EngineState", "Evaluation",
    "SignalResult", "MarketSnapshot", "Series", "Obs", "Release", "CbMonth",
]
