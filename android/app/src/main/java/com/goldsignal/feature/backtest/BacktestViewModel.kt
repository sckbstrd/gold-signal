package com.goldsignal.feature.backtest

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.goldsignal.data.GoldRepository
import com.goldsignal.model.BacktestRequest
import com.goldsignal.model.BacktestResponse
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import java.time.LocalDate
import java.time.format.DateTimeParseException

data class BacktestForm(
    val start: String = "2021-10-01",
    val end: String = "2026-09-30",
    val capital: String = "10000",
    val costBps: String = "10",
)

enum class FormError { DATE_FORMAT, DATE_RANGE, CAPITAL, COST }

data class BacktestUiState(
    val form: BacktestForm = BacktestForm(),
    val errors: Set<FormError> = emptySet(),
    val running: Boolean = false,
    val result: BacktestResponse? = null,
    val failure: String? = null,
)

class BacktestViewModel(private val repo: GoldRepository) : ViewModel() {
    private val _state = MutableStateFlow(BacktestUiState())
    val state: StateFlow<BacktestUiState> = _state.asStateFlow()

    fun edit(transform: (BacktestForm) -> BacktestForm) = _state.update { it.copy(form = transform(it.form), errors = emptySet()) }

    fun run() {
        val form = _state.value.form
        val errors = validate(form)
        if (errors.isNotEmpty()) {
            _state.update { it.copy(errors = errors) }
            return
        }
        _state.update { it.copy(running = true, failure = null) }
        viewModelScope.launch {
            try {
                val result = repo.backtest(
                    BacktestRequest(form.start, form.end, form.capital.toDouble(), form.costBps.toDouble()),
                )
                _state.update { it.copy(running = false, result = result) }
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                _state.update { it.copy(running = false, failure = e.message ?: e::class.java.simpleName) }
            }
        }
    }

    companion object {
        fun validate(form: BacktestForm): Set<FormError> {
            val errors = mutableSetOf<FormError>()
            val start = parse(form.start)
            val end = parse(form.end)
            if (start == null || end == null) errors += FormError.DATE_FORMAT
            else if (!end.isAfter(start)) errors += FormError.DATE_RANGE
            val capital = form.capital.toDoubleOrNull()
            if (capital == null || capital <= 0) errors += FormError.CAPITAL
            val cost = form.costBps.toDoubleOrNull()
            if (cost == null || cost < 0 || cost > 500) errors += FormError.COST
            return errors
        }

        private fun parse(s: String): LocalDate? = try {
            LocalDate.parse(s.trim())
        } catch (_: DateTimeParseException) {
            null
        }
    }
}
