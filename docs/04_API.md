# Gold Signal — REST API v1

Status: **DRAFT FOR REVIEW**. The base path is `/api/v1`. Every endpoint is read-only `GET`, returns JSON, and
uses UTC ISO-8601 timestamps. FastAPI also serves the generated OpenAPI spec at `/api/v1/openapi.json`.

**Conventions**
- The examples below match the worked example in `02_SCORING_MODEL_V1.md` (mock market, 2026-10-02). The
  Android Phase-1 mock fixtures are these exact payloads.
- Enums: `signal` ∈ STRONG_BUY | BUY | HOLD | REDUCE | SELL · `regime` ∈ GOLD_BULL | GOLD_BEAR | TRANSITION | PANIC ·
  `data_status` ∈ OK | DEGRADED | DELAYED · component `status` ∈ FRESH | AGING | STALE | MISSING | MOCK.
- Human text is **not** returned. Explanations are `{code, magnitude?, params}` and get localized on the device.
- Errors use RFC 7807 `application/problem+json`: `{"type","title","status","detail"}`.
- Optional auth: `X-Api-Key` header (enabled with `API_KEYS` env var). Responses carry `ETag` and `Cache-Control: max-age=60`.

---

## GET /gold/current

Prices only. These are never inputs to the score.

```json
{
  "as_of": "2026-10-02T23:30:00Z",
  "gold": {
    "symbol": "XAUUSD", "price_usd": 4180.50, "observed_at": "2026-10-02T23:29:41Z",
    "change_pct": { "d1": 0.60, "d7": 1.94, "d30": 2.12 },
    "high_52w": 4265.00, "high_52w_date": "2026-08-21", "distance_from_high_pct": -1.98,
    "futures_ref": null,
    "status": "MOCK", "source": "mock"
  },
  "usdtry": { "rate": 49.85, "observed_at": "2026-10-02T23:29:41Z",
              "change_pct": { "d1": 0.05, "d7": 0.42, "d30": 1.85 }, "status": "MOCK", "source": "mock" },
  "gram_gold": {
    "theoretical_try": 6700.15,
    "formula": "XAUUSD / 31.1034768 * USDTRY",
    "change_pct": { "d1": 0.65, "d7": 2.36, "d30": 3.97 },
    "decomposition_30d_pct": { "gold": 2.12, "usdtry": 1.85 },
    "market_try": null, "market_premium_pct": null, "market_source": null
  },
  "data_status": "OK"
}
```

## GET /gold/signal

`?kind=GLOBAL|GRAM_TRY|ALL` (default ALL)

```json
{
  "model_version": "1.0.0",
  "evaluated_at": "2026-10-02T23:30:00Z",
  "as_of_date": "2026-10-02",
  "is_official": true,
  "next_official_evaluation": "2026-10-05T23:30:00Z",
  "data_status": "OK",
  "global": {
    "score": 61.2,
    "raw_band": "BUY",
    "signal": "BUY",
    "previous_signal": "HOLD",
    "signal_since": "2026-09-25",
    "pending": null,
    "confidence": 68,
    "confidence_parts": { "agreement": 0.8607, "magnitude": 0.52, "freshness": 1.0, "persistence": 0.6 },
    "regime": "GOLD_BULL",
    "regime_pending": null,
    "components": [
      { "code": "REAL_YIELD",    "weight": 30, "s": 0.3358,  "freshness": 1.0, "points": 20.04, "tilt": 5.04,  "impact": "BULLISH", "status": "FRESH" },
      { "code": "FED",           "weight": 20, "s": 0.2946,  "freshness": 1.0, "points": 12.95, "tilt": 2.95,  "impact": "BULLISH", "status": "FRESH" },
      { "code": "DXY",           "weight": 15, "s": 0.2475,  "freshness": 1.0, "points": 9.36,  "tilt": 1.86,  "impact": "BULLISH", "status": "FRESH" },
      { "code": "NOMINAL_10Y",   "weight": 10, "s": -0.1811, "freshness": 1.0, "points": 4.09,  "tilt": -0.91, "impact": "BEARISH", "status": "FRESH" },
      { "code": "ECON",          "weight": 10, "s": 0.1449,  "freshness": 1.0, "points": 5.72,  "tilt": 0.72,  "impact": "NEUTRAL", "status": "FRESH" },
      { "code": "ETF",           "weight": 10, "s": 0.1667,  "freshness": 1.0, "points": 5.83,  "tilt": 0.83,  "impact": "BULLISH", "status": "FRESH" },
      { "code": "CENTRAL_BANKS", "weight": 5,  "s": 0.2791,  "freshness": 1.0, "points": 3.20,  "tilt": 0.70,  "impact": "BULLISH", "status": "FRESH" }
    ],
    "explanation": {
      "headline": { "code": "WHY_SIGNAL", "params": { "signal": "BUY" } },
      "positive": [
        { "code": "REAL_YIELD_FALLING", "magnitude": "MODERATE", "params": { "d30_bp": -28, "d7_bp": -11 } },
        { "code": "FED_PATH_LOWER", "magnitude": "MODERATE", "params": { "d30_bp": -21, "priced_12m_bp": -44.5 } },
        { "code": "DXY_FALLING", "magnitude": "MODERATE", "params": { "d30_pct": -1.70 } },
        { "code": "ETF_INFLOWS", "magnitude": "MODERATE", "params": { "d30_pct": 1.6 } },
        { "code": "CB_BUYING_STRONG", "magnitude": "MODERATE", "params": { "t12_tonnes": 780 } }
      ],
      "neutral": [
        { "code": "ECON_MIXED", "params": { "top_positive": "NFP", "top_negative": "CPI_YOY" } }
      ],
      "negative": [
        { "code": "NOMINAL_LEVEL_ELEVATED", "magnitude": "MODERATE", "params": { "level_pct": 4.45, "z_level": 2.14 } }
      ],
      "warnings": [],
      "conclusion": { "code": "MOST_FAVOR_WITH_RISK", "params": { "risk": "NOMINAL_10Y" } }
    }
  },
  "gram_try": {
    "score": 61.2, "raw_band": "BUY", "signal": "BUY", "previous_signal": "BUY",
    "signal_since": "2026-09-18", "pending": null, "confidence": 68,
    "global_score": 61.2,
    "fx_leg": { "s": 0.0, "tilt_points": 0.0, "max_tilt": 25,
                "usdtry_change_pct": { "d1": 0.05, "d7": 0.42, "d30": 1.85 },
                "carry_pct": { "d1": 0.075, "d7": 0.525, "d30": 2.25 },
                "excess_pct": { "d1": -0.025, "d7": -0.105, "d30": -0.40 },
                "i_try_pct": 31.0, "i_usd_pct": 3.625, "status": "FRESH" },
    "explanation": {
      "headline": { "code": "WHY_GRAM_SIGNAL", "params": { "signal": "BUY" } },
      "positive": [ { "code": "GRAM_GLOBAL_DRIVER", "params": { "global_signal": "BUY", "global_score": 61.2 } } ],
      "neutral":  [ { "code": "GRAM_FX_IN_LINE_WITH_CARRY", "params": { "d30_pct": 1.85, "carry_30d_pct": 2.25 } } ],
      "negative": [],
      "warnings": [],
      "conclusion": { "code": "GRAM_FOLLOWS_GLOBAL", "params": {} }
    }
  },
  "disclaimer_code": "NOT_FINANCIAL_ADVICE"
}
```

`pending`, when present: `{ "signal": "STRONG_BUY", "direction": "UP", "days": 2, "required": 3 }`.

## GET /gold/indicators

A summary list. It is the same as `global.components` plus each component's current value and changes.

```json
{
  "as_of": "2026-10-02T23:30:00Z",
  "indicators": [
    { "code": "REAL_YIELD", "name_code": "IND_REAL_YIELD", "value": 1.74, "unit": "pct",
      "changes": { "d1": -3, "d7": -11, "d30": -28 }, "change_unit": "bp",
      "trend": "FALLING", "impact": "BULLISH", "points": 20.04, "weight": 30, "tilt": 5.04,
      "observation_date": "2026-10-01", "age_bdays": 1, "status": "FRESH", "source": "mock" }
  ]
}
```

## GET /gold/indicators/{code}?range=1M|3M|1Y|5Y

```json
{
  "code": "REAL_YIELD",
  "value": 1.74, "unit": "pct",
  "changes": { "d1": -3, "d7": -11, "d30": -28 }, "change_unit": "bp",
  "trend": "FALLING", "impact": "BULLISH",
  "contribution": { "points": 20.04, "weight": 30, "tilt": 5.04, "s": 0.3358 },
  "sub_scores": [
    { "key": "d1",  "delta": -3,  "sigma": 5,  "z": 0.6,   "score": 0.1732, "weight": 0.2 },
    { "key": "d7",  "delta": -11, "sigma": 12, "z": 0.917, "score": 0.3215, "weight": 0.3 },
    { "key": "d30", "delta": -28, "sigma": 25, "z": 1.12,  "score": 0.4095, "weight": 0.5 }
  ],
  "series": [ ["2025-10-02", 1.86], ["2025-10-03", 1.84], ["…", 0], ["2026-10-01", 1.74] ],
  "observation_date": "2026-10-01", "age_bdays": 1, "status": "FRESH", "source": "mock"
}
```

Component-specific `extra` blocks:
- `FED`: `{"current_policy": {"target_lower": 3.50, "target_upper": 3.75, "effr": 3.58, "last_decision": {"date": "2026-09-16", "change_bp": -25}}, "market_implied": {"r3m": 3.55, "r6m": 3.40, "r12m": 3.18, "priced_12m_bp": -44.5, "method": "TBILL_PROXY"}}`
- `NOMINAL_10Y`: `{"nominal": 4.45, "real": 1.74, "breakeven": 2.71, "mean_252": 4.15, "std_252": 0.14, "z_level": 2.14}`
- `ECON`: `{"events": [ …same shape as /economic-events items, with "impact" and "decay"… ]}`
- `ETF`: `{"holdings_tonnes": {"GLD": 1012.4, "IAU": 488.1}, "changes_pct": {"d7": 0.35, "d30": 1.6, "d90": 2.9}}`
- `CENTRAL_BANKS`: `{"t12_tonnes": 780, "t3_tonnes": 165, "baseline_tonnes": 500, "monthly": [["2026-08", 52.0], …]}`
- `GRAM_TRY`: the `gram_gold` block from `/gold/current` plus the `fx_leg` block from `/gold/signal`.

## GET /gold/history?kind=GLOBAL&from=2026-01-01&to=2026-10-02&official=true

```json
{
  "kind": "GLOBAL", "model_version": "1.0.0",
  "points": [
    { "as_of_date": "2026-09-30", "score": 63.0, "signal": "BUY",  "raw_band": "BUY", "confidence": 63, "regime": "GOLD_BULL" },
    { "as_of_date": "2026-10-01", "score": 62.4, "signal": "BUY",  "raw_band": "BUY", "confidence": 64, "regime": "GOLD_BULL" },
    { "as_of_date": "2026-10-02", "score": 61.2, "signal": "BUY",  "raw_band": "BUY", "confidence": 68, "regime": "GOLD_BULL" }
  ]
}
```

## GET /economic-events?from=&to=&status=RELEASED|SCHEDULED|DELAYED&min_importance=0.5

```json
{
  "events": [
    { "id": 812, "code": "NFP", "reference_period": "2026-09", "unit": "thousands",
      "scheduled_at": "2026-10-02T12:30:00Z", "released_at": "2026-10-02T12:30:04Z", "status": "RELEASED",
      "previous": 22.0, "consensus": 100.0, "actual": 30.0, "surprise": -70.0, "surprise_z": -0.93,
      "gold_direction": -1, "importance": 1.0, "impact": 0.329, "impact_label": "BULLISH" },
    { "id": 815, "code": "ISM_SERVICES", "reference_period": "2026-09", "unit": "index",
      "scheduled_at": "2026-10-05T14:00:00Z", "released_at": null, "status": "SCHEDULED",
      "previous": 51.2, "consensus": 51.0, "actual": null, "surprise": null, "surprise_z": null,
      "gold_direction": -1, "importance": 0.5, "impact": null, "impact_label": null }
  ]
}
```

## GET /fed-expectations?from=&to=

```json
{
  "current_policy": { "target_lower": 3.50, "target_upper": 3.75, "midpoint": 3.625, "effr": 3.58,
                      "last_decision": { "date": "2026-09-16", "change_bp": -25 },
                      "next_meeting": "2026-10-28" },
  "market_implied": { "as_of_date": "2026-10-02", "method": "TBILL_PROXY",
                      "r3m": 3.55, "r6m": 3.40, "r12m": 3.18, "path_point": 3.29,
                      "priced_12m_bp": -44.5,
                      "path_change_bp": { "d1": -2, "d7": -9, "d30": -21 },
                      "p_cut_next": null, "p_hold_next": null, "p_hike_next": null },
  "history": [ { "as_of_date": "2026-09-02", "r3m": 3.68, "r6m": 3.58, "r12m": 3.42 } ]
}
```

## GET /backtest?start=2010-01-01&end=2026-09-30&capital=10000&cost_bps=10&mode=BINARY

The request is deterministic and cached by `request_sha256`. It runs synchronously, which takes about 1–2 s for 15 years of daily data.
> **The numbers below are placeholders showing the response shape. No backtest has been run yet.**
> An optional `"is_demo": true` marks synthetic demo output (Phase 1 fixture). Real results omit it or send `false`,
> and clients must show a "not a historical result" banner whenever it is true.

```json
{
  "model_version": "1.0.0", "params_sha256": "<64 hex>",
  "request": { "start": "2010-01-01", "end": "2026-09-30", "capital": 10000, "cost_bps": 10, "mode": "BINARY",
               "execution": "NEXT_CLOSE", "cash_yield": "US_TBILL_3M" },
  "strategy":  { "final_value": 0, "total_return_pct": 0, "cagr_pct": 0, "max_drawdown_pct": 0,
                 "trades": 0, "win_rate_pct": 0, "avg_gain_pct": 0, "avg_loss_pct": 0,
                 "best_trade_pct": 0, "worst_trade_pct": 0, "time_invested_pct": 0, "sharpe": 0 },
  "buy_and_hold": { "final_value": 0, "total_return_pct": 0, "cagr_pct": 0, "max_drawdown_pct": 0, "sharpe": 0 },
  "equity_curve": [ ["2010-01-08", 10000, 10000] ],
  "trades_list": [ { "entry_date": "…", "entry_price": 0, "exit_date": "…", "exit_price": 0,
                     "return_pct": 0, "days": 0, "entry_signal": "BUY", "exit_signal": "REDUCE" } ],
  "data_coverage": { "REAL_YIELD": 1.0, "FED": 1.0, "DXY": 1.0, "NOMINAL_10Y": 1.0,
                     "ECON": 0.69, "ETF": 1.0, "CENTRAL_BANKS": 1.0 },
  "warnings": [ { "code": "COVERAGE_GAP", "params": { "component": "ECON", "neutral_days_pct": 31 } } ]
}
```

## GET /alerts?since_id=0&limit=50

```json
{
  "alerts": [
    { "id": 431, "type": "SIGNAL_CHANGED", "kind": "GLOBAL", "created_at": "2026-09-25T23:30:05Z",
      "payload": { "from": "HOLD", "to": "BUY", "score_from": 56.0, "score_to": 72.0,
                   "main_reason": { "code": "REAL_YIELD_FALLING", "magnitude": "SHARP", "params": { "d30_bp": -41 } },
                   "supporting": [ "DXY_FALLING", "FED_PATH_LOWER" ] } },
    { "id": 432, "type": "MACRO_RELEASE", "kind": null, "created_at": "2026-10-02T12:31:00Z",
      "payload": { "event_id": 812, "code": "NFP", "actual": 30.0, "consensus": 100.0, "surprise": -70.0, "impact_label": "BULLISH" } }
  ],
  "next_since_id": 432
}
```

## GET /meta/model

`{ "version": "1.0.0", "params_sha256": "…", "frozen_at": null, "params": { …02_SCORING_MODEL_V1.md constants… } }`

## GET /health/data

```json
{
  "data_status": "OK",
  "sources": [
    { "code": "mock", "kind": "MOCK", "last_success_at": "2026-10-02T23:29:41Z", "last_error": null }
  ],
  "series": [
    { "code": "US_REAL_10Y", "status": "MOCK", "last_observation": "2026-10-01", "age_bdays": 1, "critical": true }
  ],
  "open_issues": []
}
```

---

## Kotlin DTO sketch (Android contract)

```kotlin
@Serializable enum class SignalLabel { STRONG_BUY, BUY, HOLD, REDUCE, SELL }
@Serializable enum class Regime { GOLD_BULL, GOLD_BEAR, TRANSITION, PANIC }
@Serializable enum class DataStatus { OK, DEGRADED, DELAYED }

@Serializable data class Reason(val code: String, val magnitude: String? = null,
                                val params: Map<String, JsonPrimitive> = emptyMap())
@Serializable data class Explanation(val headline: Reason, val positive: List<Reason>, val neutral: List<Reason>,
                                     val negative: List<Reason>, val warnings: List<Reason>, val conclusion: Reason)
@Serializable data class ComponentDto(val code: String, val weight: Int, val s: Double, val freshness: Double,
                                      val points: Double, val tilt: Double, val impact: String, val status: String)
@Serializable data class PendingDto(val signal: SignalLabel, val direction: String, val days: Int, val required: Int)
@Serializable data class GlobalSignalDto(
    val score: Double, @SerialName("raw_band") val rawBand: SignalLabel, val signal: SignalLabel,
    @SerialName("previous_signal") val previousSignal: SignalLabel?, @SerialName("signal_since") val signalSince: String,
    val pending: PendingDto?, val confidence: Int, val regime: Regime,
    val components: List<ComponentDto>, val explanation: Explanation)
@Serializable data class SignalResponse(
    @SerialName("model_version") val modelVersion: String, @SerialName("evaluated_at") val evaluatedAt: Instant,
    @SerialName("data_status") val dataStatus: DataStatus, val global: GlobalSignalDto,
    @SerialName("gram_try") val gramTry: GramSignalDto)
```
