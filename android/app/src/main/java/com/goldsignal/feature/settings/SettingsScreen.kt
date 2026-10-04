package com.goldsignal.feature.settings

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.selection.selectableGroup
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.RadioButton
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.goldsignal.BuildConfig
import com.goldsignal.R
import com.goldsignal.core.designsystem.Disclaimer
import com.goldsignal.core.designsystem.InfoNote
import com.goldsignal.core.designsystem.KeyValueRow
import com.goldsignal.core.designsystem.LocalSignalColors
import com.goldsignal.core.designsystem.SectionCard
import com.goldsignal.core.format.rememberFmt
import com.goldsignal.core.i18n.LanguageManager
import com.goldsignal.core.i18n.businessDays
import com.goldsignal.core.i18n.statusText
import com.goldsignal.core.ui.UiState
import com.goldsignal.core.ui.container
import com.goldsignal.core.ui.loadViewModel
import com.goldsignal.data.DataSource
import com.goldsignal.model.HealthResponse
import com.goldsignal.ui.ScreenScaffold

@Composable
private fun <T> RadioGroup(options: List<Pair<T, String>>, selected: T, onSelect: (T) -> Unit) {
    Column(Modifier.selectableGroup()) {
        options.forEach { (value, label) ->
            Row(
                Modifier.fillMaxWidth().heightIn(min = 48.dp)
                    .selectable(selected = selected == value, role = Role.RadioButton, onClick = { onSelect(value) }),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                RadioButton(selected = selected == value, onClick = null)
                Text(label, style = MaterialTheme.typography.bodyLarge, modifier = Modifier.padding(start = 12.dp))
            }
        }
    }
}

@Composable
fun SettingsScreen() {
    val c = container()
    var language by remember { mutableStateOf(LanguageManager.current()) }
    val key = c.repositoryKey                         // recompose when the data source changes
    ScreenScaffold(title = stringResource(R.string.settings_title)) {
        SectionCard(title = stringResource(R.string.settings_language)) {
            RadioGroup(
                listOf("" to stringResource(R.string.lang_system), "en" to "English", "tr" to "Türkçe", "ru" to "Русский"),
                language,
            ) { tag ->
                language = tag
                LanguageManager.set(tag)
            }
        }

        SectionCard(title = stringResource(R.string.settings_data_source)) {
            RadioGroup(
                listOf(DataSource.LIVE to stringResource(R.string.data_source_live_option),
                    DataSource.MOCK to stringResource(R.string.data_source_demo_option)),
                c.dataSource,
            ) { c.dataSource = it }
            Text(
                stringResource(if (c.dataSource == DataSource.MOCK) R.string.data_source_mock else R.string.data_source_live),
                style = MaterialTheme.typography.bodyMedium,
            )
            if (c.dataSource == DataSource.LIVE) ServerUrlEditor(c.serverUrl) { c.serverUrl = it }
        }

        if (c.dataSource == DataSource.LIVE) DataHealthCard(key)

        SectionCard(title = stringResource(R.string.settings_alerts)) {
            Text(stringResource(R.string.alerts_phase7), style = MaterialTheme.typography.bodyMedium)
        }
        SectionCard(title = stringResource(R.string.settings_about)) {
            Text(stringResource(R.string.about_body), style = MaterialTheme.typography.bodyMedium)
            Text(stringResource(R.string.about_confidence), style = MaterialTheme.typography.bodyMedium)
            Text(stringResource(R.string.about_no_trading), style = MaterialTheme.typography.bodyMedium,
                fontWeight = FontWeight.SemiBold)
            KeyValueRow(stringResource(R.string.about_app_version), BuildConfig.VERSION_NAME)
            InfoNote(stringResource(R.string.about_translation_note))
        }
        Disclaimer(null)
    }
}

@Composable
private fun ServerUrlEditor(current: String, onSave: (String) -> Unit) {
    var text by remember(current) { mutableStateOf(current) }
    OutlinedTextField(
        value = text, onValueChange = { text = it }, singleLine = true,
        label = { Text(stringResource(R.string.server_url_label)) },
        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Uri),
        modifier = Modifier.fillMaxWidth(),
    )
    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        OutlinedButton(onClick = { onSave(text) }, enabled = text.startsWith("http") && text != current) {
            Text(stringResource(R.string.server_url_save))
        }
        TextButton(onClick = { onSave(BuildConfig.DEFAULT_SERVER_URL) }) { Text(stringResource(R.string.server_url_reset)) }
    }
}

@Composable
private fun DataHealthCard(key: String) {
    val vm = loadViewModel("health") { health() }
    val state by vm.state.collectAsStateWithLifecycle()
    SectionCard(title = stringResource(R.string.data_health_title)) {
        when (val s = state) {
            UiState.Loading -> Text(stringResource(R.string.loading), style = MaterialTheme.typography.bodySmall)
            is UiState.Failed -> Text(stringResource(R.string.error_title) + ": " + s.message,
                style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.error)
            is UiState.Ready -> HealthRows(s.data)
        }
    }
}

@Composable
private fun HealthRows(h: HealthResponse) {
    val f = rememberFmt()
    val sc = LocalSignalColors.current
    h.latestOfficialDate?.let { KeyValueRow(stringResource(R.string.health_latest_eval), f.date(it)) }
    KeyValueRow(stringResource(R.string.health_generated), f.dateTime(h.generatedAt))
    if (h.signalOverdue) Text(stringResource(R.string.overdue_body), color = sc.warning, style = MaterialTheme.typography.bodySmall)
    h.series.forEach { s ->
        val color = when (s.status) { "FRESH" -> sc.bullish; "AGING" -> sc.warning; else -> sc.bearish }
        Column(Modifier.fillMaxWidth()) {
            KeyValueRow(s.code, statusText(s.status), valueColor = color)
            Text(
                "${s.source} · ${s.lastObservation?.let { f.date(it) } ?: "—"}" +
                    (s.ageBdays?.let { " · " } ?: "") + (s.ageBdays?.let { businessDays(it) } ?: ""),
                style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
    h.sources.filter { it.lastError != null }.forEach {
        Text("${it.name}: ${it.lastError}", style = MaterialTheme.typography.labelSmall, color = sc.bearish)
    }
    InfoNote(stringResource(R.string.health_note))
}
