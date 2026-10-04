package com.goldsignal.core.i18n

import androidx.compose.runtime.Composable
import androidx.compose.ui.res.pluralStringResource
import androidx.compose.ui.res.stringResource
import com.goldsignal.R
import com.goldsignal.model.Regime
import com.goldsignal.model.SignalLabel

@Composable
fun signalText(label: SignalLabel): String = stringResource(
    when (label) {
        SignalLabel.STRONG_BUY -> R.string.signal_strong_buy
        SignalLabel.BUY -> R.string.signal_buy
        SignalLabel.HOLD -> R.string.signal_hold
        SignalLabel.REDUCE -> R.string.signal_reduce
        SignalLabel.SELL -> R.string.signal_sell
    },
)

@Composable
fun signalText(code: String?): String =
    code?.let { c -> SignalLabel.entries.firstOrNull { it.name == c }?.let { signalText(it) } ?: c } ?: "—"

@Composable
fun regimeText(regime: Regime): String = stringResource(
    when (regime) {
        Regime.GOLD_BULL -> R.string.regime_gold_bull
        Regime.GOLD_BEAR -> R.string.regime_gold_bear
        Regime.TRANSITION -> R.string.regime_transition
        Regime.PANIC -> R.string.regime_panic
    },
)

@Composable
fun regimeDescription(regime: Regime): String = stringResource(
    when (regime) {
        Regime.GOLD_BULL -> R.string.regime_desc_bull
        Regime.GOLD_BEAR -> R.string.regime_desc_bear
        Regime.TRANSITION -> R.string.regime_desc_transition
        Regime.PANIC -> R.string.regime_desc_panic
    },
)

fun componentNameRes(code: String): Int? = when (code) {
    "REAL_YIELD" -> R.string.comp_real_yield
    "FED" -> R.string.comp_fed
    "DXY" -> R.string.comp_dxy
    "NOMINAL_10Y" -> R.string.comp_nominal
    "ECON" -> R.string.comp_econ
    "ETF" -> R.string.comp_etf
    "CENTRAL_BANKS" -> R.string.comp_cb
    "FX_USDTRY" -> R.string.comp_fx
    "GRAM_TRY" -> R.string.comp_gram
    else -> null
}

@Composable
fun componentName(code: String?): String =
    code?.let { componentNameRes(it)?.let { res -> stringResource(res) } ?: it } ?: "—"

@Composable
fun impactText(impact: String?): String = when (impact) {
    "BULLISH" -> stringResource(R.string.impact_bullish)
    "BEARISH" -> stringResource(R.string.impact_bearish)
    else -> stringResource(R.string.impact_neutral)
}

@Composable
fun trendText(trend: String?): String = when (trend) {
    "FALLING" -> stringResource(R.string.trend_falling)
    "RISING" -> stringResource(R.string.trend_rising)
    else -> stringResource(R.string.trend_flat)
}

@Composable
fun statusText(status: String?): String = when (status) {
    "FRESH" -> stringResource(R.string.status_fresh)
    "AGING" -> stringResource(R.string.status_aging)
    "STALE" -> stringResource(R.string.status_stale)
    "MISSING" -> stringResource(R.string.status_missing)
    "MOCK" -> stringResource(R.string.status_mock)
    else -> status ?: "—"
}

@Composable
fun eventName(code: String?): String = when (code) {
    "CPI_YOY" -> stringResource(R.string.event_cpi_yoy)
    "CORE_CPI_MOM" -> stringResource(R.string.event_core_cpi_mom)
    "PCE_YOY" -> stringResource(R.string.event_pce_yoy)
    "CORE_PCE_MOM" -> stringResource(R.string.event_core_pce_mom)
    "NFP" -> stringResource(R.string.event_nfp)
    "UNEMPLOYMENT" -> stringResource(R.string.event_unemployment)
    "INITIAL_CLAIMS" -> stringResource(R.string.event_initial_claims)
    "ISM_MFG" -> stringResource(R.string.event_ism_mfg)
    "ISM_SERVICES" -> stringResource(R.string.event_ism_services)
    "FOMC_DECISION" -> stringResource(R.string.event_fomc)
    null -> stringResource(R.string.none)
    else -> code
}

@Composable
fun magnitudeText(magnitude: String?): String = when (magnitude) {
    "LITTLE" -> stringResource(R.string.mag_little)
    "MODERATE" -> stringResource(R.string.mag_moderate)
    "SIGNIFICANT" -> stringResource(R.string.mag_significant)
    "SHARP" -> stringResource(R.string.mag_sharp)
    else -> ""
}

@Composable
fun businessDays(n: Int): String = pluralStringResource(R.plurals.business_days, n, n)

@Composable
fun calendarDays(n: Int): String = pluralStringResource(R.plurals.calendar_days, n, n)

/** Unit-aware value for an event (CPI in %, NFP in thousands, ISM index points). */
fun eventUnitIsPercent(code: String): Boolean =
    code in setOf("CPI_YOY", "CORE_CPI_MOM", "PCE_YOY", "CORE_PCE_MOM", "UNEMPLOYMENT")

fun eventUnitIsThousands(code: String): Boolean = code in setOf("NFP", "INITIAL_CLAIMS")
