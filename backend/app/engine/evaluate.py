"""Engine entry point.

    evaluate(snapshot, state, params, official=True) -> Evaluation(result, new_state)

Pure: no I/O, no clock, no randomness. Live evaluation and backtests call this
same function. Only *official* evaluations (one per US trading day) advance the
hysteresis and regime state; provisional (intraday) ones leave it untouched.
"""
from __future__ import annotations

import hashlib
from dataclasses import replace

from . import confidence as conf
from . import explain, gram, hysteresis, regime
from .aggregate import band_of, finalize, gold_score
from .components import ENGINES
from .params import ModelParams, canonical_json, load_params
from .result import EngineState, Evaluation, SignalBlock, SignalResult
from .snapshot import MarketSnapshot


def initial_state(params: ModelParams) -> EngineState:
    return EngineState(model_version=params.version)


def inputs_hash(snap: MarketSnapshot, params: ModelParams) -> str:
    payload = canonical_json({"params": params.sha256, "snapshot": snap.canonical()})
    return hashlib.sha256(payload.encode("ascii")).hexdigest()


def evaluate(snapshot: MarketSnapshot, state: EngineState | None = None,
             params: ModelParams | None = None, official: bool = True) -> Evaluation:
    params = params or load_params()
    state = state or initial_state(params)
    if state.model_version != params.version:
        raise ValueError(f"state belongs to model {state.model_version}, params are {params.version}")
    snap = snapshot.visible()
    on = snap.as_of_date
    if official and state.last_official_date is not None and on <= state.last_official_date:
        raise ValueError(f"official evaluation for {on} is not after {state.last_official_date}")

    # 1-3. components and score
    components = {code: finalize(code, ENGINES[code](snap, params), params) for code in params.weights}
    score = gold_score(components)
    raw_band = band_of(score, params)

    # 4. global hysteresis
    g_state = hysteresis.step(state.global_, score, on, params) if official else (
        state.global_ if state.global_.signal else hysteresis.step(state.global_, score, on, params))

    # 6. regime
    panic = regime.panic_check(snap, params)
    lookback = params["regime"]["reversal_lookback"]
    hist = state.score_history
    change_20 = score - hist[-lookback] if len(hist) >= lookback else None
    cand, breadth = regime.candidate(components, score, panic["triggered"], change_20, params)
    r_state = regime.step(state.regime, cand, params) if official else (
        state.regime if state.regime.regime else regime.step(state.regime, cand, params))

    # 5. confidence and data status
    confidence, parts = conf.global_confidence(components, g_state.days_in_band,
                                               r_state.regime == regime.PANIC, params)
    delayed = components["ECON"].extra.get("delayed", [])
    if conf.critical_delayed(components, params):
        data_status = "DELAYED"
    elif any(c.freshness < 1.0 for c in components.values()) or delayed:
        data_status = "DEGRADED"
    else:
        data_status = "OK"
    warnings = explain.data_warnings(components, delayed, r_state.regime)

    # 7. gram gold
    fed_extra = components["FED"].extra.get("current_policy", {})
    fx = gram.fx_leg(snap, fed_extra.get("midpoint"), params)
    gram_score, gram_tilt = gram.gram_score(score, fx, params)
    gr_state = hysteresis.step(state.gram, gram_score, on, params) if official else (
        state.gram if state.gram.signal else hysteresis.step(state.gram, gram_score, on, params))
    gram_conf = gram.gram_confidence(confidence, score, fx, params)
    if fx["status"] != "FRESH" and data_status == "OK":
        data_status = "DEGRADED"

    global_block = SignalBlock(
        kind="GLOBAL", score=score, raw_band=raw_band, signal=g_state.signal,
        previous_signal=g_state.previous, signal_since=g_state.since,
        pending=hysteresis.pending_view(g_state, score, params),
        confidence=confidence, confidence_parts=parts,
        explanation=explain.explain_global(components, g_state.signal, r_state.regime, warnings, params),
    )
    gram_block = SignalBlock(
        kind="GRAM_TRY", score=gram_score, raw_band=band_of(gram_score, params), signal=gr_state.signal,
        previous_signal=gr_state.previous, signal_since=gr_state.since,
        pending=hysteresis.pending_view(gr_state, gram_score, params),
        confidence=gram_conf, confidence_parts={"global_confidence": confidence,
                                                "fx_freshness": fx["freshness"],
                                                "legs_agree": gram.legs_agree(score, fx, params)},
        explanation=explain.explain_gram(score, g_state.signal, gr_state.signal, fx, params),
    )
    gold_last, fx_last = snap.gold.last, snap.usdtry.last
    gram_detail = {
        "fx_leg": {**fx, "tilt_points": gram_tilt, "max_tilt": params["gram"]["fx_tilt_max"]},
        "global_score": score,
        "theoretical_try": None if gold_last is None or fx_last is None
        else round(gram.gram_price(gold_last.value, fx_last.value, params), 2),
    }

    result = SignalResult(
        model_version=params.version, params_sha256=params.sha256, inputs_sha256=inputs_hash(snap, params),
        as_of=snap.as_of.isoformat(), as_of_date=on, is_official=official, data_status=data_status,
        regime=r_state.regime, regime_candidate=cand, regime_pending=regime.pending_view(r_state, params),
        panic_trigger={**panic, **breadth}, components=components,
        global_=global_block, gram=gram_block, gram_detail=gram_detail, warnings=warnings,
    )

    if not official:
        return Evaluation(result, state)
    keep = params["state"]["score_history_len"]
    new_state = replace(state, global_=g_state, gram=gr_state, regime=r_state,
                        score_history=(hist + (score,))[-keep:], last_official_date=on)
    return Evaluation(result, new_state)
