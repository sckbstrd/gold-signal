"""The production engine must reproduce the documented worked example exactly
(02_SCORING_MODEL_V1.md section 11 / docs/scoring_v1_reference.py)."""
from __future__ import annotations

import pytest

from app.engine import evaluate


@pytest.fixture()
def example(snapshot, prior, params):
    return evaluate(snapshot, prior, params).result


def test_components_match_reference(example, ref):
    expected = ref.run_example()["aggregate"]["components"]
    for code, exp in expected.items():
        got = example.components[code]
        assert got.s == exp["s"], code
        assert got.freshness == exp["freshness"], code
        assert got.s_eff == exp["s_eff"], code
        assert got.points == exp["points"], code
        assert got.tilt == exp["tilt"], code


def test_score_signal_confidence_regime(example, ref):
    expected = ref.run_example()
    assert example.global_.score == expected["aggregate"]["score"] == 61.2
    assert example.global_.raw_band == "BUY"
    assert example.global_.signal == "BUY"
    assert example.global_.pending is None
    assert example.global_.confidence == expected["confidence"]["confidence"] == 68
    for key in ("agreement", "magnitude", "freshness", "persistence"):
        assert example.global_.confidence_parts[key] == expected["confidence"][key]
    assert example.regime_candidate == expected["regime_candidate"] == "GOLD_BULL"
    assert example.regime == "GOLD_BULL"
    assert example.panic_trigger["triggered"] is False
    assert example.data_status == "OK"


def test_gram_gold_matches_reference(example, ref):
    expected = ref.run_example()["gram"]
    assert example.gram_detail["theoretical_try"] == expected["gram_try"] == 6700.15
    assert example.gram_detail["fx_leg"]["s"] == expected["s_fx"]
    assert [example.gram_detail["fx_leg"]["excess_pct"][k] for k in ("d1", "d7", "d30")] == \
        expected["fx_excess_pct"]
    assert example.gram.score == expected["score"] == 61.2
    assert example.gram.signal == "BUY"
    assert example.gram.confidence == expected["confidence"]


def test_component_inputs_are_the_documented_ones(example):
    c = example.components
    assert c["REAL_YIELD"].inputs["changes"] == {"d1": -3.0, "d7": -11.0, "d30": -28.0}
    assert c["FED"].inputs["changes"] == {"d1": -2.0, "d7": -9.0, "d30": -21.0}
    assert c["FED"].extra["market_implied"]["priced_12m_bp"] == -44.5
    assert c["DXY"].inputs["changes"] == {"d1": -0.22, "d7": -0.85, "d30": -1.7}
    assert c["NOMINAL_10Y"].inputs["breakeven_changes"] == {"d1": 1.0, "d7": 4.0, "d30": 12.0}
    assert c["NOMINAL_10Y"].extra["mean_252"] == 4.15
    assert c["NOMINAL_10Y"].extra["std_252"] == 0.14
    assert c["ETF"].inputs["changes"] == {"d7": 0.35, "d30": 1.6, "d90": 2.9}
    assert c["CENTRAL_BANKS"].extra["t12_tonnes"] == 780
    assert c["CENTRAL_BANKS"].extra["t3_tonnes"] == 165


def test_explanation_codes(example):
    e = example.global_.explanation
    assert e["headline"] == {"code": "WHY_SIGNAL", "params": {"signal": "BUY"}}
    assert [r["code"] for r in e["positive"]] == [
        "REAL_YIELD_FALLING", "FED_PATH_LOWER", "DXY_FALLING", "ETF_INFLOWS", "CB_BUYING_STRONG"]
    assert [r["code"] for r in e["neutral"]] == ["ECON_MIXED"]
    assert e["neutral"][0]["params"] == {"top_positive": "NFP", "top_negative": "CPI_YOY"}
    assert [r["code"] for r in e["negative"]] == ["NOMINAL_LEVEL_ELEVATED"]
    assert e["positive"][0]["params"]["d30_bp"] == -28.0
    assert e["conclusion"] == {"code": "MOST_FAVOR_WITH_RISK", "params": {"risk": "NOMINAL_10Y"}}
    g = example.gram.explanation
    assert g["conclusion"]["code"] == "GRAM_FOLLOWS_GLOBAL"
    assert [r["code"] for r in g["neutral"]] == ["GRAM_FX_IN_LINE_WITH_CARRY"]


def test_state_advances(snapshot, prior, params):
    ev = evaluate(snapshot, prior, params)
    assert ev.state.global_.days_in_band == 6
    assert ev.state.score_history[-1] == 61.2
    assert len(ev.state.score_history) == 21
    assert str(ev.state.last_official_date) == "2026-10-02"


def test_provisional_evaluation_does_not_touch_state(snapshot, prior, params):
    ev = evaluate(snapshot, prior, params, official=False)
    assert ev.state == prior
    assert ev.result.is_official is False
