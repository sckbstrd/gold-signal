package com.goldsignal.model

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive

/*
 * Typed mirror of the REST contract (docs/04_API.md). JSON is snake_case; the shared
 * Json instance applies JsonNamingStrategy.SnakeCase, so only names containing digits
 * need an explicit @SerialName.
 */

@Serializable
enum class SignalLabel { STRONG_BUY, BUY, HOLD, REDUCE, SELL }

@Serializable
enum class Regime { GOLD_BULL, GOLD_BEAR, TRANSITION, PANIC }

@Serializable
enum class DataStatus { OK, DEGRADED, DELAYED }

/** A localizable explanation item: the device renders [code] + [params] in EN/TR/RU. */
@Serializable
data class Reason(
    val code: String,
    val magnitude: String? = null,
    val params: Map<String, JsonPrimitive> = emptyMap(),
)

@Serializable
data class Explanation(
    val headline: Reason,
    val positive: List<Reason> = emptyList(),
    val neutral: List<Reason> = emptyList(),
    val negative: List<Reason> = emptyList(),
    val warnings: List<Reason> = emptyList(),
    val conclusion: Reason,
)

@Serializable
data class Pending(val signal: SignalLabel, val direction: String, val days: Int, val required: Int)

@Serializable
data class RegimePending(val regime: Regime, val days: Int, val required: Int)

@Serializable
data class ComponentSummary(
    val code: String,
    val weight: Double,
    val s: Double,
    val freshness: Double,
    val points: Double,
    val tilt: Double,
    val impact: String,
    val status: String,
)

@Serializable
data class GlobalSignal(
    val score: Double,
    val rawBand: SignalLabel,
    val signal: SignalLabel,
    val previousSignal: SignalLabel? = null,
    val signalSince: String? = null,
    val pending: Pending? = null,
    val confidence: Int,
    val confidenceParts: Map<String, Double> = emptyMap(),
    val regime: Regime,
    val regimePending: RegimePending? = null,
    val components: List<ComponentSummary>,
    val explanation: Explanation,
)

@Serializable
data class HorizonMap(val d1: Double? = null, val d7: Double? = null, val d30: Double? = null)

@Serializable
data class FxLeg(
    val s: Double,
    val freshness: Double,
    val status: String,
    val ageBdays: Int? = null,
    val usdtry: Double? = null,
    val observationDate: String? = null,
    val usdtryChangePct: HorizonMap? = null,
    val carryPct: HorizonMap? = null,
    val excessPct: HorizonMap? = null,
    val iTryPct: Double? = null,
    val iUsdPct: Double? = null,
    val tiltPoints: Double = 0.0,
    val maxTilt: Double = 25.0,
)

@Serializable
data class GramSignal(
    val score: Double,
    val rawBand: SignalLabel,
    val signal: SignalLabel,
    val previousSignal: SignalLabel? = null,
    val signalSince: String? = null,
    val pending: Pending? = null,
    val confidence: Int,
    val globalScore: Double,
    val fxLeg: FxLeg,
    val explanation: Explanation,
)

@Serializable
data class SignalResponse(
    val modelVersion: String,
    val paramsSha256: String? = null,
    val evaluatedAt: String,
    val asOfDate: String,
    val isOfficial: Boolean,
    val nextOfficialEvaluation: String? = null,
    val dataStatus: DataStatus,
    val global: GlobalSignal,
    val gramTry: GramSignal,
    val disclaimerCode: String,
)

// ------------------------------------------------------------------ /gold/current

@Serializable
data class GoldQuote(
    val symbol: String,
    val priceUsd: Double,
    val observedAt: String,
    val changePct: HorizonMap,
    @SerialName("high_52w") val high52w: Double,
    @SerialName("high_52w_date") val high52wDate: String,
    val distanceFromHighPct: Double,
    val status: String,
    val source: String,
    val series: List<SeriesPoint> = emptyList(),
)

@Serializable
data class FxQuote(val rate: Double, val observedAt: String, val changePct: HorizonMap, val status: String, val source: String)

@Serializable
data class Decomposition(val gold: Double? = null, val usdtry: Double? = null)

@Serializable
data class GramGold(
    val theoreticalTry: Double,
    val formula: String,
    val changePct: HorizonMap,
    @SerialName("decomposition_30d_pct") val decomposition30dPct: Decomposition,
    val marketTry: Double? = null,
    val marketPremiumPct: Double? = null,
    val marketSource: String? = null,
)

@Serializable
data class CurrentResponse(
    val asOf: String,
    val gold: GoldQuote,
    val usdtry: FxQuote,
    val gramGold: GramGold,
    val dataStatus: DataStatus,
)

// ------------------------------------------------------------------ indicators

/** ["2026-10-01", 1.74] in JSON. */
@Serializable(with = SeriesPointSerializer::class)
data class SeriesPoint(val date: String, val value: Double)

@Serializable
data class SubScore(
    val key: String,
    val delta: Double? = null,
    val sigma: Double? = null,
    val z: Double? = null,
    val score: Double,
    val weight: Double,
    val missing: Boolean = false,
)

@Serializable
data class Contribution(
    val points: Double,
    val weight: Double,
    val tilt: Double,
    val s: Double,
    val freshness: Double? = null,
    val sEff: Double? = null,
)

@Serializable
data class IndicatorDetail(
    val code: String,
    val value: Double? = null,
    val unit: String? = null,
    val changes: Map<String, Double?> = emptyMap(),
    val changeUnit: String? = null,
    val trend: String? = null,
    val impact: String? = null,
    val contribution: Contribution,
    val subScores: List<SubScore> = emptyList(),
    val series: List<SeriesPoint> = emptyList(),
    val observationDate: String? = null,
    val ageBdays: Int? = null,
    val status: String,
    val source: String,
    val extra: JsonObject = JsonObject(emptyMap()),
)

// Typed views of IndicatorDetail.extra (decoded on demand, per indicator code).

@Serializable
data class FedDecision(val date: String, val changeBp: Int)

@Serializable
data class CurrentPolicy(
    val targetLower: Double,
    val targetUpper: Double,
    val midpoint: Double,
    val effr: Double? = null,
    val lastDecision: FedDecision? = null,
)

@Serializable
data class MarketImplied(
    val method: String,
    val r3m: Double? = null,
    val r6m: Double? = null,
    val r12m: Double? = null,
    val pathPoint: Double? = null,
    @SerialName("priced_12m_bp") val priced12mBp: Double? = null,
)

@Serializable
data class FedExtra(
    val currentPolicy: CurrentPolicy,
    val marketImplied: MarketImplied,
    val repricing: Double? = null,
    val stance: Double? = null,
)

@Serializable
data class NominalExtra(
    val nominal: Double,
    val real: Double? = null,
    val breakeven: Double? = null,
    @SerialName("mean_252") val mean252: Double? = null,
    @SerialName("std_252") val std252: Double? = null,
    val zLevel: Double? = null,
    val bePart: Double? = null,
    val levelPart: Double? = null,
    val breakevenSeries: List<SeriesPoint> = emptyList(),
    val realSeries: List<SeriesPoint> = emptyList(),
)

@Serializable
data class ScoredEvent(
    val code: String,
    val referencePeriod: String,
    val releasedAt: String,
    val previous: Double? = null,
    val consensus: Double? = null,
    val actual: Double? = null,
    val surprise: Double,
    val surpriseZ: Double,
    val importance: Double,
    val goldDirection: Int,
    val impact: Double,
    val decay: Double,
    val weighted: Double,
)

@Serializable
data class DelayedRelease(val code: String, val referencePeriod: String, val scheduledAt: String)

@Serializable
data class EconExtra(val events: List<ScoredEvent> = emptyList(), val delayed: List<DelayedRelease> = emptyList())

@Serializable(with = MonthValueSerializer::class)
data class MonthValue(val month: String, val tonnes: Double)

@Serializable
data class CentralBankExtra(
    @SerialName("t12_tonnes") val t12Tonnes: Double,
    @SerialName("t3_tonnes") val t3Tonnes: Double,
    val baselineTonnes: Double,
    val published: String? = null,
    val monthly: List<MonthValue> = emptyList(),
)

@Serializable
data class GramExtra(val gram: GramGold, val fxLeg: FxLeg)

// ------------------------------------------------------------------ events

@Serializable
data class EconomicEvent(
    val id: Long,
    val code: String,
    val referencePeriod: String,
    val scheduledAt: String,
    val releasedAt: String? = null,
    val status: String,
    val previous: Double? = null,
    val consensus: Double? = null,
    val actual: Double? = null,
    val surprise: Double? = null,
    val surpriseZ: Double? = null,
    val goldDirection: Int? = null,
    val importance: Double? = null,
    val impact: Double? = null,
    val impactLabel: String? = null,
)

@Serializable
data class EventsResponse(val events: List<EconomicEvent>)

// ------------------------------------------------------------------ backtest

@Serializable
data class BacktestRequestEcho(
    val start: String,
    val end: String,
    val capital: Double,
    val costBps: Double,
    val mode: String,
    val execution: String,
    val cashYield: String,
)

@Serializable
data class PerformanceMetrics(
    val finalValue: Double,
    val totalReturnPct: Double,
    val cagrPct: Double,
    val maxDrawdownPct: Double,
    val sharpe: Double? = null,
    val trades: Int? = null,
    val closedTrades: Int? = null,
    val winRatePct: Double? = null,
    val avgGainPct: Double? = null,
    val avgLossPct: Double? = null,
    val bestTradePct: Double? = null,
    val worstTradePct: Double? = null,
    val timeInvestedPct: Double? = null,
)

@Serializable(with = EquityPointSerializer::class)
data class EquityPoint(val date: String, val strategy: Double, val benchmark: Double)

@Serializable
data class BacktestTrade(
    val entryDate: String,
    val entryPrice: Double,
    val exitDate: String? = null,
    val exitPrice: Double,
    val returnPct: Double,
    val days: Int,
    val entrySignal: String,
    val exitSignal: String? = null,
)

@Serializable
data class BacktestResponse(
    val isDemo: Boolean = false,
    val modelVersion: String,
    val paramsSha256: String? = null,
    val request: BacktestRequestEcho,
    val strategy: PerformanceMetrics,
    val buyAndHold: PerformanceMetrics,
    val equityCurve: List<EquityPoint>,
    val tradesList: List<BacktestTrade>,
    val dataCoverage: Map<String, Double> = emptyMap(),
    val warnings: List<Reason> = emptyList(),
)

data class BacktestRequest(val start: String, val end: String, val capital: Double, val costBps: Double)

/** Convenience accessors for reason params. */
fun Reason.num(key: String): Double? = params[key]?.content?.toDoubleOrNull()
fun Reason.str(key: String): String? = params[key]?.let { if (it.isString) it.content else it.content.takeIf { c -> c != "null" } }
