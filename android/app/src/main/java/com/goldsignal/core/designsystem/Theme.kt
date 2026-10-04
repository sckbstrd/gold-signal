package com.goldsignal.core.designsystem

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Typography
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.Immutable
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.sp
import com.goldsignal.model.SignalLabel

private val LightColors = lightColorScheme(
    primary = Color(0xFF7D5A0C),
    onPrimary = Color(0xFFFFFFFF),
    primaryContainer = Color(0xFFF5E1B0),
    onPrimaryContainer = Color(0xFF281900),
    secondary = Color(0xFF6A5D45),
    onSecondary = Color(0xFFFFFFFF),
    secondaryContainer = Color(0xFFF1E1C1),
    onSecondaryContainer = Color(0xFF231A07),
    background = Color(0xFFFBF8F1),
    onBackground = Color(0xFF1D1B16),
    surface = Color(0xFFFBF8F1),
    onSurface = Color(0xFF1D1B16),
    surfaceVariant = Color(0xFFEAE2D0),
    onSurfaceVariant = Color(0xFF4C4639),
    surfaceContainerLowest = Color(0xFFFFFFFF),
    surfaceContainerLow = Color(0xFFF6F2E8),
    surfaceContainer = Color(0xFFF1ECE1),
    surfaceContainerHigh = Color(0xFFEBE6DB),
    surfaceContainerHighest = Color(0xFFE5E0D5),
    outline = Color(0xFF7E7667),
    outlineVariant = Color(0xFFD0C6B4),
    error = Color(0xFFB3261E),
)

private val DarkColors = darkColorScheme(
    primary = Color(0xFFE9C26A),
    onPrimary = Color(0xFF412D00),
    primaryContainer = Color(0xFF5E4300),
    onPrimaryContainer = Color(0xFFF5E1B0),
    secondary = Color(0xFFD6C5A4),
    onSecondary = Color(0xFF3A2F1A),
    secondaryContainer = Color(0xFF51452F),
    onSecondaryContainer = Color(0xFFF1E1C1),
    background = Color(0xFF15140F),
    onBackground = Color(0xFFE8E2D6),
    surface = Color(0xFF15140F),
    onSurface = Color(0xFFE8E2D6),
    surfaceVariant = Color(0xFF4C4639),
    onSurfaceVariant = Color(0xFFCFC6B4),
    surfaceContainerLowest = Color(0xFF100F0B),
    surfaceContainerLow = Color(0xFF1D1C17),
    surfaceContainer = Color(0xFF21201B),
    surfaceContainerHigh = Color(0xFF2C2A25),
    surfaceContainerHighest = Color(0xFF37352F),
    outline = Color(0xFF999080),
    outlineVariant = Color(0xFF4C4639),
    error = Color(0xFFF2B8B5),
)

/** Signal colours are always paired with a text label; never colour alone. */
@Immutable
data class SignalColors(
    val strongBuy: Color,
    val buy: Color,
    val hold: Color,
    val reduce: Color,
    val sell: Color,
    val bullish: Color,
    val bearish: Color,
    val neutral: Color,
    val warning: Color,
    val warningContainer: Color,
    val onWarningContainer: Color,
) {
    fun of(label: SignalLabel): Color = when (label) {
        SignalLabel.STRONG_BUY -> strongBuy
        SignalLabel.BUY -> buy
        SignalLabel.HOLD -> hold
        SignalLabel.REDUCE -> reduce
        SignalLabel.SELL -> sell
    }

    fun impact(impact: String?): Color = when (impact) {
        "BULLISH" -> bullish
        "BEARISH" -> bearish
        else -> neutral
    }
}

private val LightSignals = SignalColors(
    strongBuy = Color(0xFF0B6B3A), buy = Color(0xFF2E8B57), hold = Color(0xFFA67C00),
    reduce = Color(0xFFC25E12), sell = Color(0xFFB3261E),
    bullish = Color(0xFF2E7D4F), bearish = Color(0xFFB3261E), neutral = Color(0xFF7E7667),
    warning = Color(0xFF9A5B00), warningContainer = Color(0xFFFFE3B8), onWarningContainer = Color(0xFF2E1800),
)

private val DarkSignals = SignalColors(
    strongBuy = Color(0xFF5FD49A), buy = Color(0xFF8BD3A5), hold = Color(0xFFE9C26A),
    reduce = Color(0xFFF2A35E), sell = Color(0xFFF2B8B5),
    bullish = Color(0xFF8BD3A5), bearish = Color(0xFFF2B8B5), neutral = Color(0xFFA9A091),
    warning = Color(0xFFFFB95C), warningContainer = Color(0xFF4A2C00), onWarningContainer = Color(0xFFFFE3B8),
)

val LocalSignalColors = staticCompositionLocalOf { LightSignals }

/** Tabular figures keep prices and scores from jittering. */
val Tabular = TextStyle(fontFeatureSettings = "tnum")

private val AppTypography = Typography().let { base ->
    base.copy(
        displayLarge = base.displayLarge.copy(fontWeight = FontWeight.SemiBold, fontFeatureSettings = "tnum"),
        displayMedium = base.displayMedium.copy(fontWeight = FontWeight.SemiBold, fontFeatureSettings = "tnum"),
        headlineSmall = base.headlineSmall.copy(fontWeight = FontWeight.SemiBold),
        titleMedium = base.titleMedium.copy(fontWeight = FontWeight.SemiBold),
        labelSmall = base.labelSmall.copy(letterSpacing = 0.8.sp),
    )
}

@Composable
fun GoldSignalTheme(dark: Boolean = isSystemInDarkTheme(), content: @Composable () -> Unit) {
    CompositionLocalProvider(LocalSignalColors provides if (dark) DarkSignals else LightSignals) {
        MaterialTheme(
            colorScheme = if (dark) DarkColors else LightColors,
            typography = AppTypography,
            content = content,
        )
    }
}
