package ai.raksha.app.ui.home

import ai.raksha.app.R
import ai.raksha.app.core.Language
import ai.raksha.app.core.ProtectionState
import ai.raksha.app.core.RuleLabels
import ai.raksha.app.core.ScanPreferences
import ai.raksha.app.ui.RakshaTheme
import ai.raksha.rules.offlineRuleHits
import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.text.format.DateUtils
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

@Composable
fun HomeScreen(
    sharedText: String?,
    protection: ProtectionState,
    interruptedAt: Long?,
    onEnableScanning: () -> Unit,
    onDisableScanning: () -> Unit,
    onOpenNotificationSettings: () -> Unit,
    onAcknowledgeInterruption: () -> Unit,
) {
    val context = LocalContext.current
    val preferences = remember { ScanPreferences(context) }

    var selectedLanguage by remember {
        mutableStateOf(Language.fromCode(preferences.language))
    }

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

            // --- Scanning state ----------------------------------------------
            Text(stringResource(R.string.scanning_heading), style = MaterialTheme.typography.titleMedium)

            // Shown above the status line on purpose: it qualifies whatever the
            // status says. Android stopped the app at some point, so there is a
            // window in which nothing was checked and the app cannot say which
            // messages fell in it (#91 §2).
            if (interruptedAt != null) {
                Card(
                    modifier = Modifier.fillMaxWidth(),
                    colors = CardDefaults.cardColors(
                        containerColor = MaterialTheme.colorScheme.secondaryContainer,
                        contentColor = MaterialTheme.colorScheme.onSecondaryContainer,
                    ),
                ) {
                    Column(
                        Modifier.padding(16.dp),
                        verticalArrangement = Arrangement.spacedBy(8.dp),
                    ) {
                        Text(
                            stringResource(R.string.interrupted_title),
                            style = MaterialTheme.typography.titleSmall,
                        )
                        Text(
                            stringResource(R.string.interrupted_body),
                            style = MaterialTheme.typography.bodySmall,
                        )
                        // Rendered by the platform, so it is localised and
                        // phrased the way the rest of the system phrases times,
                        // without another string to translate.
                        Text(
                            DateUtils.getRelativeTimeSpanString(
                                interruptedAt,
                                System.currentTimeMillis(),
                                DateUtils.MINUTE_IN_MILLIS,
                            ).toString(),
                            style = MaterialTheme.typography.bodySmall,
                        )
                        OutlinedButton(onClick = onAcknowledgeInterruption) {
                            Text(stringResource(R.string.interrupted_dismiss))
                        }
                    }
                }
            }

            val scanning = protection != ProtectionState.OFF
            Text(
                stringResource(if (scanning) R.string.scanning_on else R.string.scanning_off),
                style = MaterialTheme.typography.bodyMedium,
            )

            when (protection) {
                ProtectionState.PROTECTED -> {
                    Text(
                        stringResource(R.string.protected_status),
                        style = MaterialTheme.typography.bodySmall,
                    )
                }

                // The state #49 exists for. Given its own card, error colours and
                // an action, because it is not a status line — it is a fault the
                // user has to fix, and it looks identical to "working fine" from
                // anywhere else in the app.
                ProtectionState.SCANNING_WITHOUT_WARNINGS -> {
                    Card(
                        modifier = Modifier.fillMaxWidth(),
                        colors = CardDefaults.cardColors(
                            containerColor = MaterialTheme.colorScheme.errorContainer,
                            contentColor = MaterialTheme.colorScheme.onErrorContainer,
                        ),
                    ) {
                        Column(
                            Modifier.padding(16.dp),
                            verticalArrangement = Arrangement.spacedBy(8.dp),
                        ) {
                            Text(
                                stringResource(R.string.warnings_blocked_title),
                                style = MaterialTheme.typography.titleSmall,
                            )
                            Text(
                                stringResource(R.string.warnings_blocked_body),
                                style = MaterialTheme.typography.bodySmall,
                            )
                            Button(onClick = onOpenNotificationSettings) {
                                Text(stringResource(R.string.warnings_blocked_action))
                            }
                        }
                    }
                }

                ProtectionState.NO_SMS_PERMISSION -> {
                    Text(
                        stringResource(R.string.scanning_permission_denied),
                        style = MaterialTheme.typography.bodySmall,
                    )
                }

                ProtectionState.OFF -> {
                    Text(
                        stringResource(R.string.scanning_permission_needed),
                        style = MaterialTheme.typography.bodySmall,
                    )
                }
            }

            if (scanning) {
                OutlinedButton(onClick = onDisableScanning) {
                    Text(stringResource(R.string.scanning_disable))
                }
            } else {
                Button(onClick = onEnableScanning) {
                    Text(stringResource(R.string.scanning_enable))
                }
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
