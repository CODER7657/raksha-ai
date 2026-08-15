package ai.raksha.app

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
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
import ai.raksha.app.core.Language
import ai.raksha.app.core.RuleLabels
import ai.raksha.app.core.ScanPreferences
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
    ) { granted ->
        val smsGranted = granted[Manifest.permission.RECEIVE_SMS] == true
        ScanPreferences(this).isScanningEnabled = smsGranted
        permissionRefused = !smsGranted
    }

    private var permissionRefused by mutableStateOf(false)

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        handleShare(intent)
        setContent {
            MaterialTheme {
                Surface(modifier = Modifier.fillMaxSize()) {
                    HomeScreen(
                        sharedText = sharedText,
                        permissionRefused = permissionRefused,
                        onEnableScanning = ::enableScanning,
                        onDisableScanning = { ScanPreferences(this).isScanningEnabled = false },
                    )
                }
            }
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
            permissionRefused = false
        } else {
            requestSmsPermission.launch(missing.toTypedArray())
        }
    }
}

@Composable
private fun HomeScreen(
    sharedText: String?,
    permissionRefused: Boolean,
    onEnableScanning: () -> Unit,
    onDisableScanning: () -> Unit,
) {
    val context = LocalContext.current
    val preferences = remember { ScanPreferences(context) }

    var selectedLanguage by remember {
        mutableStateOf(Language.fromCode(preferences.language))
    }
    var scanningEnabled by remember { mutableStateOf(preferences.isScanningEnabled) }

    Scaffold { innerPadding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(innerPadding)
                .padding(24.dp)
                .verticalScroll(rememberScrollState()),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Text("Raksha AI", style = MaterialTheme.typography.headlineMedium)

            // --- Shared message result ---------------------------------------
            if (sharedText != null) {
                Text(
                    stringResource(R.string.shared_heading),
                    style = MaterialTheme.typography.titleMedium,
                )
                val hits = remember(sharedText, selectedLanguage) {
                    offlineRuleHits(sharedText, selectedLanguage.code)
                }
                Card(modifier = Modifier.fillMaxWidth()) {
                    Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                        if (hits.isEmpty()) {
                            Text(stringResource(R.string.shared_clean))
                        } else {
                            Text(
                                stringResource(R.string.shared_flagged),
                                style = MaterialTheme.typography.titleSmall,
                            )
                            // Rule labels, never the pattern that produced them.
                            hits.forEach { hit ->
                                Text(
                                    stringResource(
                                        R.string.warning_reason_bullet,
                                        RuleLabels.labelFor(context, hit.ruleId),
                                    ),
                                )
                            }
                        }
                    }
                }
                HorizontalDivider()
            } else {
                Text(
                    stringResource(R.string.shared_hint),
                    style = MaterialTheme.typography.bodyMedium,
                )
            }

            // --- Scanning toggle ---------------------------------------------
            Text(stringResource(R.string.scanning_heading), style = MaterialTheme.typography.titleMedium)
            Text(
                stringResource(
                    if (scanningEnabled) R.string.scanning_on else R.string.scanning_off
                ),
                style = MaterialTheme.typography.bodyMedium,
            )

            if (scanningEnabled) {
                OutlinedButton(onClick = { onDisableScanning(); scanningEnabled = false }) {
                    Text(stringResource(R.string.scanning_disable))
                }
            } else {
                Text(
                    stringResource(R.string.scanning_permission_needed),
                    style = MaterialTheme.typography.bodySmall,
                )
                Button(onClick = { onEnableScanning(); scanningEnabled = preferences.isScanningEnabled }) {
                    Text(stringResource(R.string.scanning_enable))
                }
            }

            if (permissionRefused) {
                Text(
                    stringResource(R.string.scanning_permission_denied),
                    style = MaterialTheme.typography.bodySmall,
                )
            }

            // Honesty about coverage — #29 §5. Users assume an app like this
            // sees WhatsApp too, and a silent gap is worse than a stated one.
            Text(
                stringResource(R.string.scanning_coverage_note),
                style = MaterialTheme.typography.bodySmall,
            )

            HorizontalDivider()

            // --- Language ----------------------------------------------------
            Text(stringResource(R.string.language_heading), style = MaterialTheme.typography.titleMedium)
            Language.entries.forEach { language ->
                FilterChip(
                    selected = language == selectedLanguage,
                    onClick = {
                        selectedLanguage = language
                        preferences.language = language.code
                    },
                    label = { Text("${language.nativeName}  (${language.englishName})") },
                )
            }

            Card {
                Text(
                    modifier = Modifier.padding(16.dp),
                    text = stringResource(
                        R.string.selected_format,
                        selectedLanguage.englishName,
                        selectedLanguage.code,
                        selectedLanguage.script,
                        selectedLanguage.bcp47,
                    ),
                    style = MaterialTheme.typography.bodySmall,
                )
            }
        }
    }
}
