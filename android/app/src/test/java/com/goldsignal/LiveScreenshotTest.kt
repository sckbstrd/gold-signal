package com.goldsignal

import android.content.Context
import androidx.activity.ComponentActivity
import androidx.compose.runtime.Composable
import androidx.compose.ui.semantics.ProgressBarRangeInfo
import androidx.compose.ui.test.hasProgressBarRangeInfo
import androidx.compose.ui.test.junit4.v2.createAndroidComposeRule
import androidx.compose.ui.test.onRoot
import androidx.test.core.app.ApplicationProvider
import com.github.takahirom.roborazzi.captureRoboImage
import com.goldsignal.core.designsystem.GoldSignalTheme
import com.goldsignal.data.DataSource
import com.goldsignal.feature.dashboard.DashboardScreen
import com.goldsignal.feature.history.HistoryScreen
import com.goldsignal.feature.indicator.IndicatorScreen
import com.goldsignal.feature.settings.SettingsScreen
import com.goldsignal.feature.why.WhyScreen
import mockwebserver3.Dispatcher
import mockwebserver3.MockResponse
import mockwebserver3.MockWebServer
import mockwebserver3.RecordedRequest
import org.junit.After
import org.junit.Assume.assumeTrue
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.RuntimeEnvironment
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode
import java.io.File

/**
 * The real app in Live mode against a REAL published site served locally.
 * Run with GS_LIVE_SITE=/path/to/site; skipped otherwise.
 */
@RunWith(RobolectricTestRunner::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [35], qualifiers = "w400dp-h2400dp-xhdpi")
class LiveScreenshotTest {
    @get:Rule
    val rule = createAndroidComposeRule<ComponentActivity>()
    private val site = System.getenv("GS_LIVE_SITE")?.let(::File)
    private val server = MockWebServer()

    @Before
    fun setUp() {
        assumeTrue("GS_LIVE_SITE not set", site != null && site.isDirectory)
        server.dispatcher = object : Dispatcher() {
            override fun dispatch(request: RecordedRequest): MockResponse {
                val file = File(site, request.target.removePrefix("/"))
                return if (file.isFile) MockResponse.Builder().body(file.readText()).build()
                else MockResponse.Builder().code(404).build()
            }
        }
        server.start()
        val container = (ApplicationProvider.getApplicationContext<Context>() as GoldSignalApp).container
        container.dataSource = DataSource.LIVE
        container.serverUrl = server.url("/api/v1/").toString()
    }

    @After
    fun tearDown() = server.close()

    private fun shot(name: String, qualifiers: String = "en", content: @Composable () -> Unit) {
        RuntimeEnvironment.setQualifiers("+$qualifiers")
        rule.setContent { GoldSignalTheme { content() } }
        rule.waitUntil(15_000) {
            rule.onAllNodes(hasProgressBarRangeInfo(ProgressBarRangeInfo.Indeterminate)).fetchSemanticsNodes().isEmpty()
        }
        rule.waitForIdle()
        rule.onRoot().captureRoboImage("build/outputs/roborazzi/live_$name.png")
    }

    @Test fun dashboard() = shot("01_dashboard_en") { DashboardScreen({}, {}, {}) }
    @Test fun dashboardTr() = shot("02_dashboard_tr", "tr") { DashboardScreen({}, {}, {}) }
    @Test fun why() = shot("03_why_en") { WhyScreen(0) {} }
    @Test fun whyGramRu() = shot("04_why_gram_ru", "ru") { WhyScreen(1) {} }
    @Test fun history() = shot("05_history_en") { HistoryScreen {} }
    @Test fun econ() = shot("06_econ_en") { IndicatorScreen("ECON") {} }
    @Test fun fed() = shot("07_fed_en") { IndicatorScreen("FED") {} }
    @Test fun settings() = shot("08_settings_en") { SettingsScreen() }
}
