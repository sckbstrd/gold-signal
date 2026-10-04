package com.goldsignal.core.format

import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.platform.LocalConfiguration
import java.text.NumberFormat
import java.time.LocalDate
import java.time.OffsetDateTime
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.time.format.FormatStyle
import java.util.Locale
import kotlin.math.abs

/**
 * Locale-aware number formatting. Pure JVM (no Android types) so it is unit-testable.
 *
 * Conventions:  EN  $4,180.50  ₺6,700.15  +0.60%   −28 bp
 *               TR  $4.180,50  ₺6.700,15  +%0,60   −28 bp
 *               RU  4 180,50 $ 6 700,15 ₺ +0,60 %  −28 б.п.
 */
class Fmt(val locale: Locale) {
    private val lang = locale.language

    fun num(v: Double, decimals: Int = 2): String =
        NumberFormat.getNumberInstance(locale).apply {
            minimumFractionDigits = decimals
            maximumFractionDigits = decimals
        }.format(v).replace('-', MINUS)

    fun signed(v: Double, decimals: Int = 2): String {
        val body = num(abs(v), decimals)
        return when {
            isZero(v, decimals) -> body
            v > 0 -> "+$body"
            else -> "$MINUS$body"
        }
    }

    private fun isZero(v: Double, decimals: Int) = abs(v) < 0.5 * Math.pow(10.0, -decimals.toDouble())

    /** Percent with the locale's sign placement. */
    fun pct(v: Double, decimals: Int = 2, signed: Boolean = true): String {
        val sign = when {
            !signed || isZero(v, decimals) -> ""
            v > 0 -> "+"
            else -> MINUS.toString()
        }
        val body = num(if (signed) abs(v) else v, decimals)
        return when (lang) {
            "tr" -> "$sign%$body"
            "ru" -> "$sign$body %"
            else -> "$sign$body%"
        }
    }

    fun bp(v: Double, decimals: Int = 0): String {
        val unit = if (lang == "ru") "б.п." else "bp"
        return "${signed(v, decimals)} $unit"
    }

    fun usd(v: Double): String = money(v, "$")

    fun tryAmount(v: Double): String = money(v, "₺")

    private fun money(v: Double, symbol: String): String =
        if (lang == "ru") "${num(v)} $symbol" else "$symbol${num(v)}"

    fun tonnes(v: Double, signed: Boolean = false): String {
        val unit = if (lang == "ru") "т" else "t"
        return "${if (signed) signed(v, 0) else num(v, 0)} $unit"
    }

    fun rate(v: Double, decimals: Int = 2): String = pct(v, decimals, signed = false)

    fun date(iso: String): String = runCatching {
        LocalDate.parse(iso.take(10)).format(DateTimeFormatter.ofLocalizedDate(FormatStyle.MEDIUM).withLocale(locale))
    }.getOrDefault(iso)

    fun shortDate(iso: String): String = runCatching {
        val pattern = if (lang == "en") "MMM d" else "d MMM"
        LocalDate.parse(iso.take(10)).format(DateTimeFormatter.ofPattern(pattern, locale))
    }.getOrDefault(iso)

    /** Chart axis label: day + month for short ranges, month + year for long ones. */
    fun axisDate(iso: String, rangeDays: Long): String = if (rangeDays > 92) monthYear(iso) else shortDate(iso)

    fun monthYear(iso: String): String = runCatching {
        LocalDate.parse(iso.take(7) + "-01").format(DateTimeFormatter.ofPattern("MMM yyyy", locale))
    }.getOrDefault(iso)

    /** Timestamp converted to the device time zone. */
    fun dateTime(iso: String, zone: ZoneId = ZoneId.systemDefault()): String = runCatching {
        OffsetDateTime.parse(iso).atZoneSameInstant(zone)
            .format(DateTimeFormatter.ofLocalizedDateTime(FormatStyle.MEDIUM, FormatStyle.SHORT).withLocale(locale))
    }.getOrDefault(iso)

    fun dateTimeMillis(millis: Long, zone: ZoneId = ZoneId.systemDefault()): String =
        java.time.Instant.ofEpochMilli(millis).atZone(zone)
            .format(DateTimeFormatter.ofLocalizedDateTime(FormatStyle.MEDIUM, FormatStyle.SHORT).withLocale(locale))

    companion object {
        const val MINUS = '−'
    }
}

@Composable
fun rememberFmt(): Fmt {
    val locale = LocalConfiguration.current.locales[0]
    return remember(locale) { Fmt(locale) }
}
