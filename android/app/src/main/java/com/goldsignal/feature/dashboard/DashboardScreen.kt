package com.goldsignal.feature.dashboard

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Spacer
import androidx.compose.runtime.LaunchedEffect
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.compose.LocalLifecycleOwner
import androidx.lifecycle.repeatOnLifecycle
import com.goldsignal.model.ProvisionalResponse
import kotlinx.coroutines.delay
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.goldsignal.R
import com.goldsignal.core.designsystem.Banner
import com.goldsignal.core.designsystem.CenteredBar
import com.goldsignal.core.designsystem.Disclaimer
import com.goldsignal.core.designsystem.ErrorBox
import com.goldsignal.core.designsystem.ImpactArrow
import com.goldsignal.core.designsystem.LoadingBox
import com.goldsignal.core.designsystem.LocalSignalColors
import com.goldsignal.core.designsystem.ScoreGauge
import com.goldsignal.core.designsystem.SectionCard
import com.goldsignal.core.designsystem.SignalBadge
import com.goldsignal.core.designsystem.Tabular
import com.goldsignal.core.designsystem.formatScore
import com.goldsignal.core.format.Fmt
import com.goldsignal.core.format.rememberFmt
import com.goldsignal.core.i18n.componentName
import com.goldsignal.core.i18n.regimeDescription
import com.goldsignal.core.i18n.regimeText
import com.goldsignal.core.i18n.signalText
import com.goldsignal.core.i18n.statusText
import com.goldsignal.core.ui.UiState
import com.goldsignal.core.ui.container
import com.goldsignal.core.ui.loadViewModel
import com.goldsignal.data.DataSource
import com.goldsignal.data.FetchInfo
import com.goldsignal.model.HistoryPoint
import com.goldsignal.core.designsystem.ChartLine
import com.goldsignal.core.designsystem.LineChart
import java.time.Instant
import java.time.OffsetDateTime
import com.goldsignal.model.ComponentSummary
import com.goldsignal.model.CurrentResponse
import com.goldsignal.model.DataStatus
import com.goldsignal.model.Pending
import com.goldsignal.model.SignalLabel
import com.goldsignal.model.SignalResponse
import com.goldsignal.ui.ScreenScaffold
import kotlinx.coroutines.async
import kotlinx.coroutines.coroutineScope

data class DashboardData(
    val signal: SignalResponse,
    val current: CurrentResponse,
    val source: DataSource,
    val fetch: FetchInfo,
    val history: List<HistoryPoint>?,
    val provisional: ProvisionalResponse?,
)

/** The backend republishes every 30 minutes; while the dashboard is visible, poll every 5. */
private const val AUTO_REFRESH_MS = 5 * 60_000L

@Composable
fun DashboardScreen(onIndicator: (String) -> Unit, onWhy: (Int) -> Unit, onHistory: () -> Unit) {
    val vm = loadViewModel("dashboard") {
        coroutineScope {
            val s = async { signal() }
            val c = async { current() }
            val h = async { runCatching { history().rows() }.getOrNull() }
            val p = async { runCatching { provisional() }.getOrNull() }
            DashboardData(s.await(), c.await(), source, freshness, h.await(), p.await())
        }
    }
    val state by vm.state.collectAsStateWithLifecycle()
    val c = container()
    val lifecycle = LocalLifecycleOwner.current.lifecycle
    LaunchedEffect(vm, lifecycle, c.repositoryKey) {
        if (c.dataSource != DataSource.LIVE || !c.autoRefresh) return@LaunchedEffect
        lifecycle.repeatOnLifecycle(Lifecycle.State.RESUMED) {
            while (true) {
                // Also catches up immediately when the app comes back to the foreground.
                if (vm.loadedAt > 0 && System.currentTimeMillis() - vm.loadedAt >= AUTO_REFRESH_MS) {
                    vm.refresh(silent = true)
                }
                delay(30_000)
            }
        }
    }
    ScreenScaffold(title = stringResource(R.string.dashboard_title), scrollable = state is UiState.Ready,
        onRefresh = vm::refresh) {
        when (val s = state) {
            UiState.Loading -> LoadingBox()
            is UiState.Failed -> ErrorBox(
                s.message, vm::refresh,
                secondary = if (c.dataSource == DataSource.LIVE) {
                    stringResource(R.string.use_demo_data) to { c.dataSource = DataSource.MOCK }
                } else null,
            )
            is UiState.Ready -> DashboardContent(s.data, onIndicator, onWhy, onHistory)
        }
    }
}

@Composable
private fun DashboardContent(
    d: DashboardData,
    onIndicator: (String) -> Unit,
    onWhy: (Int) -> Unit,
    onHistory: () -> Unit,
) {
    val f = rememberFmt()
    val g = d.signal.global
    Text(
        stringResource(R.string.updated_at, f.dateTime(d.signal.evaluatedAt)),
        style = MaterialTheme.typography.labelMedium,
        color = MaterialTheme.colorScheme.onSurfaceVariant,
        modifier = Modifier.fillMaxWidth(),
        textAlign = TextAlign.Center,
    )
    if (d.source == DataSource.MOCK) {
        Banner(stringResource(R.string.mock_title), stringResource(R.string.mock_body), critical = false)
    }
    if (d.fetch.fromCache) {
        Banner(stringResource(R.string.offline_title),
            stringResource(R.string.offline_body, d.fetch.cachedAtMillis?.let { f.dateTimeMillis(it) } ?: "—"),
            critical = false)
    }
    if (isOverdue(d.signal.nextOfficialEvaluation)) {
        Banner(stringResource(R.string.overdue_title), stringResource(R.string.overdue_body), critical = false)
    }
    when (d.signal.dataStatus) {
        DataStatus.DELAYED -> Banner(stringResource(R.string.data_delayed), stringResource(R.string.data_delayed_body))
        DataStatus.DEGRADED -> Banner(stringResource(R.string.data_degraded), stringResource(R.string.data_degraded_body), critical = false)
        DataStatus.OK -> Unit
    }

    PriceCard(d.current, f, onGram = { onIndicator("GRAM_TRY") })
    d.provisional?.let { LiveCard(it, f) }

    SectionCard {
        Column(Modifier.fillMaxWidth(), horizontalAlignment = Alignment.CenterHorizontally) {
            Text(stringResource(R.string.gold_score), style = MaterialTheme.typography.labelLarge,
                color = MaterialTheme.colorScheme.onSurfaceVariant)
            ScoreGauge(g.score, g.signal, size = 190.dp)
            SignalBadge(g.signal, large = true)
            g.pending?.let { PendingLine(it) }
            g.signalSince?.let {
                Text(stringResource(R.string.signal_since, f.date(it)), style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.padding(top = 4.dp))
            }
            Text(
                stringResource(R.string.confidence_value, f.pct(g.confidence.toDouble(), 0, signed = false)),
                style = MaterialTheme.typography.titleMedium,
                modifier = Modifier.padding(top = 12.dp),
            )
            Text(stringResource(R.string.confidence_disclaimer), style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant, textAlign = TextAlign.Center)
            HorizontalDivider(Modifier.padding(vertical = 12.dp))
            Text(stringResource(R.string.regime_label), style = MaterialTheme.typography.labelMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant)
            Text(regimeText(g.regime), style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
            Text(regimeDescription(g.regime), style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant, textAlign = TextAlign.Center)
        }
    }

    SectionCard(title = stringResource(R.string.factors_title)) {
        g.components.forEach { c -> FactorRow(c, f, onClick = { onIndicator(c.code) }) }
        Text(stringResource(R.string.factors_note), style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant)
    }

    d.history?.takeIf { it.size > 20 }?.let { HistoryCard(it, f, onHistory) }

    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
        SignalTile(stringResource(R.string.global_gold), g.signal, g.score, Modifier.weight(1f)) { onWhy(0) }
        SignalTile(stringResource(R.string.gram_gold_signal), d.signal.gramTry.signal, d.signal.gramTry.score,
            Modifier.weight(1f)) { onWhy(1) }
    }

    Button(onClick = { onWhy(0) }, modifier = Modifier.fillMaxWidth().height(52.dp)) {
        Text(stringResource(R.string.why_button), style = MaterialTheme.typography.titleMedium)
    }

    d.signal.nextOfficialEvaluation?.let {
        Text(stringResource(R.string.next_evaluation, f.dateTime(it)), style = MaterialTheme.typography.labelSmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.fillMaxWidth(), textAlign = TextAlign.Center)
    }
    Disclaimer(d.signal.modelVersion)
}

@Composable
private fun LiveCard(p: ProvisionalResponse, f: Fmt) {
    val sc = LocalSignalColors.current
    SectionCard {
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Canvas(Modifier.size(10.dp)) { drawCircle(if (p.marketOpen) sc.bullish else sc.neutral) }
            Text(stringResource(if (p.marketOpen) R.string.live_label else R.string.markets_closed),
                style = MaterialTheme.typography.labelLarge, fontWeight = FontWeight.Bold,
                color = if (p.marketOpen) sc.bullish else MaterialTheme.colorScheme.onSurfaceVariant)
            Spacer(Modifier.weight(1f))
            (p.quotesAsOf ?: p.asOf).let {
                Text(stringResource(R.string.live_updated, f.time(it)), style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
        }
        Text(stringResource(R.string.provisional_title), style = MaterialTheme.typography.labelMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant)
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            Text(f.num(p.score, 1), style = MaterialTheme.typography.headlineMedium.merge(Tabular),
                fontWeight = FontWeight.SemiBold)
            SignalBadge(p.rawBand)
            p.official.score?.let { official ->
                val delta = p.score - official
                Text(stringResource(R.string.provisional_vs_official, f.signed(delta, 1), f.num(official, 1)),
                    style = MaterialTheme.typography.labelMedium.merge(Tabular),
                    color = if (delta > 0.05) sc.bullish else if (delta < -0.05) sc.bearish else sc.neutral)
            }
        }
        Text(
            stringResource(R.string.provisional_note,
                p.official.signal?.let { signalText(it) } ?: "—",
                p.official.nextOfficialEvaluation?.let { f.dateTime(it) } ?: "—"),
            style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
    }
}

/** The backend should have produced a newer evaluation by now (3 h grace after the scheduled time). */
private fun isOverdue(nextOfficial: String?): Boolean = runCatching {
    nextOfficial != null && Instant.now().isAfter(OffsetDateTime.parse(nextOfficial).toInstant().plusSeconds(3 * 3600))
}.getOrDefault(false)

@Composable
private fun HistoryCard(points: List<HistoryPoint>, f: Fmt, onClick: () -> Unit) {
    val last = points.takeLast(260)
    SectionCard(title = stringResource(R.string.history_card_title), onClick = onClick) {
        LineChart(
            lines = listOf(ChartLine(last.map { it.score }, MaterialTheme.colorScheme.primary)),
            startLabel = f.monthYear(last.first().date), endLabel = f.monthYear(last.last().date),
            formatY = { f.num(it, 0) }, reference = 50.0,
        )
        Text(stringResource(R.string.history_card_more), style = MaterialTheme.typography.labelLarge,
            color = MaterialTheme.colorScheme.primary)
    }
}

@Composable
private fun PriceCard(c: CurrentResponse, f: Fmt, onGram: () -> Unit) {
    val sc = LocalSignalColors.current
    SectionCard {
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(16.dp)) {
            PriceCell(stringResource(R.string.gold_spot), f.usd(c.gold.priceUsd), c.gold.changePct.d1, f, Modifier.weight(1f))
            PriceCell(stringResource(R.string.gram_gold), f.tryAmount(c.gramGold.theoreticalTry), c.gramGold.changePct.d1, f,
                Modifier.weight(1f).clip(RoundedCornerShape(8.dp)).clickable(role = Role.Button, onClick = onGram))
        }
        Text(
            stringResource(R.string.distance_from_high, f.pct(c.gold.distanceFromHighPct), f.usd(c.gold.high52w)),
            style = MaterialTheme.typography.bodySmall,
            color = if (c.gold.distanceFromHighPct < -10) sc.bearish else MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Text(
            stringResource(R.string.prices_as_of, f.dateTime(c.gold.observedAt)),
            style = MaterialTheme.typography.labelSmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
    }
}

@Composable
private fun PriceCell(label: String, price: String, d1: Double?, f: Fmt, modifier: Modifier = Modifier) {
    val sc = LocalSignalColors.current
    Column(modifier) {
        Text(label, style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Text(price, style = MaterialTheme.typography.titleLarge.merge(Tabular), fontWeight = FontWeight.SemiBold)
        if (d1 != null) {
            Text(
                stringResource(R.string.change_1d, f.pct(d1)),
                style = MaterialTheme.typography.labelMedium.merge(Tabular),
                color = if (d1 > 0) sc.bullish else if (d1 < 0) sc.bearish else sc.neutral,
            )
        }
    }
}

@Composable
private fun PendingLine(p: Pending) {
    Surface(color = MaterialTheme.colorScheme.secondaryContainer, shape = RoundedCornerShape(50),
        modifier = Modifier.padding(top = 8.dp)) {
        Text(
            stringResource(R.string.pending_change, signalText(p.signal), p.days, p.required),
            modifier = Modifier.padding(horizontal = 12.dp, vertical = 4.dp),
            style = MaterialTheme.typography.labelMedium,
            color = MaterialTheme.colorScheme.onSecondaryContainer,
        )
    }
}

@Composable
private fun FactorRow(c: ComponentSummary, f: Fmt, onClick: () -> Unit) {
    val sc = LocalSignalColors.current
    Row(
        Modifier.fillMaxWidth().clip(RoundedCornerShape(8.dp)).clickable(role = Role.Button, onClick = onClick)
            .padding(vertical = 6.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        Column(Modifier.weight(1f)) {
            Text(componentName(c.code), style = MaterialTheme.typography.bodyMedium)
            if (c.status != "FRESH" && c.status != "MOCK") {
                Text(statusText(c.status), style = MaterialTheme.typography.labelSmall, color = sc.warning)
            }
        }
        CenteredBar(c.tilt, c.weight / 2, sc.impact(c.impact), Modifier.width(72.dp))
        Text(
            stringResource(R.string.factor_points, f.num(c.points, 1), f.num(c.weight, 0)),
            style = MaterialTheme.typography.bodyMedium.merge(Tabular),
            modifier = Modifier.width(64.dp),
            textAlign = TextAlign.End,
        )
        ImpactArrow(c.impact, Modifier.width(14.dp))
        Icon(painterResource(R.drawable.ic_chevron), null, Modifier.size(16.dp), tint = MaterialTheme.colorScheme.outline)
    }
}

@Composable
private fun SignalTile(title: String, label: SignalLabel, score: Double, modifier: Modifier, onClick: () -> Unit) {
    SectionCard(modifier = modifier, onClick = onClick) {
        Column(Modifier.fillMaxWidth(), horizontalAlignment = Alignment.CenterHorizontally) {
            Text(title, style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant,
                textAlign = TextAlign.Center)
            SignalBadge(label, Modifier.padding(vertical = 6.dp))
            Text(stringResource(R.string.score_short, formatScore(score)), style = MaterialTheme.typography.labelMedium.merge(Tabular),
                color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}
