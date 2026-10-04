package com.goldsignal.core.designsystem

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.PathEffect
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.StrokeJoin
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp

data class ChartLine(val values: List<Double>, val color: Color, val dashed: Boolean = false)

/**
 * Minimal multi-line chart: shared y-range, optional dashed reference level,
 * min/max labels, and first/last x labels. Deliberately simple.
 */
@Composable
fun LineChart(
    lines: List<ChartLine>,
    startLabel: String,
    endLabel: String,
    formatY: (Double) -> String,
    modifier: Modifier = Modifier,
    reference: Double? = null,
    description: String = "",
) {
    val all = lines.flatMap { it.values } + listOfNotNull(reference)
    if (all.isEmpty()) return
    val min = all.min()
    val max = all.max()
    val span = (max - min).takeIf { it > 1e-9 } ?: 1.0
    val grid = MaterialTheme.colorScheme.outlineVariant
    val refColor = MaterialTheme.colorScheme.outline
    Column(modifier.fillMaxWidth()) {
        Row(Modifier.fillMaxWidth()) {
            Text(formatY(max), style = MaterialTheme.typography.labelSmall.merge(Tabular),
                color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        Canvas(Modifier.fillMaxWidth().height(160.dp).semantics { contentDescription = description }) {
            val h = size.height
            val w = size.width
            fun y(v: Double) = (h - (v - min) / span * h).toFloat()
            drawLine(grid, Offset(0f, 0f), Offset(w, 0f), 1f)
            drawLine(grid, Offset(0f, h), Offset(w, h), 1f)
            if (reference != null) {
                drawLine(refColor, Offset(0f, y(reference)), Offset(w, y(reference)), 2f,
                    pathEffect = PathEffect.dashPathEffect(floatArrayOf(10f, 8f)))
            }
            lines.forEach { line ->
                if (line.values.size < 2) return@forEach
                val step = w / (line.values.size - 1)
                val path = Path()
                line.values.forEachIndexed { i, v ->
                    val x = i * step
                    if (i == 0) path.moveTo(x, y(v)) else path.lineTo(x, y(v))
                }
                drawPath(
                    path, line.color,
                    style = Stroke(
                        width = 2.5.dp.toPx(), cap = StrokeCap.Round, join = StrokeJoin.Round,
                        pathEffect = if (line.dashed) PathEffect.dashPathEffect(floatArrayOf(12f, 8f)) else null,
                    ),
                )
                drawCircle(line.color, 4.dp.toPx(), Offset(w, y(line.values.last())))
            }
        }
        Row(Modifier.fillMaxWidth()) {
            Text(formatY(min), style = MaterialTheme.typography.labelSmall.merge(Tabular),
                color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        Row(Modifier.fillMaxWidth()) {
            Text(startLabel, Modifier.weight(1f), style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant)
            Text(endLabel, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}

/** Vertical bars with an optional dashed reference (e.g. a monthly baseline). */
@Composable
fun BarChart(
    values: List<Double>,
    labels: List<String>,
    color: Color,
    modifier: Modifier = Modifier,
    reference: Double? = null,
    description: String = "",
) {
    if (values.isEmpty()) return
    val top = maxOf(values.max(), reference ?: 0.0, 1.0)
    val bottom = minOf(values.min(), 0.0)
    val span = top - bottom
    val refColor = MaterialTheme.colorScheme.outline
    Column(modifier.fillMaxWidth()) {
        Canvas(Modifier.fillMaxWidth().height(120.dp).semantics { contentDescription = description }) {
            val n = values.size
            val slot = size.width / n
            val barW = slot * 0.62f
            fun y(v: Double) = (size.height - (v - bottom) / span * size.height).toFloat()
            values.forEachIndexed { i, v ->
                val x = i * slot + (slot - barW) / 2
                val y0 = y(0.0)
                val y1 = y(v)
                drawRect(color, Offset(x, minOf(y0, y1)), Size(barW, kotlin.math.abs(y0 - y1)))
            }
            if (reference != null) {
                drawLine(refColor, Offset(0f, y(reference)), Offset(size.width, y(reference)), 2f,
                    pathEffect = PathEffect.dashPathEffect(floatArrayOf(10f, 8f)))
            }
        }
        Row(Modifier.fillMaxWidth()) {
            Text(labels.firstOrNull().orEmpty(), Modifier.weight(1f), style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant)
            Text(labels.lastOrNull().orEmpty(), style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}
