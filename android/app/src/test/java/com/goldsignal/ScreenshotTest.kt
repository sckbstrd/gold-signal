package com.goldsignal

import androidx.activity.ComponentActivity
import androidx.compose.runtime.Composable
import androidx.compose.ui.semantics.ProgressBarRangeInfo
import androidx.compose.ui.test.hasProgressBarRangeInfo
import androidx.compose.ui.test.junit4.v2.createAndroidComposeRule
import androidx.compose.ui.test.onRoot
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.onNodeWithText
import androidx.test.platform.app.InstrumentationRegistry
import com.github.takahirom.roborazzi.captureRoboImage
import com.goldsignal.core.designsystem.GoldSignalTheme
import com.goldsignal.feature.backtest.BacktestScreen
import com.goldsignal.feature.dashboard.DashboardScreen
import com.goldsignal.feature.events.EventsScreen
import com.goldsignal.feature.indicator.IndicatorScreen
import com.goldsignal.feature.settings.SettingsScreen
import com.goldsignal.feature.why.WhyScreen
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.RuntimeEnvironment
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode

/**
 * Renders every screen on the JVM against the bundled engine fixtures, in all three
 * languages. Run: ./gradlew :app:recordRoborazziDebug  (PNGs in app/build/outputs/roborazzi)
 */
@RunWith(RobolectricTestRunner::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [35], qualifiers = "w400dp-h2400dp-xhdpi")
class ScreenshotTest {
    @get:Rule
    val rule = createAndroidComposeRule<ComponentActivity>()

    @org.junit.Before
    fun demoMode() {
        // The app defaults to live data; screenshots render the bundled demo (no network in tests).
        (androidx.test.core.app.ApplicationProvider.getApplicationContext<android.content.Context>() as GoldSignalApp)
            .container.dataSource = com.goldsignal.data.DataSource.MOCK
    }

    private fun shot(name: String, qualifiers: String = "en", content: @Composable () -> Unit) {
        RuntimeEnvironment.setQualifiers("+$qualifiers")
        rule.setContent { GoldSignalTheme { content() } }
        awaitLoaded()
        rule.onRoot().captureRoboImage("build/outputs/roborazzi/$name.png")
    }

    private fun awaitLoaded() {
        rule.waitUntil(10_000) {
            rule.onAllNodes(hasProgressBarRangeInfo(ProgressBarRangeInfo.Indeterminate))
                .fetchSemanticsNodes().isEmpty()
        }
        rule.waitForIdle()
    }

    @Test fun dashboardEn() = shot("01_dashboard_en") { DashboardScreen({}, {}, {}) }
    @Test fun dashboardTr() = shot("02_dashboard_tr", "tr") { DashboardScreen({}, {}, {}) }
    @Test fun dashboardRu() = shot("03_dashboard_ru", "ru") { DashboardScreen({}, {}, {}) }
    @Test fun dashboardDark() = shot("04_dashboard_en_dark", "night") { DashboardScreen({}, {}, {}) }
    @Test fun whyGlobalEn() = shot("05_why_global_en") { WhyScreen(0) {} }
    @Test fun whyGramTr() = shot("06_why_gram_tr", "tr") { WhyScreen(1) {} }
    @Test fun whyGlobalRu() = shot("07_why_global_ru", "ru") { WhyScreen(0) {} }
    @Test fun realYieldEn() = shot("08_indicator_real_yield_en") { IndicatorScreen("REAL_YIELD") {} }
    @Test fun fedEn() = shot("09_indicator_fed_en") { IndicatorScreen("FED") {} }
    @Test fun nominalRu() = shot("10_indicator_nominal_ru", "ru") { IndicatorScreen("NOMINAL_10Y") {} }
    @Test fun econEn() = shot("11_indicator_econ_en") { IndicatorScreen("ECON") {} }
    @Test fun centralBanksEn() = shot("12_indicator_cb_en") { IndicatorScreen("CENTRAL_BANKS") {} }
    @Test fun gramTr() = shot("13_indicator_gram_tr", "tr") { IndicatorScreen("GRAM_TRY") {} }
    @Test fun eventsEn() = shot("14_events_en") { EventsScreen() }
    @Test fun settingsRu() = shot("16_settings_ru", "ru") { SettingsScreen() }
    @Test fun historyEn() = shot("17_history_en") { com.goldsignal.feature.history.HistoryScreen {} }
    @Test fun historyTr() = shot("18_history_tr", "tr") { com.goldsignal.feature.history.HistoryScreen {} }

    @Test
    fun backtestEn() {
        RuntimeEnvironment.setQualifiers("+en")
        rule.setContent { GoldSignalTheme { BacktestScreen() } }
        val run = InstrumentationRegistry.getInstrumentation().targetContext.getString(R.string.bt_run)
        rule.onNodeWithText(run).performClick()
        awaitLoaded()
        rule.waitUntil(10_000) { rule.onAllNodes(androidx.compose.ui.test.hasText("Equity curve", ignoreCase = true)).fetchSemanticsNodes().isNotEmpty() }
        rule.onRoot().captureRoboImage("build/outputs/roborazzi/15_backtest_en.png")
    }
}
