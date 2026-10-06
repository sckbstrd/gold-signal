package com.goldsignal

import com.goldsignal.data.AppJson
import com.goldsignal.model.CentralBankExtra
import com.goldsignal.model.CurrentResponse
import com.goldsignal.model.EconExtra
import com.goldsignal.model.EventsResponse
import com.goldsignal.model.FedExtra
import com.goldsignal.model.GramExtra
import com.goldsignal.model.HealthResponse
import com.goldsignal.model.HistoryReport
import com.goldsignal.model.HistoryResponse
import com.goldsignal.model.IndicatorDetail
import com.goldsignal.model.NominalExtra
import com.goldsignal.model.SignalResponse
import kotlinx.serialization.json.decodeFromJsonElement
import org.junit.Assume.assumeTrue
import org.junit.Test
import java.io.File

/**
 * Decodes every document of a REAL published site (not the demo fixtures).
 * Run with:  GS_LIVE_SITE=/path/to/site ./gradlew :app:testDebugUnitTest
 * Skipped when the variable is not set.
 */
class LiveSiteContractTest {
    private val root = System.getenv("GS_LIVE_SITE")?.let { File(it, "api/v1") }

    private inline fun <reified T> load(path: String): T =
        AppJson.decodeFromString(File(root, "$path.json").readText(Charsets.UTF_8))

    @Test
    fun everyLiveDocumentDecodes() {
        assumeTrue("GS_LIVE_SITE not set", root != null && root.isDirectory)
        load<SignalResponse>("gold/signal")
        load<CurrentResponse>("gold/current")
        load<EventsResponse>("economic-events")
        load<HealthResponse>("health/data")
        load<HistoryReport>("gold/history/report")
        if (File(root, "gold/provisional.json").exists()) load<com.goldsignal.model.ProvisionalResponse>("gold/provisional")
        check(load<HistoryResponse>("gold/history").rows().size > 1000)
        for (code in listOf("REAL_YIELD", "FED", "DXY", "NOMINAL_10Y", "ECON", "ETF", "CENTRAL_BANKS", "GRAM_TRY")) {
            val d = load<IndicatorDetail>("gold/indicators/$code")
            when (code) {
                "FED" -> AppJson.decodeFromJsonElement<FedExtra>(d.extra)
                "NOMINAL_10Y" -> AppJson.decodeFromJsonElement<NominalExtra>(d.extra)
                "ECON" -> AppJson.decodeFromJsonElement<EconExtra>(d.extra)
                "GRAM_TRY" -> AppJson.decodeFromJsonElement<GramExtra>(d.extra)
                "CENTRAL_BANKS" -> if (d.status != "MISSING") AppJson.decodeFromJsonElement<CentralBankExtra>(d.extra)
            }
        }
    }
}
