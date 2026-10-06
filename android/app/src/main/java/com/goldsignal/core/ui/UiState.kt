package com.goldsignal.core.ui

import androidx.compose.runtime.Composable
import androidx.compose.ui.platform.LocalContext
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.compose.viewModel
import com.goldsignal.AppContainer
import com.goldsignal.GoldSignalApp
import com.goldsignal.data.GoldRepository
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

sealed interface UiState<out T> {
    data object Loading : UiState<Nothing>
    data class Ready<T>(val data: T) : UiState<T>
    data class Failed(val message: String) : UiState<Nothing>
}

/** One read-only screen = one loader. Used by every screen except the backtest form. */
class LoadViewModel<T>(private val loader: suspend () -> T) : ViewModel() {
    private val _state = MutableStateFlow<UiState<T>>(UiState.Loading)
    val state: StateFlow<UiState<T>> = _state.asStateFlow()

    init {
        refresh()
    }

    /** Millis of the last successful load (0 = never). */
    var loadedAt: Long = 0L
        private set

    /** silent = keep showing the current data while reloading (used for auto-refresh). */
    fun refresh(silent: Boolean = false) {
        if (!silent || _state.value !is UiState.Ready) _state.value = UiState.Loading
        viewModelScope.launch {
            try {
                _state.value = UiState.Ready(loader())
                loadedAt = System.currentTimeMillis()
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                // A failed silent refresh keeps the data on screen; a visible one shows the error.
                if (!silent || _state.value !is UiState.Ready) {
                    _state.value = UiState.Failed(e.message ?: e::class.java.simpleName)
                }
            }
        }
    }
}

@Composable
fun container(): AppContainer = (LocalContext.current.applicationContext as GoldSignalApp).container

@Composable
fun repository(): GoldRepository = container().repository

/** ViewModels are scoped to the active data source, so switching Live/Demo reloads everything. */
@Composable
fun <T> loadViewModel(key: String, loader: suspend GoldRepository.() -> T): LoadViewModel<T> {
    val c = container()
    val repo = c.repository
    return viewModel(key = "$key|${c.repositoryKey}") { LoadViewModel { repo.loader() } }
}
