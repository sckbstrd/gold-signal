package com.goldsignal

import android.app.Application
import android.content.Context
import androidx.compose.runtime.mutableIntStateOf
import com.goldsignal.data.DataSource
import com.goldsignal.data.GoldRepository
import com.goldsignal.data.mock.MockGoldRepository
import com.goldsignal.data.remote.LiveGoldRepository
import java.io.File

/**
 * Manual dependency container. The data source (live backend or bundled demo) and the
 * server URL are user settings; changing either swaps the repository.
 */
class AppContainer(app: Application) {
    private val prefs = app.getSharedPreferences("settings", Context.MODE_PRIVATE)
    private val cacheDir = File(app.cacheDir, "documents")
    val mock = MockGoldRepository(app.assets)
    private var live: LiveGoldRepository? = null

    /** Snapshot state: reading it from Compose subscribes to settings changes. */
    private val revision = mutableIntStateOf(0)

    var dataSource: DataSource
        get() = runCatching { DataSource.valueOf(prefs.getString(KEY_SOURCE, null) ?: "") }
            .getOrDefault(DataSource.LIVE)
        set(value) {
            prefs.edit().putString(KEY_SOURCE, value.name).apply()
            revision.intValue++
        }

    var serverUrl: String
        get() = prefs.getString(KEY_URL, null)?.takeIf { it.isNotBlank() } ?: BuildConfig.DEFAULT_SERVER_URL
        set(value) {
            prefs.edit().putString(KEY_URL, value.trim()).apply()
            revision.intValue++
        }

    val repository: GoldRepository
        get() = if (dataSource == DataSource.MOCK) mock else liveFor(serverUrl)

    /** Periodic refresh of the dashboard in Live mode (tests switch it off). */
    var autoRefresh: Boolean = true

    /** Changes whenever the effective data source changes (scopes ViewModels; observable from Compose). */
    val repositoryKey: String
        get() {
            revision.intValue
            return if (dataSource == DataSource.MOCK) "mock" else "live:$serverUrl"
        }

    @Synchronized
    private fun liveFor(url: String): LiveGoldRepository {
        val current = live
        if (current != null && current.baseUrl == LiveGoldRepository.normalize(url)) return current
        return LiveGoldRepository(url, cacheDir, demoBacktest = { mock.backtest(it) }).also { live = it }
    }

    companion object {
        private const val KEY_SOURCE = "data_source"
        private const val KEY_URL = "server_url"
    }
}

class GoldSignalApp : Application() {
    lateinit var container: AppContainer
        private set

    override fun onCreate() {
        super.onCreate()
        container = AppContainer(this)
    }
}
