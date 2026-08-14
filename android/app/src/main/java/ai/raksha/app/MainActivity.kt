package ai.raksha.app

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Card
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import ai.raksha.app.core.Language

/**
 * Phase 1 shell.
 *
 * This screen exists to prove the module builds, runs, and can read the shared
 * language list — nothing more. It requests no permissions and reaches no
 * network. The SMS listener and on-device scoring arrive in Phase 2, once the
 * rule engine has been ported to Kotlin (see docs/SMS-AUTOSCAN-PLAN.md).
 */
class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            MaterialTheme {
                Surface(modifier = Modifier.fillMaxSize()) {
                    ShellScreen()
                }
            }
        }
    }
}

@Composable
private fun ShellScreen() {
    var selected by remember { mutableStateOf(Language.DEFAULT) }

    Scaffold { innerPadding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(innerPadding)
                .padding(24.dp)
                .verticalScroll(rememberScrollState()),
            verticalArrangement = Arrangement.spacedBy(16.dp),
        ) {
            Text(
                text = "Raksha AI",
                style = MaterialTheme.typography.headlineMedium,
            )
            Text(
                text = "Phase 1 shell — SMS scanning is not enabled in this build.",
                style = MaterialTheme.typography.bodyMedium,
            )

            Text(
                text = "Language",
                style = MaterialTheme.typography.titleMedium,
            )

            // Rendered from the shared enum rather than a hardcoded list, so a
            // language added on the backend shows up here the moment
            // Language.kt is updated to match.
            Language.entries.forEach { language ->
                FilterChip(
                    selected = language == selected,
                    onClick = { selected = language },
                    label = { Text("${language.nativeName}  (${language.englishName})") },
                )
            }

            Card {
                Text(
                    modifier = Modifier.padding(16.dp),
                    text = "Selected: ${selected.englishName} · ${selected.code} · " +
                        "${selected.script} script · ${selected.bcp47}",
                    style = MaterialTheme.typography.bodySmall,
                )
            }
        }
    }
}
