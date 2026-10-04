package com.goldsignal.core.designsystem

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.layout.layout
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import com.goldsignal.R
import com.goldsignal.core.i18n.signalText
import com.goldsignal.model.SignalLabel

@Composable
fun SectionCard(
    modifier: Modifier = Modifier,
    title: String? = null,
    onClick: (() -> Unit)? = null,
    content: @Composable ColumnScope.() -> Unit,
) {
    Surface(
        modifier = modifier.fillMaxWidth().clip(RoundedCornerShape(16.dp))
            .let { if (onClick != null) it.clickable(onClick = onClick) else it },
        color = MaterialTheme.colorScheme.surfaceContainerLow,
        shape = RoundedCornerShape(16.dp),
    ) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            if (title != null) SectionTitle(title)
            content()
        }
    }
}

@Composable
fun SectionTitle(text: String, modifier: Modifier = Modifier) {
    // Locale-aware: Turkish "i" must become "İ", not "I".
    val locale = androidx.compose.ui.platform.LocalConfiguration.current.locales[0]
    Text(
        text.uppercase(locale),
        modifier = modifier,
        style = MaterialTheme.typography.labelSmall,
        color = MaterialTheme.colorScheme.onSurfaceVariant,
    )
}

/** Coloured pill with the localized signal name. */
@Composable
fun SignalBadge(label: SignalLabel, modifier: Modifier = Modifier, large: Boolean = false) {
    val color = LocalSignalColors.current.of(label)
    Surface(modifier = modifier, color = color.copy(alpha = 0.14f), shape = RoundedCornerShape(50)) {
        Text(
            signalText(label),
            modifier = Modifier.padding(horizontal = if (large) 18.dp else 10.dp, vertical = if (large) 6.dp else 3.dp),
            style = if (large) MaterialTheme.typography.titleLarge else MaterialTheme.typography.labelLarge,
            fontWeight = FontWeight.Bold,
            color = color,
        )
    }
}

/**
 * 0-100 gauge with the band boundaries (25 / 40 / 60 / 75) marked on the track.
 */
@Composable
fun ScoreGauge(score: Double, label: SignalLabel, modifier: Modifier = Modifier, size: Dp = 200.dp) {
    val signals = LocalSignalColors.current
    val track = MaterialTheme.colorScheme.surfaceContainerHighest
    val tick = MaterialTheme.colorScheme.surface
    val color = signals.of(label)
    val start = 150f
    val sweep = 240f
    val gaugeDescription = stringResource(R.string.gauge_description, formatScore(score), signalText(label))
    // The 240° arc leaves the bottom of its square empty; report only ~80% of the height so the
    // content below sits close to the arc.
    val trimmed = Modifier.layout { measurable, constraints ->
        val p = measurable.measure(constraints)
        layout(p.width, (p.height * 0.8f).toInt()) { p.place(0, 0) }
    }
    Box(modifier.then(trimmed).size(size).semantics { contentDescription = gaugeDescription }, contentAlignment = Alignment.Center) {
        Canvas(Modifier.fillMaxSize().padding(8.dp)) {
            val stroke = 14.dp.toPx()
            val inset = stroke / 2
            val arcSize = Size(this.size.width - stroke, this.size.height - stroke)
            val topLeft = Offset(inset, inset)
            drawArc(track, start, sweep, false, topLeft, arcSize, style = Stroke(stroke, cap = StrokeCap.Round))
            drawArc(color, start, (sweep * (score / 100.0)).toFloat().coerceIn(0.5f, sweep), false, topLeft, arcSize,
                style = Stroke(stroke, cap = StrokeCap.Round))
            for (b in listOf(25f, 40f, 60f, 75f)) {
                drawArc(tick, start + sweep * b / 100f - 0.6f, 1.2f, false, topLeft, arcSize, style = Stroke(stroke))
            }
        }
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            Text(formatScore(score), style = MaterialTheme.typography.displayMedium)
            Text("/ 100", style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}

fun formatScore(score: Double): String = Math.round(score).toString()

/**
 * Horizontal bar centred on the neutral point. [tilt] in [-half, +half]; fills right when bullish.
 */
@Composable
fun CenteredBar(tilt: Double, half: Double, color: Color, modifier: Modifier = Modifier) {
    val track = MaterialTheme.colorScheme.surfaceContainerHighest
    val mid = MaterialTheme.colorScheme.outline
    Canvas(modifier.height(10.dp)) {
        val r = CornerRadius(size.height / 2, size.height / 2)
        drawRoundRect(track, cornerRadius = r)
        val frac = (tilt / half).coerceIn(-1.0, 1.0).toFloat()
        val cx = size.width / 2
        val w = cx * kotlin.math.abs(frac)
        if (w > 0.5f) {
            val left = if (frac >= 0) cx else cx - w
            drawRoundRect(color, topLeft = Offset(left, 0f), size = Size(w, size.height), cornerRadius = r)
        }
        drawRect(mid, topLeft = Offset(cx - 1f, -2f), size = Size(2f, size.height + 4f))
    }
}

@Composable
fun ImpactArrow(impact: String?, modifier: Modifier = Modifier) {
    val color = LocalSignalColors.current.impact(impact)
    val glyph = when (impact) { "BULLISH" -> "▲"; "BEARISH" -> "▼"; else -> "•" }
    Text(glyph, modifier = modifier, color = color, style = MaterialTheme.typography.labelLarge)
}

@Composable
fun Banner(title: String, body: String?, modifier: Modifier = Modifier, critical: Boolean = true) {
    val sc = LocalSignalColors.current
    val bg = if (critical) MaterialTheme.colorScheme.errorContainer else sc.warningContainer
    val fg = if (critical) MaterialTheme.colorScheme.onErrorContainer else sc.onWarningContainer
    Row(
        modifier.fillMaxWidth().clip(RoundedCornerShape(12.dp)).background(bg).padding(12.dp),
        horizontalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        Icon(painterResource(R.drawable.ic_warning), contentDescription = null, tint = fg, modifier = Modifier.size(20.dp))
        Column {
            Text(title, style = MaterialTheme.typography.labelLarge, fontWeight = FontWeight.Bold, color = fg)
            if (body != null) Text(body, style = MaterialTheme.typography.bodySmall, color = fg)
        }
    }
}

@Composable
fun InfoNote(text: String, modifier: Modifier = Modifier) {
    Row(modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        Icon(painterResource(R.drawable.ic_info), null, Modifier.size(16.dp).padding(top = 2.dp),
            tint = MaterialTheme.colorScheme.onSurfaceVariant)
        Text(text, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

@Composable
fun KeyValueRow(key: String, value: String, modifier: Modifier = Modifier, valueColor: Color = Color.Unspecified) {
    Row(modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
        Text(key, Modifier.weight(1f), style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant)
        Text(value, style = MaterialTheme.typography.bodyMedium.merge(Tabular), fontWeight = FontWeight.Medium,
            color = valueColor, textAlign = TextAlign.End)
    }
}

/** Three small "1D / 7D / 30D" cells. */
@Composable
fun HorizonCells(cells: List<Pair<String, String>>, colors: List<Color>, modifier: Modifier = Modifier) {
    Row(modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        cells.forEachIndexed { i, (label, value) ->
            Column(
                Modifier.weight(1f).clip(RoundedCornerShape(10.dp))
                    .background(MaterialTheme.colorScheme.surfaceContainer).padding(vertical = 8.dp),
                horizontalAlignment = Alignment.CenterHorizontally,
            ) {
                Text(label, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                Text(value, style = MaterialTheme.typography.titleSmall.merge(Tabular), color = colors.getOrElse(i) { Color.Unspecified })
            }
        }
    }
}

@Composable
fun LoadingBox(modifier: Modifier = Modifier) {
    Box(modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
        CircularProgressIndicator()
    }
}

@Composable
fun ErrorBox(
    message: String,
    onRetry: () -> Unit,
    modifier: Modifier = Modifier,
    secondary: Pair<String, () -> Unit>? = null,
) {
    Column(
        modifier.fillMaxSize().padding(32.dp),
        verticalArrangement = Arrangement.Center,
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Text(stringResource(R.string.error_title), style = MaterialTheme.typography.titleMedium)
        Spacer(Modifier.height(8.dp))
        Text(message, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant,
            textAlign = TextAlign.Center)
        Spacer(Modifier.height(16.dp))
        Button(onClick = onRetry) { Text(stringResource(R.string.action_retry)) }
        if (secondary != null) {
            androidx.compose.material3.TextButton(onClick = secondary.second) { Text(secondary.first) }
        }
    }
}

@Composable
fun Disclaimer(modelVersion: String?, modifier: Modifier = Modifier) {
    Column(modifier.fillMaxWidth().padding(vertical = 8.dp), horizontalAlignment = Alignment.CenterHorizontally) {
        Text(
            stringResource(R.string.disclaimer),
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            textAlign = TextAlign.Center,
            modifier = Modifier.widthIn(max = 420.dp),
        )
        if (modelVersion != null) {
            Text(stringResource(R.string.model_version, modelVersion), style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.outline)
        }
    }
}

@Composable
fun Legend(items: List<Pair<String, Color>>, modifier: Modifier = Modifier) {
    Row(modifier, horizontalArrangement = Arrangement.spacedBy(14.dp), verticalAlignment = Alignment.CenterVertically) {
        items.forEach { (label, color) ->
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                Box(Modifier.width(14.dp).height(3.dp).background(color, RoundedCornerShape(2.dp)))
                Text(label, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
        }
    }
}

@Composable
fun Square(modifier: Modifier = Modifier, content: @Composable () -> Unit) {
    Box(modifier.aspectRatio(1f)) { content() }
}
