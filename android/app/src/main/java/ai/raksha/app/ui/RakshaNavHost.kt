package ai.raksha.app.ui

import androidx.compose.foundation.layout.padding
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.automirrored.filled.List
import androidx.compose.material.icons.filled.Lock
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.navigation.NavGraph.Companion.findStartDestination
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import androidx.navigation.navArgument
import ai.raksha.app.R
import ai.raksha.app.ui.detail.TraceDetailScreen
import ai.raksha.app.ui.detail.TraceDetailViewModel
import ai.raksha.app.ui.history.HistoryScreen
import ai.raksha.app.ui.settings.SettingsScreen
import androidx.lifecycle.viewmodel.compose.viewModel

/**
 * The app's routes.
 *
 * Three tabs and one detail screen. Small enough that a sealed hierarchy would
 * be ceremony, so the routes are constants with one builder for the only one
 * that takes an argument.
 */
object Routes {
    const val HOME = "home"
    const val HISTORY = "history"
    const val SETTINGS = "settings"

    const val TRACE = "trace/{scanId}"
    fun trace(scanId: Long) = "trace/$scanId"

    const val ARG_SCAN_ID = "scanId"
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun RakshaNavHost(
    homeScreen: @Composable () -> Unit,
) {
    val navController = rememberNavController()
    val backStackEntry by navController.currentBackStackEntryAsState()
    val route = backStackEntry?.destination?.route

    val onTrace = route?.startsWith("trace/") == true

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Text(
                        stringResource(
                            when {
                                onTrace -> R.string.title_trace
                                route == Routes.HISTORY -> R.string.title_history
                                route == Routes.SETTINGS -> R.string.title_settings
                                else -> R.string.app_name
                            },
                        ),
                    )
                },
                navigationIcon = {
                    // Only the detail screen is a push; the tabs are peers and a
                    // back arrow on them would be a lie about the stack.
                    if (onTrace) {
                        IconButton(
                            onClick = { navController.popBackStack() },
                        ) {
                            // Auto-mirrored: in Urdu the whole layout flips, and
                            // a back arrow still pointing left would point at
                            // where "forward" now is.
                            Icon(
                                imageVector = Icons.AutoMirrored.Filled.ArrowBack,
                                contentDescription = stringResource(R.string.action_back),
                            )
                        }
                    }
                },
            )
        },
        bottomBar = {
            // Hidden on the detail screen: it is a push, not a tab, and leaving
            // the bar visible invites a tap that silently abandons what the user
            // was reading.
            if (!onTrace) {
                NavigationBar {
                    listOf(
                        // Material icons rather than android.R.drawable.*: the
                        // platform ones are StateListDrawables, and Compose's
                        // painterResource only loads vectors and rasters — it
                        // throws at render, not at build.
                        Triple(Routes.HOME, R.string.tab_protection, Icons.Filled.Lock),
                        Triple(Routes.HISTORY, R.string.tab_history, Icons.AutoMirrored.Filled.List),
                        Triple(Routes.SETTINGS, R.string.tab_settings, Icons.Filled.Settings),
                    ).forEach { (destination, label, icon) ->
                        val selected = route == destination
                        NavigationBarItem(
                            selected = selected,
                            onClick = {
                                navController.navigate(destination) {
                                    // Tabs, not a growing stack: returning to a
                                    // tab should not require pressing back once
                                    // per visit.
                                    popUpTo(navController.graph.findStartDestination().id) {
                                        saveState = true
                                    }
                                    launchSingleTop = true
                                    restoreState = true
                                }
                            },
                            icon = {
                                Icon(
                                    imageVector = icon,
                                    // Null: the label below is already read, and
                                    // announcing both says everything twice.
                                    contentDescription = null,
                                )
                            },
                            label = { Text(stringResource(label)) },
                        )
                    }
                }
            }
        },
    ) { innerPadding ->
        NavHost(
            navController = navController,
            startDestination = Routes.HOME,
            modifier = Modifier.padding(innerPadding),
        ) {
            composable(Routes.HOME) { homeScreen() }

            composable(Routes.HISTORY) {
                HistoryScreen(onOpenTrace = { navController.navigate(Routes.trace(it)) })
            }

            composable(Routes.SETTINGS) { SettingsScreen() }

            composable(
                Routes.TRACE,
                arguments = listOf(navArgument(Routes.ARG_SCAN_ID) { type = NavType.LongType }),
            ) { entry ->
                val scanId = entry.arguments?.getLong(Routes.ARG_SCAN_ID) ?: return@composable
                TraceDetailScreen(
                    scanId = scanId,
                    viewModel = viewModel<TraceDetailViewModel>(),
                )
            }
        }
    }
}
