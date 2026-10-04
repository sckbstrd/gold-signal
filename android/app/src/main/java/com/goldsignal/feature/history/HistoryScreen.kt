package com.goldsignal.feature.history

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
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
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.goldsignal.R
import com.goldsignal.core.designsystem.ChartLine
import com.goldsignal.core.designsystem.Disclaimer
import com.goldsignal.core.designsystem.ErrorBox
import com.goldsignal.core.designsystem.InfoNote
import com.goldsignal.core.designsystem.KeyValueRow
import com.goldsignal.core.designsystem.LineChart
import com.goldsignal.core.designsystem.LoadingBox
import com.goldsignal.core.designsystem.LocalSignalColors
import com.goldsignal.core.designsystem.SectionCard
import com.goldsignal.core.designsystem.Tabular
import com.goldsignal.core.format.Fmt
import com.goldsignal.core.format.rememberFmt
import com.goldsignal.core.i18n.componentName
import com.goldsignal.core.i18n.regimeText
import com.goldsignal.core.i18n.signalText
import com.goldsignal.core.ui.UiState
import com.goldsignal.core.ui.loadViewModel
import com.goldsignal.model.HistoryPoint
import com.goldsignal.model.HistoryReport
import com.goldsignal.model.Regime
import com.goldsignal.model.SignalLabel
import com.goldsignal.ui.ScreenScaffold
import kotlinx.coroutines.async
import kotlinx.coroutines.coroutineScope
import java.time.LocalDate

data class HistoryData(val points: List<HistoryPoint>, val report: HistoryReport)

@Composable
fun HistoryScreen(onBack: () -> Unit) {
    val vm = loadViewModel("history") {
        coroutineScope {
            val h = async { history().rows() }
            val r = async { historyReport() }
            HistoryData(h.await(), r.await())
        }
    }
    val state by vm.state.collectAsStateWithLifecycle()
    ScreenScaffold(title = stringResource(R.string.history_title), onBack = onBack, scrollable = state is UiState.Ready) {
        when (val s = state) {
            UiState.Loading -> LoadingBox()
            is UiState.Failed -> ErrorBox(s.message, vm::refresh)
            is UiState.Ready -> HistoryContent(s.data)
        }
    }
}

private val ranges = listOf(366L, 5 * 366L, Long.MAX_VALUE)

@Composable
private fun HistoryContent(d: HistoryData) {
    val f = rememberFmt()
    var range by rememberSaveable { mutableIntStateOf(1) }
    val all = d.points
    if (all.isEmpty()) return
    val cutoff = if (ranges[range] == Long.MAX_VALUE) null else LocalDate.parse(all.last().date).minusDays(ranges[range])
    val pts = if (cutoff == null) all else all.filter { LocalDate.parse(it.date) > cutoff }
    val firstLive = all.firstOrNull { it.origin == "LIVE" }?.date

    SectionCard {
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            listOf(R.string.chart_1y, R.string.chart_5y, R.string.chart_all).forEachIndexed { i, res ->
                FilterChip(range == i, { range = i }, { Text(stringResource(res)) })
            }
        }
        LineChart(
            lines = listOf(ChartLine(pts.map { it.score }, MaterialTheme.colorScheme.primary)),
            startLabel = f.monthYear(pts.first().date), endLabel = f.monthYear(pts.last().date),
            formatY = { f.num(it, 0) }, reference = 50.0, description = stringResource(R.string.history_title),
        )
        Text(stringResource(R.string.history_signal_strip), style = MaterialTheme.typography.labelMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant)
        SignalStrip(pts.map { it.signal })
        SignalLegend()
    }
    if (d.report.notes.contains("BACKFILL_IS_RECONSTRUCTED")) {
        InfoNote(firstLive?.let { stringResource(R.string.history_backfill_note, f.date(it)) }
            ?: stringResource(R.string.history_backfill_note_all))
    }
    ReportCards(d.report, f)
    Disclaimer(d.report.modelVersion)
}

private fun labelOf(code: String): SignalLabel? = SignalLabel.entries.firstOrNull { it.name == code }

@Composable
private fun SignalStrip(signals: List<String>) {
    val sc = LocalSignalColors.current
    val colors = signals.map { labelOf(it)?.let(sc::of) ?: sc.neutral }
    Canvas(Modifier.fillMaxWidth().height(14.dp).clip(RoundedCornerShape(4.dp))) {
        if (colors.isEmpty()) return@Canvas
        val w = size.width / colors.size
        var start = 0
        for (i in 1..colors.size) {
            if (i == colors.size || colors[i] != colors[start]) {
                drawRect(colors[start], Offset(start * w, 0f), Size((i - start) * w + 0.5f, size.height))
                start = i
            }
        }
    }
}

@Composable
private fun SignalLegend() {
    val sc = LocalSignalColors.current
    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
        SignalLabel.entries.reversed().forEach { label ->
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                Box(Modifier.width(10.dp).height(10.dp).clip(RoundedCornerShape(2.dp))) {
                    Canvas(Modifier.fillMaxWidth().height(10.dp)) { drawRect(sc.of(label)) }
                }
                Text(signalText(label), style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
        }
    }
}

@Composable
private fun ShareBars(shares: Map<String, Double>, color: (String) -> Color, label: @Composable (String) -> String) {
    shares.entries.sortedByDescending { it.value }.forEach { (k, v) ->
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Text(label(k), Modifier.width(132.dp), style = MaterialTheme.typography.bodySmall)
            val track = MaterialTheme.colorScheme.surfaceContainerHighest
            Canvas(Modifier.weight(1f).height(10.dp).clip(RoundedCornerShape(5.dp))) {
                drawRect(track)
                drawRect(color(k), size = Size(size.width * (v / 100.0).toFloat(), size.height))
            }
            Text(rememberFmt().pct(v, 1, signed = false), Modifier.width(56.dp),
                style = MaterialTheme.typography.bodySmall.merge(Tabular), textAlign = TextAlign.End)
        }
    }
}

@Composable
private fun ReportCards(r: HistoryReport, f: Fmt) {
    val sc = LocalSignalColors.current
    SectionCard(title = stringResource(R.string.history_report_title)) {
        if (r.firstDate != null && r.lastDate != null) {
            KeyValueRow(stringResource(R.string.history_period), "${f.date(r.firstDate)} – ${f.date(r.lastDate)}")
        }
        KeyValueRow(stringResource(R.string.history_days), r.days.toString())
        KeyValueRow(stringResource(R.string.history_changes_per_year), f.num(r.changesPerYear, 1))
        KeyValueRow(stringResource(R.string.history_mean_run), f.num(r.meanRunDays, 0))
        r.score?.let {
            KeyValueRow(stringResource(R.string.history_score_range),
                "${f.num(it.p10, 0)} / ${f.num(it.p50, 0)} / ${f.num(it.p90, 0)}")
        }
        HorizontalDivider()
        Text(stringResource(R.string.history_signal_share), style = MaterialTheme.typography.labelMedium,
            fontWeight = FontWeight.SemiBold)
        ShareBars(r.signalShare, { k -> labelOf(k)?.let(sc::of) ?: sc.neutral }, { k -> signalText(k) })
        HorizontalDivider()
        Text(stringResource(R.string.history_regime_share), style = MaterialTheme.typography.labelMedium,
            fontWeight = FontWeight.SemiBold)
        val regimeColor = MaterialTheme.colorScheme.secondary
        ShareBars(r.regimeShare, { regimeColor },
            { k -> Regime.entries.firstOrNull { it.name == k }?.let { regimeText(it) } ?: k })
        InfoNote(stringResource(R.string.history_report_note))
    }
    SectionCard(title = stringResource(R.string.history_coverage_title)) {
        r.componentCoverage.forEach { (code, pct) ->
            KeyValueRow(componentName(code), f.pct(pct, 1, signed = false),
                valueColor = if (pct >= 95) sc.bullish else if (pct > 0) sc.warning else sc.bearish)
        }
        InfoNote(stringResource(R.string.history_coverage_note))
    }
}
