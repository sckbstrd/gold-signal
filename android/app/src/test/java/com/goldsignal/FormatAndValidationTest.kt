package com.goldsignal

import com.goldsignal.core.format.Fmt
import com.goldsignal.feature.backtest.BacktestForm
import com.goldsignal.feature.backtest.BacktestViewModel
import com.goldsignal.feature.backtest.FormError
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import java.util.Locale

class FormatAndValidationTest {
    private val en = Fmt(Locale.forLanguageTag("en-US"))
    private val tr = Fmt(Locale.forLanguageTag("tr-TR"))
    private val ru = Fmt(Locale.forLanguageTag("ru-RU"))

    private fun String.normSpaces() = replace(' ', ' ').replace(' ', ' ')

    @Test
    fun percentFollowsLocaleConventions() {
        assertEquals("+0.60%", en.pct(0.6))
        assertEquals("+%0,60", tr.pct(0.6))
        assertEquals("+0,60 %", ru.pct(0.6).normSpaces())
        assertEquals("−1.98%", en.pct(-1.98))
    }

    @Test
    fun moneyAndBasisPoints() {
        assertEquals("$4,180.50", en.usd(4180.50))
        assertEquals("₺6.700,15", tr.tryAmount(6700.15))
        assertEquals("6 700,15 ₺", ru.tryAmount(6700.15).normSpaces())
        assertEquals("−28 bp", en.bp(-28.0).normSpaces())
        assertEquals("−28 б.п.", ru.bp(-28.0).normSpaces())
    }

    @Test
    fun zeroHasNoSign() {
        assertEquals("0.00%", en.pct(0.0))
        assertEquals("0.00%", en.pct(-0.001))
    }

    @Test
    fun backtestFormValidation() {
        assertTrue(BacktestViewModel.validate(BacktestForm()).isEmpty())
        assertEquals(setOf(FormError.DATE_FORMAT), BacktestViewModel.validate(BacktestForm(start = "2021/10/01")))
        assertEquals(setOf(FormError.DATE_RANGE), BacktestViewModel.validate(BacktestForm(start = "2026-01-01", end = "2025-01-01")))
        assertEquals(setOf(FormError.CAPITAL), BacktestViewModel.validate(BacktestForm(capital = "-5")))
        assertEquals(setOf(FormError.COST), BacktestViewModel.validate(BacktestForm(costBps = "abc")))
    }
}
