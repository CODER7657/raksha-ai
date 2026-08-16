package ai.raksha.app

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.net.Uri
import android.os.Bundle
import android.provider.Settings
import android.text.format.DateUtils
import android.view.View
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.FilterChip
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import ai.raksha.app.core.InterruptionMonitor
import ai.raksha.app.core.Language
import ai.raksha.app.core.ProtectionState
import ai.raksha.app.core.RuleLabels
import ai.raksha.app.core.ScanPreferences
import ai.raksha.app.ui.RakshaNavHost
import ai.raksha.app.ui.RakshaTheme
import ai.raksha.app.ui.home.HomeScreen
import ai.raksha.rules.offlineRuleHits

/**
 * The app's one screen: turn checking on, pick a language, and — when a message
 * is shared in from a messaging app — show what the engine made of it.
 *
 * Nothing here reaches the network. Scoring is [offlineRuleHits] from
 * `:core:rules`, running in-process.
 */
class MainActivity : ComponentActivity() {

    /** Text shared in via ACTION_SEND, scored on arrival. */
    private var sharedText by mutableStateOf<String?>(null)

    private val requestSmsPermission = registerForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions()
    ) {
        // The result map is deliberately ignored. It contains only the
        // permissions that were *asked for*, so a permission the user already
        // granted is absent — and reading `granted[RECEIVE_SMS] == true` off it
        // returned false whenever SMS was already held and only notifications
        // were missing. The effect was that denying notifications silently
        // switched scanning off, which is a worse version of the bug #49 exists
        // to fix: the user refuses one thing and loses another, with no message
        // saying so.
        //
        // Asking the system what is actually granted has no such edge.
        ScanPreferences(this).isScanningEnabled = ProtectionState.hasSmsPermission(this)
        refreshState()
    }

    private var protection by mutableStateOf(ProtectionState.OFF)

    /** When Android last force-stopped us, if the user has not dismissed it. */
    private var interruptedAt by mutableStateOf<Long?>(null)

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        blockObscuredTouches()
        handleShare(intent)
        refreshState()
        setContent {
            RakshaTheme {
                Surface(modifier = Modifier.fillMaxSize()) {
                    // The activity keeps ownership of the things only it can do
                    // — permission requests, the settings intent, reading the
                    // exit-reason history — and hands the protection screen down
                    // as a slot. Everything else is a ViewModel behind a route.
                    RakshaNavHost(
                        homeScreen = {
                            HomeScreen(
                                sharedText = sharedText,
                                protection = protection,
                                interruptedAt = interruptedAt,
                                onEnableScanning = ::enableScanning,
                                onDisableScanning = {
                                    ScanPreferences(this).isScanningEnabled = false
                                    refreshState()
                                },
                                onOpenNotificationSettings = ::openNotificationSettings,
                                onAcknowledgeInterruption = ::acknowledgeInterruption,
                            )
                        },
                    )
                }
            }
        }
    }

    /**
     * Notifications can be switched off in Settings while the app is in the
     * background, so the state is re-read on every resume rather than only after
     * a permission dialog. Without this the user turns warnings off, comes back,
     * and the app still claims to be protecting them.
     */
    override fun onResume() {
        super.onResume()
        refreshState()
    }

    private fun refreshState() {
        protection = ProtectionState.of(this)
        val preferences = ScanPreferences(this)
        interruptedAt = if (InterruptionMonitor.hasUnacknowledgedInterruption(this, preferences)) {
            InterruptionMonitor.lastForceStopMillis(this)
        } else {
            null
        }
    }

    private fun acknowledgeInterruption() {
        val preferences = ScanPreferences(this)
        // Stamp with the interruption's own time, not now: a second
        // force-stop after this one must still be reported.
        preferences.acknowledgedInterruptionMillis =
            InterruptionMonitor.lastForceStopMillis(this) ?: System.currentTimeMillis()
        refreshState()
    }

    /**
     * Discards touches that arrive while another app's window is drawn over
     * ours (#82 §5).
     *
     * Tapjacking matters more here than in most apps. An overlay is a live
     * technique in the very scams this app detects: the attacker draws a
     * transparent window, the user believes they are tapping one thing and
     * taps another. Every control on this screen is consequential — turning
     * protection off, opening notification settings — and a warning the user
     * cannot safely tap is worse than no warning, because they believe they
     * acted.
     *
     * Set on the content root rather than per-control: `ViewGroup.dispatchTouchEvent`
     * runs the security filter before dispatching to children, so one call
     * covers the whole Compose tree and cannot be forgotten on a control added
     * later. Available since API 9, so no version guard is needed at minSdk 24.
     *
     * The stronger option is `Window.setHideOverlayWindows(true)` on API 31+,
     * which hides the overlay instead of merely ignoring its touches. It is not
     * used here because it requires declaring `HIDE_OVERLAY_WINDOWS`, and the
     * permission declaration submitted in #39 states the app holds exactly two
     * permissions. Worth revisiting once that review clears — the trade is a
     * third (normal, promptless) permission for a materially better defence.
     */
    private fun blockObscuredTouches() {
        findViewById<View>(android.R.id.content).filterTouchesWhenObscured = true
    }

    private fun openNotificationSettings() {
        // Deep-links to this app's notification settings, which is the only
        // place the user can undo this. Falling back to app details keeps the
        // button honest on OEM builds that do not handle the specific action.
        val intent = Intent(Settings.ACTION_APP_NOTIFICATION_SETTINGS)
            .putExtra(Settings.EXTRA_APP_PACKAGE, packageName)
        if (intent.resolveActivity(packageManager) != null) {
            startActivity(intent)
        } else {
            startActivity(
                Intent(
                    Settings.ACTION_APPLICATION_DETAILS_SETTINGS,
                    Uri.fromParts("package", packageName, null),
                )
            )
        }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        handleShare(intent)
    }

    private fun handleShare(intent: Intent?) {
        if (intent?.action != Intent.ACTION_SEND) return
        if (intent.type != "text/plain") return
        sharedText = intent.getStringExtra(Intent.EXTRA_TEXT)
    }

    /**
     * Asks only when the user opts in. The permission dialog is the moment a
     * user decides whether to trust the app, and asking at launch — before
     * anything has been explained — is how that trust is lost.
     */
    private fun enableScanning() {
        val needed = buildList {
            add(Manifest.permission.RECEIVE_SMS)
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
                add(Manifest.permission.POST_NOTIFICATIONS)
            }
        }
        val missing = needed.filter {
            ContextCompat.checkSelfPermission(this, it) != PackageManager.PERMISSION_GRANTED
        }
        if (missing.isEmpty()) {
            ScanPreferences(this).isScanningEnabled = true
            refreshState()
        } else {
            requestSmsPermission.launch(missing.toTypedArray())
        }
    }
}
