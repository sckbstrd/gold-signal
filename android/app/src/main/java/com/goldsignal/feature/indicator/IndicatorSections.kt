package com.goldsignal.feature.indicator

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.goldsignal.R
import com.goldsignal.core.designsystem.BarChart
import com.goldsignal.core.designsystem.ChartLine
import com.goldsignal.core.designsystem.HorizonCells
import com.goldsignal.core.designsystem.InfoNote
import com.goldsignal.core.designsystem.KeyValueRow
import com.goldsignal.core.designsystem.Legend
import com.goldsignal.core.designsystem.LineChart
import com.goldsignal.core.designsystem.LocalSignalColors
import com.goldsignal.core.designsystem.SectionCard
import com.goldsignal.core.designsystem.SignalBadge
import com.goldsignal.core.designsystem.Tabular
import com.goldsignal.core.designsystem.formatScore
import com.goldsignal.core.format.Fmt
import com.goldsignal.core.i18n.calendarDays
import com.goldsignal.core.i18n.eventName
import com.goldsignal.core.i18n.eventUnitIsPercent
import com.goldsignal.core.i18n.eventUnitIsThousands
import com.goldsignal.core.i18n.impactText
import com.goldsignal.data.AppJson
import com.goldsignal.model.CentralBankExtra
import com.goldsignal.model.EconExtra
import com.goldsignal.model.FedExtra
import com.goldsignal.model.GramExtra
import com.goldsignal.model.IndicatorDetail
import com.goldsignal.model.NominalExtra
import com.goldsignal.model.SeriesPoint
import kotlinx.serialization.json.decodeFromJsonElement
import kotlinx.serialization.json.jsonObject

private inline fun <reified T> IndicatorDetail.extraAs(): T? =
    runCatching { AppJson.decodeFromJsonElement<T>(extra) }.getOrNull()

// ------------------------------------------------------------------ Fed

@Composable
fun FedSections(d: IndicatorDetail, f: Fmt) {
    val x = d.extraAs<FedExtra>() ?: return
    val p = x.currentPolicy
    val m = x.marketImplied
    SectionCard(title = stringResource(R.string.fed_current_title)) {
        KeyValueRow(stringResource(R.string.fed_target_range), "${f.rate(p.targetLower)} – ${f.rate(p.targetUpper)}")
        p.effr?.let { KeyValueRow(stringResource(R.string.fed_effr), f.rate(it)) }
        p.lastDecision?.let {
            KeyValueRow(stringResource(R.string.fed_last_decision), "${f.date(it.date)} · ${f.bp(it.changeBp.toDouble())}")
        }
    }
    SectionCard(title = stringResource(R.string.fed_implied_title)) {
        m.r3m?.let { KeyValueRow(stringResource(R.string.fed_in_3m), f.rate(it)) }
        m.r6m?.let { KeyValueRow(stringResource(R.string.fed_in_6m), f.rate(it)) }
        m.r12m?.let { KeyValueRow(stringResource(R.string.fed_in_12m), f.rate(it)) }
        m.priced12mBp?.let {
            val amount = "${f.num(kotlin.math.abs(it), 0)} ${if (f.locale.language == "ru") "б.п." else "bp"}"
            KeyValueRow(
                stringResource(R.string.fed_priced),
                stringResource(if (it < 0) R.string.bp_cuts else R.string.bp_hikes, amount),
                valueColor = if (it < 0) LocalSignalColors.current.bullish else LocalSignalColors.current.bearish,
            )
        }
        InfoNote(stringResource(R.string.fed_method_tbill))
        val implied = d.extra["implied_series"]?.jsonObject
        if (implied != null) {
            val series = listOf("r3m", "r6m", "r12m").mapNotNull { k ->
                implied[k]?.let { AppJson.decodeFromJsonElement<List<SeriesPoint>>(it) }
            }
            if (series.size == 3) {
                val colors = listOf(MaterialTheme.colorScheme.outline, MaterialTheme.colorScheme.secondary,
                    MaterialTheme.colorScheme.primary)
                val pts = series.map { it.lastDays(366) }
                LineChart(
                    lines = pts.mapIndexed { i, s -> ChartLine(s.map { it.value }, colors[i]) },
                    startLabel = f.axisDate(pts[0].first().date, 366), endLabel = f.axisDate(pts[0].last().date, 366),
                    formatY = { f.rate(it) }, reference = p.midpoint,
                )
                Legend(listOf(stringResource(R.string.fed_in_3m) to colors[0], stringResource(R.string.fed_in_6m) to colors[1],
                    stringResource(R.string.fed_in_12m) to colors[2]))
            }
        }
    }
    InfoNote(stringResource(R.string.fed_not_confuse))
}

// ------------------------------------------------------------------ Nominal 10Y

@Composable
fun NominalSections(d: IndicatorDetail, f: Fmt) {
    val x = d.extraAs<NominalExtra>() ?: return
    SectionCard(title = stringResource(R.string.nom_decomposition)) {
        KeyValueRow(stringResource(R.string.nom_nominal), f.rate(x.nominal))
        x.real?.let { KeyValueRow(stringResource(R.string.nom_real), f.rate(it)) }
        x.breakeven?.let { KeyValueRow(stringResource(R.string.nom_breakeven), f.rate(it)) }
        x.mean252?.let { KeyValueRow(stringResource(R.string.nom_avg), f.rate(it)) }
        x.zLevel?.let { KeyValueRow(stringResource(R.string.nom_z), f.signed(it, 2)) }
        if (x.realSeries.size > 2 && x.breakevenSeries.size > 2) {
            val nom = d.series.lastDays(366)
            val real = x.realSeries.lastDays(366)
            val be = x.breakevenSeries.lastDays(366)
            val c = listOf(MaterialTheme.colorScheme.primary, MaterialTheme.colorScheme.secondary, MaterialTheme.colorScheme.outline)
            LineChart(
                lines = listOf(ChartLine(nom.map { it.value }, c[0]), ChartLine(real.map { it.value }, c[1]),
                    ChartLine(be.map { it.value }, c[2], dashed = true)),
                startLabel = f.axisDate(nom.first().date, 366), endLabel = f.axisDate(nom.last().date, 366),
                formatY = { f.rate(it) },
            )
            Legend(listOf(stringResource(R.string.nom_nominal) to c[0], stringResource(R.string.nom_real) to c[1],
                stringResource(R.string.nom_breakeven) to c[2]))
        }
        InfoNote(stringResource(R.string.nom_dedup_note))
    }
}

// ------------------------------------------------------------------ Economic data

@Composable
fun EconSections(d: IndicatorDetail, f: Fmt) {
    val x = d.extraAs<EconExtra>() ?: return
    val sc = LocalSignalColors.current
    SectionCard(title = stringResource(R.string.econ_recent)) {
        x.events.forEachIndexed { i, e ->
            if (i > 0) HorizontalDivider()
            Row(Modifier.fillMaxWidth()) {
                Column(Modifier.weight(1f)) {
                    Text(eventName(e.code), style = MaterialTheme.typography.bodyMedium, fontWeight = FontWeight.Medium)
                    Text("${e.referencePeriod} · ${f.date(e.releasedAt)}", style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
                val label = if (e.impact >= 0.05) "BULLISH" else if (e.impact <= -0.05) "BEARISH" else "NEUTRAL"
                Text(impactText(label), style = MaterialTheme.typography.labelMedium, color = sc.impact(label))
            }
            HorizonCells(
                listOf(
                    stringResource(R.string.econ_actual) to eventValue(e.code, e.actual, f),
                    stringResource(R.string.econ_expected) to eventValue(e.code, e.consensus, f),
                    stringResource(R.string.econ_surprise) to eventValue(e.code, e.surprise, f, signed = true),
                ),
                listOf(MaterialTheme.colorScheme.onSurface, MaterialTheme.colorScheme.onSurface,
                    if (e.weighted > 0) sc.bullish else if (e.weighted < 0) sc.bearish else sc.neutral),
            )
        }
        x.delayed.forEach {
            Text("${eventName(it.code)} · ${stringResource(R.string.econ_delayed)}", color = sc.warning,
                style = MaterialTheme.typography.labelLarge)
        }
        InfoNote(stringResource(R.string.econ_note))
    }
}

fun eventValue(code: String, v: Double?, f: Fmt, signed: Boolean = false): String {
    if (v == null) return "—"
    return when {
        eventUnitIsPercent(code) -> if (signed) f.signed(v, 1) + " pp" else f.pct(v, 1, signed = false)
        eventUnitIsThousands(code) -> (if (signed) f.signed(v, 0) else f.num(v, 0)) + "K"
        else -> if (signed) f.signed(v, 1) else f.num(v, 1)
    }
}

// ------------------------------------------------------------------ Central banks

@Composable
fun CentralBankSections(d: IndicatorDetail, f: Fmt) {
    val x = d.extraAs<CentralBankExtra>() ?: return
    SectionCard {
        KeyValueRow(stringResource(R.string.cb_t12), f.tonnes(x.t12Tonnes))
        KeyValueRow(stringResource(R.string.cb_t3), f.tonnes(x.t3Tonnes))
        KeyValueRow(stringResource(R.string.cb_baseline), f.tonnes(x.baselineTonnes))
        if (x.monthly.isNotEmpty()) {
            BarChart(
                values = x.monthly.map { it.tonnes },
                labels = x.monthly.map { f.monthYear(it.month) },
                color = MaterialTheme.colorScheme.primary,
                reference = x.baselineTonnes / 12,
            )
        }
        InfoNote(stringResource(R.string.cb_note))
    }
}

// ------------------------------------------------------------------ Gram gold

@Composable
fun GramSections(d: IndicatorDetail, f: Fmt) {
    val x = d.extraAs<GramExtra>() ?: return
    val gramSignal = d.extra["gram_signal"]?.let {
        runCatching { AppJson.decodeFromJsonElement<GramSignalLite>(it) }.getOrNull()
    }
    val sc = LocalSignalColors.current
    SectionCard {
        Text(stringResource(R.string.gram_theoretical), style = MaterialTheme.typography.labelMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant)
        Text(f.tryAmount(x.gram.theoreticalTry), style = MaterialTheme.typography.displayMedium)
        HorizonCells(
            listOf("d1", "d7", "d30").map { k ->
                horizonLabel(k) to (when (k) { "d1" -> x.gram.changePct.d1; "d7" -> x.gram.changePct.d7; else -> x.gram.changePct.d30 }
                    ?.let { f.pct(it) } ?: "—")
            },
            emptyList(),
        )
        Text(stringResource(R.string.gram_formula), style = MaterialTheme.typography.bodySmall.merge(Tabular),
            color = MaterialTheme.colorScheme.onSurfaceVariant)
        KeyValueRow(stringResource(R.string.gram_usdtry), x.fxLeg.usdtry?.let { f.num(it, 4) } ?: "—")
        KeyValueRow(stringResource(R.string.gram_market),
            x.gram.marketTry?.let { f.tryAmount(it) } ?: stringResource(R.string.gram_market_na))
        if (gramSignal != null) {
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                Text(stringResource(R.string.gram_gold_signal), style = MaterialTheme.typography.labelLarge,
                    modifier = Modifier.weight(1f))
                SignalBadge(gramSignal.signal)
                Text(formatScore(gramSignal.score), style = MaterialTheme.typography.labelLarge.merge(Tabular))
            }
        }
    }
    if (d.series.size > 2) {
        var range by rememberSaveable { mutableIntStateOf(2) }
        val pts = d.series.lastDays(listOf(30L, 91L, 366L)[range])
        SectionCard {
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                listOf(R.string.chart_1m, R.string.chart_3m, R.string.chart_1y).forEachIndexed { i, res ->
                    androidx.compose.material3.FilterChip(range == i, { range = i }, { Text(stringResource(res)) })
                }
            }
            LineChart(listOf(ChartLine(pts.map { it.value }, MaterialTheme.colorScheme.primary)),
                f.axisDate(pts.first().date, listOf(30L, 91L, 366L)[range]), f.axisDate(pts.last().date, listOf(30L, 91L, 366L)[range]), { f.tryAmount(it) })
        }
    }
    SectionCard(title = stringResource(R.string.gram_decomp_title)) {
        x.gram.decomposition30dPct.gold?.let { KeyValueRow(stringResource(R.string.gram_decomp_gold), f.pct(it)) }
        x.gram.decomposition30dPct.usdtry?.let { KeyValueRow(stringResource(R.string.gram_usdtry), f.pct(it)) }
        x.gram.changePct.d30?.let {
            KeyValueRow(stringResource(R.string.comp_gram), f.pct(it), valueColor = if (it >= 0) sc.bullish else sc.bearish)
        }
    }
    SectionCard(title = stringResource(R.string.gram_fx_leg_title)) {
        val fx = x.fxLeg
        HorizonCells(
            listOf(
                stringResource(R.string.gram_fx_move) to (fx.usdtryChangePct?.d30?.let { f.pct(it) } ?: "—"),
                stringResource(R.string.gram_carry) to (fx.carryPct?.d30?.let { f.pct(it) } ?: "—"),
                stringResource(R.string.gram_excess) to (fx.excessPct?.d30?.let { f.pct(it) } ?: "—"),
            ),
            listOf(MaterialTheme.colorScheme.onSurface, MaterialTheme.colorScheme.onSurface,
                fx.excessPct?.d30?.let { if (it > 0) sc.bullish else if (it < 0) sc.bearish else sc.neutral }
                    ?: MaterialTheme.colorScheme.onSurface),
        )
        Text(stringResource(R.string.label_30d_window, calendarDays(30)), style = MaterialTheme.typography.labelSmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant)
        if (fx.iTryPct != null && fx.iUsdPct != null) {
            Text(stringResource(R.string.gram_policy_rates, f.rate(fx.iTryPct), f.rate(fx.iUsdPct, 3)),
                style = MaterialTheme.typography.bodySmall)
        }
        Text(stringResource(R.string.gram_tilt, f.signed(fx.tiltPoints, 1), f.num(fx.maxTilt, 0)),
            style = MaterialTheme.typography.bodyMedium, fontWeight = FontWeight.Medium)
        InfoNote(stringResource(R.string.gram_carry_note))
    }
    InfoNote(stringResource(R.string.gram_two_drivers))
}

@kotlinx.serialization.Serializable
private data class GramSignalLite(val score: Double, val signal: com.goldsignal.model.SignalLabel)
