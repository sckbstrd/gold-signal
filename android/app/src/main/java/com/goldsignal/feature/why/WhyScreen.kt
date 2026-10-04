package com.goldsignal.feature.why

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.PrimaryTabRow
import androidx.compose.material3.Tab
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.goldsignal.R
import com.goldsignal.core.designsystem.Disclaimer
import com.goldsignal.core.designsystem.ErrorBox
import com.goldsignal.core.designsystem.InfoNote
import com.goldsignal.core.designsystem.LoadingBox
import com.goldsignal.core.designsystem.LocalSignalColors
import com.goldsignal.core.designsystem.SectionCard
import com.goldsignal.core.designsystem.SignalBadge
import com.goldsignal.core.designsystem.formatScore
import com.goldsignal.core.format.rememberFmt
import com.goldsignal.core.i18n.reasonText
import com.goldsignal.core.i18n.regimeText
import com.goldsignal.core.ui.UiState
import com.goldsignal.core.ui.loadViewModel
import com.goldsignal.model.Explanation
import com.goldsignal.model.Reason
import com.goldsignal.model.SignalLabel
import com.goldsignal.model.SignalResponse
import com.goldsignal.ui.ScreenScaffold

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun WhyScreen(initialTab: Int, onBack: () -> Unit) {
    val vm = loadViewModel("why") { signal() }
    val state by vm.state.collectAsStateWithLifecycle()
    var tab by rememberSaveable { mutableIntStateOf(initialTab) }
    ScreenScaffold(title = stringResource(R.string.why_title), onBack = onBack, scrollable = state is UiState.Ready) {
        when (val s = state) {
            UiState.Loading -> LoadingBox()
            is UiState.Failed -> ErrorBox(s.message, vm::refresh)
            is UiState.Ready -> {
                PrimaryTabRow(selectedTabIndex = tab, containerColor = MaterialTheme.colorScheme.background) {
                    Tab(tab == 0, onClick = { tab = 0 }, text = { Text(stringResource(R.string.why_tab_global)) })
                    Tab(tab == 1, onClick = { tab = 1 }, text = { Text(stringResource(R.string.why_tab_gram)) })
                }
                WhyContent(s.data, gram = tab == 1)
            }
        }
    }
}

@Composable
private fun WhyContent(sig: SignalResponse, gram: Boolean) {
    val f = rememberFmt()
    val label: SignalLabel
    val score: Double
    val confidence: Int
    val explanation: Explanation
    if (gram) {
        label = sig.gramTry.signal; score = sig.gramTry.score
        confidence = sig.gramTry.confidence; explanation = sig.gramTry.explanation
    } else {
        label = sig.global.signal; score = sig.global.score
        confidence = sig.global.confidence; explanation = sig.global.explanation
    }
    val sc = LocalSignalColors.current

    SectionCard {
        Text(reasonText(explanation.headline), style = MaterialTheme.typography.headlineSmall)
        SignalBadge(label)
        Text(
            stringResource(
                R.string.why_score_line, formatScore(score), f.pct(confidence.toDouble(), 0, signed = false),
                regimeText(sig.global.regime),
            ),
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        if (gram) InfoNote(stringResource(R.string.gram_two_drivers))
    }
    ReasonList(stringResource(R.string.why_positive), explanation.positive, sc.bullish, numbered = true)
    ReasonList(stringResource(R.string.why_negative), explanation.negative, sc.bearish, numbered = false)
    ReasonList(stringResource(R.string.why_neutral), explanation.neutral, sc.neutral, numbered = false)
    ReasonList(stringResource(R.string.why_warnings), explanation.warnings, sc.warning, numbered = false)
    SectionCard(title = stringResource(R.string.why_conclusion)) {
        Text(reasonText(explanation.conclusion), style = MaterialTheme.typography.bodyLarge, fontWeight = FontWeight.Medium)
    }
    InfoNote(stringResource(R.string.confidence_disclaimer))
    InfoNote(stringResource(R.string.why_generated_note, sig.modelVersion))
    Disclaimer(null)
}

@Composable
private fun ReasonList(title: String, items: List<Reason>, accent: Color, numbered: Boolean) {
    if (items.isEmpty()) return
    SectionCard(title = title) {
        items.forEachIndexed { i, r ->
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                Text(if (numbered) "${i + 1}." else "•", color = accent, fontWeight = FontWeight.Bold,
                    modifier = Modifier.width(20.dp))
                Column(Modifier.weight(1f).padding(bottom = 2.dp)) {
                    Text(reasonText(r), style = MaterialTheme.typography.bodyMedium)
                }
            }
        }
    }
}
