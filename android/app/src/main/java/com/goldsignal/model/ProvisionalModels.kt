package com.goldsignal.model

import kotlinx.serialization.Serializable

/** /gold/provisional: intraday score on live quotes. Never changes the official signal. */
@Serializable
data class ProvisionalResponse(
    val asOf: String,
    val quotesAsOf: String? = null,
    val marketOpen: Boolean = false,
    val movedInputs: List<String> = emptyList(),
    val score: Double,
    val rawBand: SignalLabel,
    val gramScore: Double,
    val gramRawBand: SignalLabel,
    val panicTrigger: Boolean = false,
    val components: List<ProvisionalComponent> = emptyList(),
    val official: OfficialRef,
    val modelVersion: String,
)

@Serializable
data class ProvisionalComponent(val code: String, val points: Double, val s: Double, val status: String)

@Serializable
data class OfficialRef(
    val asOfDate: String? = null,
    val score: Double? = null,
    val signal: SignalLabel? = null,
    val gramSignal: SignalLabel? = null,
    val nextOfficialEvaluation: String? = null,
)
