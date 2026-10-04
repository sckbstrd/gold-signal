package com.goldsignal.core.i18n

import androidx.compose.runtime.Composable
import androidx.compose.ui.res.stringResource
import com.goldsignal.R
import com.goldsignal.core.format.Fmt
import com.goldsignal.core.format.rememberFmt
import com.goldsignal.model.Reason
import com.goldsignal.model.num
import com.goldsignal.model.str
import kotlin.math.abs

/**
 * Renders a server reason code in the current language. Every sentence is built from
 * the numbers the model actually used; nothing here is generic filler text.
 * Unknown codes fall back to the raw code so a newer server never crashes an older app.
 */
@Composable
fun reasonText(r: Reason): String {
    val f = rememberFmt()
    val mag = magnitudeText(r.magnitude)
    val bp = { key: String -> r.num(key)?.let { f.bp(it) } ?: "—" }
    val pct = { key: String -> r.num(key)?.let { f.pct(it) } ?: "—" }
    return when (r.code) {
        "WHY_SIGNAL" -> stringResource(R.string.why_signal, signalText(r.str("signal")))
        "WHY_GRAM_SIGNAL" -> stringResource(R.string.why_gram_signal, signalText(r.str("signal")))

        "REAL_YIELD_FALLING" -> stringResource(R.string.r_real_yield_falling, mag, bp("d30_bp"), bp("d7_bp"))
        "REAL_YIELD_RISING" -> stringResource(R.string.r_real_yield_rising, mag, bp("d30_bp"), bp("d7_bp"))
        "REAL_YIELD_FLAT" -> stringResource(R.string.r_real_yield_flat, bp("d30_bp"))

        "FED_PATH_LOWER" -> stringResource(R.string.r_fed_path_lower, mag, bp("d30_bp"), pricedPhrase(r, f))
        "FED_PATH_HIGHER" -> stringResource(R.string.r_fed_path_higher, mag, bp("d30_bp"), pricedPhrase(r, f))
        "FED_PATH_STABLE" -> stringResource(R.string.r_fed_path_stable, pricedPhrase(r, f))

        "DXY_FALLING" -> stringResource(R.string.r_dxy_falling, mag, pct("d30_pct"))
        "DXY_RISING" -> stringResource(R.string.r_dxy_rising, mag, pct("d30_pct"))
        "DXY_FLAT" -> stringResource(R.string.r_dxy_flat, pct("d30_pct"))

        "NOMINAL_LEVEL_ELEVATED" -> stringResource(
            R.string.r_nominal_level_elevated,
            r.num("level_pct")?.let { f.rate(it) } ?: "—", r.num("z_level")?.let { f.num(abs(it), 1) } ?: "—",
        )
        "NOMINAL_LEVEL_LOW" -> stringResource(
            R.string.r_nominal_level_low,
            r.num("level_pct")?.let { f.rate(it) } ?: "—", r.num("z_level")?.let { f.num(abs(it), 1) } ?: "—",
        )
        "BREAKEVENS_RISING" -> stringResource(R.string.r_breakevens_rising, bp("be_d30_bp"))
        "BREAKEVENS_FALLING" -> stringResource(R.string.r_breakevens_falling, bp("be_d30_bp"))
        "NOMINAL_NEUTRAL" -> stringResource(
            R.string.r_nominal_neutral, r.num("level_pct")?.let { f.rate(it) } ?: "—", bp("be_d30_bp"),
        )

        "ECON_DOVISH_SURPRISES" -> stringResource(
            R.string.r_econ_dovish, eventName(r.str("event")), eventValue(r, "actual", f), eventValue(r, "consensus", f),
        )
        "ECON_HAWKISH_SURPRISES" -> stringResource(
            R.string.r_econ_hawkish, eventName(r.str("event")), eventValue(r, "actual", f), eventValue(r, "consensus", f),
        )
        "ECON_MIXED" -> stringResource(R.string.r_econ_mixed, eventName(r.str("top_positive")), eventName(r.str("top_negative")))
        "ECON_QUIET" -> stringResource(R.string.r_econ_quiet)

        "ETF_INFLOWS" -> stringResource(R.string.r_etf_inflows, pct("d30_pct"))
        "ETF_OUTFLOWS" -> stringResource(R.string.r_etf_outflows, pct("d30_pct"))
        "ETF_STABLE" -> stringResource(R.string.r_etf_stable, pct("d30_pct"))

        "CB_BUYING_STRONG" -> stringResource(R.string.r_cb_strong, r.num("t12_tonnes")?.let { f.tonnes(it) } ?: "—")
        "CB_BUYING_WEAK" -> stringResource(R.string.r_cb_weak, r.num("t12_tonnes")?.let { f.tonnes(it) } ?: "—")
        "CB_BUYING_NORMAL" -> stringResource(R.string.r_cb_normal, r.num("t12_tonnes")?.let { f.tonnes(it) } ?: "—")

        "COMPONENT_AGING" -> stringResource(R.string.w_component_aging, componentName(r.str("component")), ageText(r))
        "COMPONENT_STALE" -> stringResource(R.string.w_component_stale, componentName(r.str("component")), ageText(r))
        "COMPONENT_MISSING" -> stringResource(R.string.w_component_missing, componentName(r.str("component")))
        "RELEASE_DELAYED" -> stringResource(
            R.string.w_release_delayed, eventName(r.str("event")), r.str("scheduled")?.let { f.date(it) } ?: "—",
        )
        "PANIC_REGIME" -> stringResource(R.string.w_panic)
        "DEMO_DATA" -> stringResource(R.string.w_demo_data)
        "COVERAGE_GAP" -> stringResource(
            R.string.w_coverage_gap, componentName(r.str("component")), r.num("neutral_days_pct")?.let { f.pct(it, 0, false) } ?: "—",
        )

        "MOST_FAVOR" -> stringResource(R.string.c_most_favor)
        "MOST_FAVOR_WITH_RISK" -> stringResource(R.string.c_most_favor_with_risk, componentName(r.str("risk")))
        "MOST_OPPOSE" -> stringResource(R.string.c_most_oppose)
        "MOST_OPPOSE_WITH_SUPPORT" -> stringResource(R.string.c_most_oppose_with_support, componentName(r.str("support")))
        "HOLD_MIXED" -> stringResource(R.string.c_hold_mixed, componentName(r.str("support")), componentName(r.str("risk")))
        "HOLD_LEANING" -> stringResource(
            if (r.str("direction") == "POSITIVE") R.string.c_hold_leaning_positive else R.string.c_hold_leaning_negative,
        )
        "HOLD_QUIET" -> stringResource(R.string.c_hold_quiet)
        "PANIC_CAUTION" -> stringResource(R.string.c_panic_caution)

        "GRAM_GLOBAL_DRIVER" -> stringResource(
            R.string.r_gram_global_driver, signalText(r.str("global_signal")), r.num("global_score")?.let { f.num(it, 1) } ?: "—",
        )
        "GRAM_FX_TRY_WEAKER_THAN_CARRY" -> stringResource(R.string.r_gram_fx_weaker, pct("d30_pct"), pct("carry_30d_pct"))
        "GRAM_FX_TRY_STRONGER_THAN_CARRY" -> stringResource(R.string.r_gram_fx_stronger, pct("d30_pct"), pct("carry_30d_pct"))
        "GRAM_FX_IN_LINE_WITH_CARRY" -> stringResource(R.string.r_gram_fx_in_line, pct("d30_pct"), pct("carry_30d_pct"))
        "GRAM_FOLLOWS_GLOBAL" -> stringResource(R.string.c_gram_follows_global)
        "GRAM_FX_DRIVEN" -> stringResource(
            if (r.str("direction") == "POSITIVE") R.string.c_gram_fx_driven_positive else R.string.c_gram_fx_driven_negative,
        )
        "GRAM_DRIVERS_ALIGNED" -> stringResource(R.string.c_gram_aligned)
        "GRAM_DRIVERS_OFFSET" -> stringResource(R.string.c_gram_offset)
        else -> r.code
    }
}

@Composable
private fun pricedPhrase(r: Reason, f: Fmt): String {
    val priced = r.num("priced_12m_bp") ?: return ""
    val amount = "${f.num(abs(priced), 0)} ${if (f.locale.language == "ru") "б.п." else "bp"}"
    return if (priced < 0) stringResource(R.string.priced_cuts, amount) else stringResource(R.string.priced_hikes, amount)
}

@Composable
private fun ageText(r: Reason): String = r.num("age_bdays")?.toInt()?.let { businessDays(it) } ?: "—"

private fun eventValue(r: Reason, key: String, f: Fmt): String {
    val v = r.num(key) ?: return "—"
    val code = r.str("event") ?: return f.num(v, 1)
    return when {
        eventUnitIsPercent(code) -> f.pct(v, 1, signed = false)
        eventUnitIsThousands(code) -> "${f.num(v, 0)}K"
        else -> f.num(v, 1)
    }
}
