package com.goldsignal.feature.backtest

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.pluralStringResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import com.goldsignal.R
import com.goldsignal.core.designsystem.Banner
import com.goldsignal.core.designsystem.ChartLine
import com.goldsignal.core.designsystem.Disclaimer
import com.goldsignal.core.designsystem.InfoNote
import com.goldsignal.core.designsystem.Legend
import com.goldsignal.core.designsystem.LineChart
import com.goldsignal.core.designsystem.LocalSignalColors
import com.goldsignal.core.designsystem.SectionCard
import com.goldsignal.core.designsystem.Tabular
import com.goldsignal.core.format.Fmt
import com.goldsignal.core.format.rememberFmt
import com.goldsignal.core.i18n.reasonText
import com.goldsignal.core.i18n.signalText
import com.goldsignal.core.ui.repository
import com.goldsignal.model.BacktestResponse
import com.goldsignal.ui.ScreenScaffold

@Composable
fun BacktestScreen() {
    val repo = repository()
    val vm: BacktestViewModel = viewModel { BacktestViewModel(repo) }
    val state by vm.state.collectAsStateWithLifecycle()
    val f = rememberFmt()
    ScreenScaffold(title = stringResource(R.string.backtest_title)) {
        SectionCard {
            Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                Field(stringResource(R.string.bt_start), state.form.start, Modifier.weight(1f),
                    FormError.DATE_FORMAT in state.errors || FormError.DATE_RANGE in state.errors) { v -> vm.edit { it.copy(start = v) } }
                Field(stringResource(R.string.bt_end), state.form.end, Modifier.weight(1f),
                    FormError.DATE_FORMAT in state.errors || FormError.DATE_RANGE in state.errors) { v -> vm.edit { it.copy(end = v) } }
            }
            Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                Field(stringResource(R.string.bt_capital), state.form.capital, Modifier.weight(1f),
                    FormError.CAPITAL in state.errors, KeyboardType.Decimal) { v -> vm.edit { it.copy(capital = v) } }
                Field(stringResource(R.string.bt_cost), state.form.costBps, Modifier.weight(1f),
                    FormError.COST in state.errors, KeyboardType.Decimal) { v -> vm.edit { it.copy(costBps = v) } }
            }
            state.errors.forEach { e ->
                Text(
                    stringResource(
                        when (e) {
                            FormError.DATE_FORMAT -> R.string.bt_invalid_date
                            FormError.DATE_RANGE -> R.string.bt_invalid_range
                            FormError.CAPITAL -> R.string.bt_invalid_capital
                            FormError.COST -> R.string.bt_invalid_cost
                        },
                    ),
                    color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall,
                )
            }
            Button(onClick = vm::run, enabled = !state.running, modifier = Modifier.fillMaxWidth().height(48.dp)) {
                if (state.running) CircularProgressIndicator(Modifier.size(20.dp), strokeWidth = 2.dp)
                else Text(stringResource(R.string.bt_run))
            }
            InfoNote(stringResource(R.string.bt_rules))
        }
        state.failure?.let { Banner(stringResource(R.string.error_title), it) }
        state.result?.let { Results(it, f) }
        Disclaimer(null)
    }
}

@Composable
private fun Field(
    label: String,
    value: String,
    modifier: Modifier,
    isError: Boolean,
    keyboard: KeyboardType = KeyboardType.Ascii,
    onChange: (String) -> Unit,
) {
    OutlinedTextField(
        value = value, onValueChange = onChange, label = { Text(label, maxLines = 1) }, singleLine = true,
        isError = isError, modifier = modifier, keyboardOptions = KeyboardOptions(keyboardType = keyboard),
        textStyle = MaterialTheme.typography.bodyMedium.merge(Tabular),
    )
}

@Composable
private fun Results(r: BacktestResponse, f: Fmt) {
    val sc = LocalSignalColors.current
    if (r.isDemo) {
        Banner(stringResource(R.string.bt_demo_title),
            stringResource(R.string.bt_demo_body, f.date(r.request.start), f.date(r.request.end)), critical = false)
    }
    r.warnings.filter { it.code != "DEMO_DATA" }.forEach { InfoNote(reasonText(it)) }

    SectionCard {
        Row(Modifier.fillMaxWidth()) {
            Text("", Modifier.weight(1.3f))
            Text(stringResource(R.string.bt_strategy), Modifier.weight(1f), style = MaterialTheme.typography.labelMedium,
                fontWeight = FontWeight.Bold, textAlign = TextAlign.End)
            Text(stringResource(R.string.bt_buy_hold), Modifier.weight(1f), style = MaterialTheme.typography.labelMedium,
                fontWeight = FontWeight.Bold, textAlign = TextAlign.End)
        }
        HorizontalDivider()
        val s = r.strategy
        val b = r.buyAndHold
        MetricRow(stringResource(R.string.bt_final), f.usd(s.finalValue), f.usd(b.finalValue))
        MetricRow(stringResource(R.string.bt_total_return), f.pct(s.totalReturnPct), f.pct(b.totalReturnPct))
        MetricRow(stringResource(R.string.bt_cagr), f.pct(s.cagrPct), f.pct(b.cagrPct))
        MetricRow(stringResource(R.string.bt_mdd), f.pct(s.maxDrawdownPct), f.pct(b.maxDrawdownPct))
        MetricRow(stringResource(R.string.bt_sharpe), s.sharpe?.let { f.num(it, 2) } ?: "—", b.sharpe?.let { f.num(it, 2) } ?: "—")
        HorizontalDivider()
        StrategyOnly(stringResource(R.string.bt_trades), s.trades?.toString() ?: "—")
        StrategyOnly(stringResource(R.string.bt_win_rate), s.winRatePct?.let { f.pct(it, 1, false) } ?: "—")
        StrategyOnly(stringResource(R.string.bt_avg_gain), s.avgGainPct?.let { f.pct(it) } ?: "—")
        StrategyOnly(stringResource(R.string.bt_avg_loss), s.avgLossPct?.let { f.pct(it) } ?: "—")
        StrategyOnly(stringResource(R.string.bt_best), s.bestTradePct?.let { f.pct(it) } ?: "—")
        StrategyOnly(stringResource(R.string.bt_worst), s.worstTradePct?.let { f.pct(it) } ?: "—")
        StrategyOnly(stringResource(R.string.bt_invested), s.timeInvestedPct?.let { f.pct(it, 1, false) } ?: "—")
    }

    if (r.equityCurve.size > 2) {
        SectionCard(title = stringResource(R.string.bt_equity)) {
            val primary = MaterialTheme.colorScheme.primary
            val outline = MaterialTheme.colorScheme.outline
            LineChart(
                lines = listOf(ChartLine(r.equityCurve.map { it.benchmark }, outline),
                    ChartLine(r.equityCurve.map { it.strategy }, primary)),
                startLabel = f.monthYear(r.equityCurve.first().date),
                endLabel = f.monthYear(r.equityCurve.last().date),
                formatY = { f.usd(it) },
                reference = r.request.capital,
            )
            Legend(listOf(stringResource(R.string.bt_strategy) to primary, stringResource(R.string.bt_buy_hold) to outline))
        }
    }

    if (r.tradesList.isNotEmpty()) {
        SectionCard(title = stringResource(R.string.bt_trades)) {
            r.tradesList.forEachIndexed { i, t ->
                if (i > 0) HorizontalDivider()
                Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                    Column(Modifier.weight(1f)) {
                        Text(
                            "${f.date(t.entryDate)} → ${t.exitDate?.let { f.date(it) } ?: stringResource(R.string.bt_open)}",
                            style = MaterialTheme.typography.bodySmall,
                        )
                        Text(
                            "${signalText(t.entrySignal)} → ${t.exitSignal?.let { signalText(it) } ?: "…"} · " +
                                pluralStringResource(R.plurals.calendar_days, t.days, t.days),
                            style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                    Text(f.pct(t.returnPct), style = MaterialTheme.typography.titleSmall.merge(Tabular),
                        color = if (t.returnPct > 0) sc.bullish else sc.bearish)
                }
            }
        }
    }
}

@Composable
private fun MetricRow(label: String, strategy: String, benchmark: String) {
    Row(Modifier.fillMaxWidth()) {
        Text(label, Modifier.weight(1.3f), style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant)
        Text(strategy, Modifier.weight(1f), style = MaterialTheme.typography.bodySmall.merge(Tabular),
            fontWeight = FontWeight.SemiBold, textAlign = TextAlign.End)
        Text(benchmark, Modifier.weight(1f), style = MaterialTheme.typography.bodySmall.merge(Tabular), textAlign = TextAlign.End)
    }
}

@Composable
private fun StrategyOnly(label: String, value: String) = MetricRow(label, value, "")
