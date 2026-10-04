package com.goldsignal.model

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.double
import kotlinx.serialization.json.int
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonPrimitive

/** /gold/history: compact rows; [columns] names each position. */
@Serializable
data class HistoryResponse(val modelVersion: String, val columns: List<String>, val points: List<JsonArray>) {
    fun rows(): List<HistoryPoint> {
        val ix = columns.withIndex().associate { it.value to it.index }
        fun JsonArray.s(name: String) = this[ix.getValue(name)].jsonPrimitive.contentOrNull
        return points.map { p ->
            HistoryPoint(
                date = p.s("date")!!,
                score = p[ix.getValue("score")].jsonPrimitive.double,
                signal = p.s("signal")!!,
                rawBand = p.s("raw_band")!!,
                confidence = p[ix.getValue("confidence")].jsonPrimitive.int,
                regime = p.s("regime")!!,
                gramScore = p[ix.getValue("gram_score")].jsonPrimitive.double,
                gramSignal = p.s("gram_signal")!!,
                origin = p.s("origin")!!,
                missing = ix["missing"]?.let { i -> p[i].jsonArray.map { (it as JsonPrimitive).content } } ?: emptyList(),
            )
        }
    }
}

data class HistoryPoint(
    val date: String,
    val score: Double,
    val signal: String,
    val rawBand: String,
    val confidence: Int,
    val regime: String,
    val gramScore: Double,
    val gramSignal: String,
    val origin: String,
    val missing: List<String>,
)

@Serializable
data class ScoreStats(val mean: Double, val p10: Double, val p50: Double, val p90: Double, val min: Double, val max: Double)

@Serializable
data class YearStats(val days: Int, val meanScore: Double, val buyShare: Double, val sellShare: Double, val signalChanges: Int)

@Serializable
data class HistoryReport(
    val modelVersion: String,
    val firstDate: String? = null,
    val lastDate: String? = null,
    val days: Int = 0,
    val originShare: Map<String, Double> = emptyMap(),
    val signalShare: Map<String, Double> = emptyMap(),
    val rawBandShare: Map<String, Double> = emptyMap(),
    val regimeShare: Map<String, Double> = emptyMap(),
    val gramSignalShare: Map<String, Double> = emptyMap(),
    val signalChanges: Int = 0,
    val changesPerYear: Double = 0.0,
    val meanRunDays: Double = 0.0,
    val score: ScoreStats? = null,
    val componentCoverage: Map<String, Double> = emptyMap(),
    val byYear: Map<String, YearStats> = emptyMap(),
    val notes: List<String> = emptyList(),
)

// ------------------------------------------------------------------ /health/data

@Serializable
data class SourceHealth(
    val code: String,
    val name: String,
    val kind: String,
    val lastSuccessAt: String? = null,
    val lastErrorAt: String? = null,
    val lastError: String? = null,
    val rowsLastRun: Int = 0,
)

@Serializable
data class SeriesHealth(
    val code: String,
    val source: String,
    val firstObservation: String? = null,
    val lastObservation: String? = null,
    val ageBdays: Int? = null,
    val status: String,
)

@Serializable
data class HealthResponse(
    val generatedAt: String,
    val dataStatus: String? = null,
    val sources: List<SourceHealth> = emptyList(),
    val series: List<SeriesHealth> = emptyList(),
    @SerialName("latest_official_date") val latestOfficialDate: String? = null,
    val signalOverdue: Boolean = false,
)
