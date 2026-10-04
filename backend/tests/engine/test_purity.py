"""The engine must stay pure: no I/O layers, no clock, no randomness."""
from __future__ import annotations

import re
from pathlib import Path

ENGINE = Path(__file__).resolve().parents[2] / "app" / "engine"
FORBIDDEN = [
    r"from\s+\.\.\s*(db|providers|api)\b", r"import\s+app\.(db|providers|api)\b", r"from\s+app\.(db|providers|api)\b",
    r"\bdatetime\.now\(", r"\bdate\.today\(", r"\butcnow\(", r"\bimport\s+random\b", r"\btime\.time\(",
    r"\brequests\b", r"\bhttpx\b", r"\bopen\(",
]


def test_engine_sources_are_pure():
    offenders = []
    for path in ENGINE.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for pattern in FORBIDDEN:
            if re.search(pattern, text):
                offenders.append(f"{path.name}: {pattern}")
    assert offenders == []


def test_params_are_frozen(params):
    import pytest
    with pytest.raises(TypeError):
        params.raw["weights"]["REAL_YIELD"] = 99


def test_params_hash_is_stable(params):
    from app.engine.params import load_params
    assert load_params("1.0.0").sha256 == params.sha256
    assert len(params.sha256) == 64
