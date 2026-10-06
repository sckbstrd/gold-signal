package com.goldsignal

import com.goldsignal.data.remote.LiveGoldRepository
import kotlinx.coroutines.test.runTest
import mockwebserver3.MockResponse
import mockwebserver3.MockWebServer
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder
import java.io.File
import java.io.IOException

/** Live repository: reads `<base>/<path>.json`, caches every good response, falls back offline. */
class LiveRepositoryTest {
    @get:Rule
    val tmp = TemporaryFolder()

    private val server = MockWebServer()
    private val fixtures = listOf(File("src/main/assets/mock"), File("app/src/main/assets/mock")).first { it.isDirectory }
    private fun fixture(name: String) = File(fixtures, name).readText()

    @Before
    fun start() = server.start()

    @After
    fun stop() = server.close()

    private fun repo() = LiveGoldRepository(
        server.url("/api/v1").toString(), tmp.root, demoBacktest = { error("not used") })

    @Test
    fun readsDocumentsWithJsonSuffix() = runTest {
        server.enqueue(MockResponse.Builder().body(fixture("signal.json")).build())
        val s = repo().signal()
        assertEquals(61.2, s.global.score, 1e-9)
        assertTrue(server.takeRequest().target.startsWith("/api/v1/gold/signal.json?t="))
    }

    @Test
    fun fallsBackToCacheWhenOffline() = runTest {
        val repo = repo()
        server.enqueue(MockResponse.Builder().body(fixture("history.json")).build())
        val first = repo.history()
        assertFalse(repo.freshness.fromCache)
        server.enqueue(MockResponse.Builder().code(503).build())
        val second = repo.history()
        assertTrue("served from cache", repo.freshness.fromCache)
        assertEquals(first.points.size, second.points.size)
    }

    @Test
    fun invalidResponseIsNeverCached() = runTest {
        val repo = repo()
        server.enqueue(MockResponse.Builder().body("{\"not\":\"a signal\"}").build())
        val failed = runCatching { repo.signal() }
        assertTrue(failed.isFailure)
        server.enqueue(MockResponse.Builder().code(500).build())
        val offline = runCatching { repo.signal() }
        assertTrue("nothing valid cached -> error, not garbage", offline.exceptionOrNull() is IOException)
    }
}
