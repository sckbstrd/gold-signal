package com.goldsignal.ui

import androidx.annotation.DrawableRes
import androidx.annotation.StringRes
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Icon
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.res.stringResource
import androidx.navigation.NavGraph.Companion.findStartDestination
import androidx.navigation.NavHostController
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import androidx.navigation.navArgument
import com.goldsignal.R
import com.goldsignal.feature.backtest.BacktestScreen
import com.goldsignal.feature.dashboard.DashboardScreen
import com.goldsignal.feature.events.EventsScreen
import com.goldsignal.feature.history.HistoryScreen
import com.goldsignal.feature.indicator.IndicatorScreen
import com.goldsignal.feature.settings.SettingsScreen
import com.goldsignal.feature.why.WhyScreen

object Routes {
    const val SIGNAL = "signal"
    const val EVENTS = "events"
    const val BACKTEST = "backtest"
    const val SETTINGS = "settings"
    const val INDICATOR = "indicator/{code}"
    const val WHY = "why?tab={tab}"
    const val HISTORY = "history"

    fun indicator(code: String) = "indicator/$code"
    fun why(tab: Int = 0) = "why?tab=$tab"
}

private data class Tab(val route: String, @StringRes val label: Int, @DrawableRes val icon: Int)

private val tabs = listOf(
    Tab(Routes.SIGNAL, R.string.nav_signal, R.drawable.ic_signal),
    Tab(Routes.EVENTS, R.string.nav_events, R.drawable.ic_event),
    Tab(Routes.BACKTEST, R.string.nav_backtest, R.drawable.ic_backtest),
    Tab(Routes.SETTINGS, R.string.nav_settings, R.drawable.ic_settings),
)

@Composable
fun GoldSignalNavHost(nav: NavHostController = rememberNavController()) {
    val backStack by nav.currentBackStackEntryAsState()
    val route = backStack?.destination?.route
    Scaffold(
        // Inner screens draw their own top bars, so only the bottom inset is handled here.
        contentWindowInsets = WindowInsets(0, 0, 0, 0),
        bottomBar = {
            NavigationBar {
                tabs.forEach { tab ->
                    val selected = route == tab.route ||
                        (tab.route == Routes.SIGNAL && (route == Routes.INDICATOR || route == Routes.WHY || route == Routes.HISTORY))
                    NavigationBarItem(
                        selected = selected,
                        onClick = {
                            nav.navigate(tab.route) {
                                popUpTo(nav.graph.findStartDestination().id) { saveState = true }
                                launchSingleTop = true
                                restoreState = true
                            }
                        },
                        icon = { Icon(painterResource(tab.icon), contentDescription = null) },
                        label = { Text(stringResource(tab.label)) },
                    )
                }
            }
        },
    ) { padding ->
        Box(Modifier.fillMaxSize().padding(padding)) {
            NavHost(nav, startDestination = Routes.SIGNAL) {
                composable(Routes.SIGNAL) {
                    DashboardScreen(
                        onIndicator = { nav.navigate(Routes.indicator(it)) },
                        onWhy = { tab -> nav.navigate(Routes.why(tab)) },
                        onHistory = { nav.navigate(Routes.HISTORY) },
                    )
                }
                composable(Routes.HISTORY) { HistoryScreen(onBack = { nav.popBackStack() }) }
                composable(Routes.EVENTS) { EventsScreen() }
                composable(Routes.BACKTEST) { BacktestScreen() }
                composable(Routes.SETTINGS) { SettingsScreen() }
                composable(Routes.INDICATOR, arguments = listOf(navArgument("code") { type = NavType.StringType })) {
                    IndicatorScreen(code = it.arguments?.getString("code").orEmpty(), onBack = { nav.popBackStack() })
                }
                composable(
                    Routes.WHY,
                    arguments = listOf(navArgument("tab") { type = NavType.IntType; defaultValue = 0 }),
                ) {
                    WhyScreen(initialTab = it.arguments?.getInt("tab") ?: 0, onBack = { nav.popBackStack() })
                }
            }
        }
    }
}
