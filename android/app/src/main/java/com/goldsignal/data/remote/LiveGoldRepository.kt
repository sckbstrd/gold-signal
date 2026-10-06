package com.goldsignal.data.remote

import com.goldsignal.data.AppJson
import com.goldsignal.data.DataSource
import com.goldsignal.data.FetchInfo
import com.goldsignal.data.GoldRepository
import com.goldsignal.model.BacktestRequest
import com.goldsignal.model.BacktestResponse
import com.goldsignal.model.CurrentResponse
import com.goldsignal.model.EventsResponse
import com.goldsignal.model.HealthResponse
import com.goldsignal.model.HistoryReport
import com.goldsignal.model.HistoryResponse
import com.goldsignal.model.IndicatorDetail
import com.goldsignal.model.ProvisionalResponse
import com.goldsignal.model.SignalResponse
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.KSerializer
import kotlinx.serialization.serializer
import okhttp3.OkHttpClient
import okhttp3.Request
import java.io.File
import java.io.IOException
import java.util.concurrent.TimeUnit

/**
 * Reads the backend's documents: `<base>/gold/signal.json` etc. Works against the REST API
 * and the static GitHub Pages copy alike (both accept the ".json" suffix).
 *
 * Offline-first: every successful response is cached on disk; when the network fails the last
 * cached copy is returned and [freshness] reports it, so the UI can say "offline".
 */
class LiveGoldRepository(
    baseUrl: String,
    private val cacheDir: File,
    private val demoBacktest: suspend (BacktestRequest) -> BacktestResponse,
    private val client: OkHttpClient = defaultClient(),
) : GoldRepository {
    val baseUrl: String = normalize(baseUrl)
    override val source = DataSource.LIVE

    @Volatile
    override var freshness: FetchInfo = FetchInfo.LIVE
        private set

    private fun cacheFile(path: String) = File(cacheDir, path.replace('/', '_') + ".json")

    private suspend fun <T> doc(path: String, serializer: KSerializer<T>): T = withContext(Dispatchers.IO) {
        val file = cacheFile(path)
        try {
            // 5-minute cache-buster: the static host's CDN would otherwise serve copies up to 10 minutes old.
            val request = Request.Builder().url(baseUrl + path + ".json?t=" + System.currentTimeMillis() / 300_000).header("Accept", "application/json").build()
            val body = client.newCall(request).execute().use { r ->
                if (!r.isSuccessful) throw IOException("HTTP ${r.code} for $path")
                r.body.string()
            }
            val parsed = AppJson.decodeFromString(serializer, body)     // validate before caching
            file.parentFile?.mkdirs()
            file.writeText(body)
            freshness = FetchInfo.LIVE
            parsed
        } catch (e: IOException) {
            if (!file.exists()) throw e
            freshness = FetchInfo(true, file.lastModified())
            AppJson.decodeFromString(serializer, file.readText())
        }
    }

    override suspend fun signal(): SignalResponse = doc("gold/signal", serializer())
    override suspend fun current(): CurrentResponse = doc("gold/current", serializer())
    override suspend fun indicator(code: String): IndicatorDetail = doc("gold/indicators/$code", serializer())
    override suspend fun events(): EventsResponse = doc("economic-events", serializer())
    override suspend fun history(): HistoryResponse = doc("gold/history", serializer())
    override suspend fun historyReport(): HistoryReport = doc("gold/history/report", serializer())
    override suspend fun health(): HealthResponse = doc("health/data", serializer())
    override suspend fun provisional(): ProvisionalResponse = doc("gold/provisional", serializer())

    /** The real backtest is Phase 6; until then the clearly flagged demo is shown in both modes. */
    override suspend fun backtest(request: BacktestRequest): BacktestResponse = demoBacktest(request)

    companion object {
        fun normalize(url: String): String = url.trim().let { if (it.endsWith("/")) it else "$it/" }

        fun defaultClient(): OkHttpClient = OkHttpClient.Builder()
            .connectTimeout(15, TimeUnit.SECONDS)
            .readTimeout(30, TimeUnit.SECONDS)
            .build()
    }
}
