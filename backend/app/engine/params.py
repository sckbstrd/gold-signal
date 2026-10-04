"""Versioned, frozen model parameters.

Parameters live in JSON files under ``params/``. The engine never hard-codes a
tunable number: changing any value means a new file and a new model version.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping

PARAMS_DIR = Path(__file__).parent / "params"
DEFAULT_VERSION = "1.0.0"


def _freeze(value: Any) -> Any:
    if isinstance(value, dict):
        return MappingProxyType({k: _freeze(v) for k, v in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(v) for v in value)
    return value


@dataclass(frozen=True)
class ModelParams:
    version: str
    sha256: str
    raw: Mapping[str, Any]

    def __getitem__(self, key: str) -> Any:
        return self.raw[key]

    def component(self, code: str) -> Mapping[str, Any]:
        return self.raw["components"][code]

    @property
    def weights(self) -> Mapping[str, float]:
        return self.raw["weights"]

    @property
    def dead_zone(self) -> float:
        return self.raw["dead_zone"]

    @property
    def kappa(self) -> float:
        return self.raw["kappa"]

    @property
    def digits(self) -> int:
        return self.raw["round_component"]

    @property
    def neutral(self) -> float:
        return self.raw["neutral_threshold"]


def canonical_json(data: Any) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def params_from_dict(data: dict[str, Any]) -> ModelParams:
    sha = hashlib.sha256(canonical_json(data).encode("ascii")).hexdigest()
    return ModelParams(version=data["version"], sha256=sha, raw=_freeze(data))


@lru_cache(maxsize=8)
def load_params(version: str = DEFAULT_VERSION) -> ModelParams:
    path = PARAMS_DIR / f"v{version.replace('.', '_')}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    if data["version"] != version:
        raise ValueError(f"{path.name} declares version {data['version']}, expected {version}")
    weights_total = sum(data["weights"].values())
    if abs(weights_total - 100) > 1e-9:
        raise ValueError(f"weights must sum to 100, got {weights_total}")
    return params_from_dict(data)
