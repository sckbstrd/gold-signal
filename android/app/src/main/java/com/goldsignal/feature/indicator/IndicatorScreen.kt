package com.goldsignal.feature.indicator

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.material3.FilterChip
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.goldsignal.R
import com.goldsignal.core.designsystem.ChartLine
import com.goldsignal.core.designsystem.Disclaimer
import com.goldsignal.core.designsystem.ErrorBox
import com.goldsignal.core.designsystem.HorizonCells
import com.goldsignal.core.designsystem.InfoNote
import com.goldsignal.core.designsystem.LineChart
import com.goldsignal.core.designsystem.LoadingBox
import com.goldsignal.core.designsystem.LocalSignalColors
import com.goldsignal.core.designsystem.SectionCard
import com.goldsignal.core.designsystem.Tabular
import com.goldsignal.core.format.Fmt
import com.goldsignal.core.format.rememberFmt
import com.goldsignal.core.i18n.businessDays
import com.goldsignal.core.i18n.componentName
import com.goldsignal.core.i18n.eventName
import com.goldsignal.core.i18n.impactText
import com.goldsignal.core.i18n.statusText
import com.goldsignal.core.i18n.trendText
import com.goldsignal.core.ui.UiState
import com.goldsignal.core.ui.loadViewModel
import com.goldsignal.model.IndicatorDetail
import com.goldsignal.model.SeriesPoint
import com.goldsignal.model.SubScore
import com.goldsignal.ui.ScreenScaffold
import java.time.LocalDate

@Composable
fun IndicatorScreen(code: String, onBack: () -> Unit) {
    val vm = loadViewModel("indicator-$code") { indicator(code) }
    val state by vm.state.collectAsStateWithLifecycle()
    ScreenScaffold(title = componentName(code), onBack = onBack, scrollable = state is UiState.Ready) {
        when (val s = state) {
            UiState.Loading -> LoadingBox()
            is UiState.Failed -> ErrorBox(s.message, vm::refresh)
            is UiState.Ready -> IndicatorContent(s.data)
        }
    }
}

@Composable
private fun IndicatorContent(d: IndicatorDetail) {
    val f = rememberFmt()
    if (d.code == "GRAM_TRY") {
        GramSections(d, f)
    } else {
        HeaderCard(d, f)
        if (d.series.isNotEmpty()) ChartCard(d, f)
        when (d.code) {
            "FED" -> FedSections(d, f)
            "NOMINAL_10Y" -> NominalSections(d, f)
            "ECON" -> EconSections(d, f)
            "CENTRAL_BANKS" -> CentralBankSections(d, f)
            else -> Unit
        }
        ScoringCard(d, f)
    }
    DataAgeLine(d, f)
    Disclaimer(null)
}

@Composable
private fun HeaderCard(d: IndicatorDetail, f: Fmt) {
    val sc = LocalSignalColors.current
    SectionCard {
        if (d.value != null) {
            // For FED the headline value is the market-implied path, never the current policy rate.
            Text(stringResource(if (d.code == "FED") R.string.fed_path_value else R.string.current_value),
                style = MaterialTheme.typography.labelMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant)
            Text(valueText(d.code, d.unit, d.value, f), style = MaterialTheme.typography.displayMedium)
        }
        val horizons = d.changes.entries.filter { it.value != null }
        if (horizons.isNotEmpty()) {
            HorizonCells(
                horizons.map { (k, v) -> horizonLabel(k) to changeText(d.changeUnit, v!!, f) },
                horizons.map { (_, v) -> directionColor(d.code, v!!) },
            )
        }
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
            if (d.trend != null && d.code != "ECON" && d.code != "CENTRAL_BANKS") {
                LabeledValue(stringResource(R.string.trend_label), trendText(d.trend))
            }
            LabeledValue(stringResource(R.string.gold_impact), impactText(d.impact), sc.impact(d.impact))
        }
        HorizontalDivider()
        Text(stringResource(R.string.contribution), style = MaterialTheme.typography.labelMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant)
        Text(
            stringResource(
                R.string.contribution_value, f.num(d.contribution.points, 1), f.num(d.contribution.weight, 0),
                f.signed(d.contribution.tilt, 1),
            ),
            style = MaterialTheme.typography.titleMedium.merge(Tabular),
            color = sc.impact(d.impact),
        )
    }
}

@Composable
private fun LabeledValue(label: String, value: String, color: androidx.compose.ui.graphics.Color = androidx.compose.ui.graphics.Color.Unspecified) {
    Column {
        Text(label, style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Text(value, style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.Bold, color = color)
    }
}

private val ranges = listOf(30L, 91L, 366L)

@Composable
private fun RangeChips(selected: Int, onSelect: (Int) -> Unit) {
    val labels = listOf(R.string.chart_1m, R.string.chart_3m, R.string.chart_1y)
    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        labels.forEachIndexed { i, res ->
            FilterChip(selected = selected == i, onClick = { onSelect(i) }, label = { Text(stringResource(res)) })
        }
    }
}

fun List<SeriesPoint>.lastDays(days: Long): List<SeriesPoint> {
    if (isEmpty()) return this
    val cutoff = LocalDate.parse(last().date).minusDays(days)
    return filter { LocalDate.parse(it.date) > cutoff }
}

@Composable
private fun ChartCard(d: IndicatorDetail, f: Fmt) {
    var range by rememberSaveable { mutableIntStateOf(2) }
    val pts = d.series.lastDays(ranges[range])
    if (pts.size < 2) return
    val color = MaterialTheme.colorScheme.primary
    SectionCard {
        RangeChips(range) { range = it }
        LineChart(
            lines = listOf(ChartLine(pts.map { it.value }, color)),
            startLabel = f.axisDate(pts.first().date, ranges[range]),
            endLabel = f.axisDate(pts.last().date, ranges[range]),
            formatY = { valueText(d.code, d.unit, it, f) },
            description = componentName(d.code),
        )
    }
}

@Composable
private fun ScoringCard(d: IndicatorDetail, f: Fmt) {
    if (d.subScores.isEmpty()) return
    SectionCard(title = stringResource(R.string.how_scored)) {
        Row(Modifier.fillMaxWidth()) {
            Header(stringResource(R.string.col_horizon), Modifier.weight(1.4f), TextAlign.Start)
            Header(stringResource(R.string.col_change), Modifier.weight(1.1f))
            Header(stringResource(R.string.col_typical), Modifier.weight(1f))
            Header(stringResource(R.string.col_score), Modifier.weight(0.9f))
            Header(stringResource(R.string.col_weight), Modifier.weight(0.8f))
        }
        d.subScores.forEach { s -> SubScoreRow(d.code, s, f) }
        InfoNote(stringResource(R.string.how_scored_body))
    }
}

@Composable
private fun Header(text: String, modifier: Modifier, align: TextAlign = TextAlign.End) {
    Text(text, modifier, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant,
        textAlign = align)
}

@Composable
private fun SubScoreRow(code: String, s: SubScore, f: Fmt) {
    val sc = LocalSignalColors.current
    val cell = MaterialTheme.typography.bodySmall.merge(Tabular)
    Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
        Text(subKeyLabel(s.key), Modifier.weight(1.4f), style = MaterialTheme.typography.bodySmall)
        Text(s.delta?.let { subDeltaText(code, s.key, it, f) } ?: "—", Modifier.weight(1.1f), style = cell, textAlign = TextAlign.End)
        Text(s.sigma?.let { subDeltaText(code, s.key, it, f, signed = false) } ?: "—", Modifier.weight(1f), style = cell,
            textAlign = TextAlign.End)
        Text(f.signed(s.score, 2), Modifier.weight(0.9f), style = cell, textAlign = TextAlign.End,
            color = if (s.score > 0) sc.bullish else if (s.score < 0) sc.bearish else sc.neutral)
        Text(f.num(s.weight, 2), Modifier.weight(0.8f), style = cell, textAlign = TextAlign.End)
    }
}

@Composable
private fun subKeyLabel(key: String): String = when (key) {
    "d1", "d7", "d30", "d90" -> horizonLabel(key)
    "stance" -> stringResource(R.string.sub_stance)
    "level" -> stringResource(R.string.sub_level)
    "momentum" -> stringResource(R.string.sub_momentum)
    else -> eventName(key)
}

@Composable
fun horizonLabel(key: String): String = when (key) {
    "d1" -> stringResource(R.string.label_1d)
    "d7" -> stringResource(R.string.label_7d)
    "d30" -> stringResource(R.string.label_30d)
    "d90" -> stringResource(R.string.label_90d)
    else -> key
}

fun valueText(code: String, unit: String?, v: Double, f: Fmt): String = when (unit) {
    "pct" -> f.rate(v)
    "tonnes" -> f.tonnes(v)
    "try_per_gram" -> f.tryAmount(v)
    else -> f.num(v, 2)
}

fun changeText(unit: String?, v: Double, f: Fmt): String = when (unit) {
    "bp" -> f.bp(v)
    "pct" -> f.pct(v)
    else -> f.signed(v, 1)
}

private fun subDeltaText(code: String, key: String, v: Double, f: Fmt, signed: Boolean = true): String = when (code) {
    "REAL_YIELD", "FED", "NOMINAL_10Y" -> if (signed) f.bp(v) else "${f.num(v, 0)} ${if (f.locale.language == "ru") "б.п." else "bp"}"
    "DXY", "ETF", "GRAM_TRY" -> f.pct(v, 2, signed)
    "CENTRAL_BANKS" -> f.tonnes(v, signed)
    else -> if (signed) f.signed(v, 1) else f.num(v, 1)
}

/** Colour a change by what it means for gold, not by its sign. */
@Composable
private fun directionColor(code: String, v: Double): androidx.compose.ui.graphics.Color {
    val sc = LocalSignalColors.current
    val risingIsBullish = when (code) {
        "ETF", "CENTRAL_BANKS", "GRAM_TRY" -> true
        "NOMINAL_10Y" -> null
        else -> false
    }
    return when {
        risingIsBullish == null || v == 0.0 -> MaterialTheme.colorScheme.onSurface
        (v > 0) == risingIsBullish -> sc.bullish
        else -> sc.bearish
    }
}

@Composable
private fun DataAgeLine(d: IndicatorDetail, f: Fmt) {
    val date = d.observationDate?.let { f.date(it) } ?: "—"
    val age = d.ageBdays?.let { businessDays(it) } ?: "—"
    Text(
        stringResource(R.string.data_age, date, age, statusText(d.status), d.source),
        style = MaterialTheme.typography.labelSmall,
        color = MaterialTheme.colorScheme.onSurfaceVariant,
        modifier = Modifier.fillMaxWidth().padding(top = 4.dp),
        textAlign = TextAlign.Center,
    )
}
