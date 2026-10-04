package com.goldsignal.feature.events

import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.goldsignal.R
import com.goldsignal.core.designsystem.Disclaimer
import com.goldsignal.core.designsystem.ErrorBox
import com.goldsignal.core.designsystem.HorizonCells
import com.goldsignal.core.designsystem.InfoNote
import com.goldsignal.core.designsystem.LoadingBox
import com.goldsignal.core.designsystem.LocalSignalColors
import com.goldsignal.core.designsystem.SectionCard
import com.goldsignal.core.designsystem.SectionTitle
import com.goldsignal.core.format.Fmt
import com.goldsignal.core.format.rememberFmt
import com.goldsignal.core.i18n.eventName
import com.goldsignal.core.i18n.impactText
import com.goldsignal.core.ui.UiState
import com.goldsignal.core.ui.loadViewModel
import com.goldsignal.feature.indicator.eventValue
import com.goldsignal.model.EconomicEvent
import com.goldsignal.ui.ScreenScaffold

@Composable
fun EventsScreen() {
    val vm = loadViewModel("events") { events() }
    val state by vm.state.collectAsStateWithLifecycle()
    ScreenScaffold(title = stringResource(R.string.events_title), scrollable = state is UiState.Ready) {
        when (val s = state) {
            UiState.Loading -> LoadingBox()
            is UiState.Failed -> ErrorBox(s.message, vm::refresh)
            is UiState.Ready -> {
                val f = rememberFmt()
                val (released, pending) = s.data.events.partition { it.status == "RELEASED" }
                InfoNote(stringResource(R.string.econ_note))
                if (pending.isNotEmpty()) {
                    SectionTitle(stringResource(R.string.events_upcoming))
                    pending.sortedBy { it.scheduledAt }.forEach { EventCard(it, f) }
                }
                if (released.isNotEmpty()) {
                    SectionTitle(stringResource(R.string.events_released))
                    released.sortedByDescending { it.releasedAt }.forEach { EventCard(it, f) }
                }
                InfoNote(stringResource(R.string.events_tz_note))
                Disclaimer(null)
            }
        }
    }
}

@Composable
private fun EventCard(e: EconomicEvent, f: Fmt) {
    val sc = LocalSignalColors.current
    SectionCard {
        Row(Modifier.fillMaxWidth()) {
            Text(eventName(e.code), Modifier.weight(1f), style = MaterialTheme.typography.titleSmall)
            when {
                e.status == "DELAYED" ->
                    Text(stringResource(R.string.econ_delayed), color = sc.warning, style = MaterialTheme.typography.labelLarge,
                        fontWeight = FontWeight.Bold)
                e.impactLabel != null ->
                    Text(impactText(e.impactLabel), color = sc.impact(e.impactLabel), style = MaterialTheme.typography.labelLarge)
            }
        }
        Text(
            "${e.referencePeriod} · ${f.dateTime(e.releasedAt ?: e.scheduledAt)}",
            style = MaterialTheme.typography.labelSmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        val cells = buildList {
            add(stringResource(R.string.econ_previous) to eventValue(e.code, e.previous, f))
            add(stringResource(R.string.econ_expected) to eventValue(e.code, e.consensus, f))
            if (e.status == "RELEASED") {
                add(stringResource(R.string.econ_actual) to eventValue(e.code, e.actual, f))
                add(stringResource(R.string.econ_surprise) to eventValue(e.code, e.surprise, f, signed = true))
            }
        }
        val impact = e.impact ?: 0.0
        HorizonCells(
            cells,
            cells.indices.map { i ->
                if (i == 3) (if (impact > 0.05) sc.bullish else if (impact < -0.05) sc.bearish else sc.neutral)
                else MaterialTheme.colorScheme.onSurface
            },
        )
    }
}
