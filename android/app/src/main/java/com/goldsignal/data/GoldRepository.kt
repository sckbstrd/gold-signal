package com.goldsignal.data

import com.goldsignal.model.BacktestRequest
import com.goldsignal.model.BacktestResponse
import com.goldsignal.model.CurrentResponse
import com.goldsignal.model.EventsResponse
import com.goldsignal.model.HealthResponse
import com.goldsignal.model.HistoryReport
import com.goldsignal.model.HistoryResponse
import com.goldsignal.model.IndicatorDetail
import com.goldsignal.model.SignalResponse
import kotlinx.serialization.ExperimentalSerializationApi
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonNamingStrategy

/**
 * The app's only gateway to data. [com.goldsignal.data.mock.MockGoldRepository] serves the bundled
 * demo; [com.goldsignal.data.remote.LiveGoldRepository] serves the backend (REST or static copy).
 */
interface GoldRepository {
    val source: DataSource

    /** Where the last response came from; lets the UI say "offline, showing cached data". */
    val freshness: FetchInfo get() = FetchInfo.LIVE

    suspend fun signal(): SignalResponse
    suspend fun current(): CurrentResponse
    suspend fun indicator(code: String): IndicatorDetail
    suspend fun events(): EventsResponse
    suspend fun history(): HistoryResponse
    suspend fun historyReport(): HistoryReport
    suspend fun health(): HealthResponse
    suspend fun backtest(request: BacktestRequest): BacktestResponse
}

enum class DataSource { MOCK, LIVE }

data class FetchInfo(val fromCache: Boolean, val cachedAtMillis: Long?) {
    companion object {
        val LIVE = FetchInfo(false, null)
    }
}

@OptIn(ExperimentalSerializationApi::class)
val AppJson: Json = Json {
    namingStrategy = JsonNamingStrategy.SnakeCase
    ignoreUnknownKeys = true
    explicitNulls = false
    coerceInputValues = true
}
