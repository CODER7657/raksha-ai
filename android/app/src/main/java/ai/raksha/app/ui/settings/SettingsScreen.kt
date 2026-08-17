package ai.raksha.app.ui.settings

import android.app.Application
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.stateDescription
import androidx.compose.ui.unit.dp
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.compose.LifecycleResumeEffect
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.compose.viewModel
import ai.raksha.app.R
import ai.raksha.app.call.CallScreeningRole
import ai.raksha.app.core.ServiceLocator
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

data class SettingsUiState(
    val historyEnabled: Boolean = true,
    val storedCount: Int = 0,
    /** False on Android below 30, or on a device with no screening role. */
    val callScreeningSupported: Boolean = false,
    /** Re-read every resume: the role can be taken away in system settings. */
    val callScreeningHeld: Boolean = false,
    /** How many numbers layer 1 knows. Zero is the normal state on a new install. */
    val knownNumberCount: Int = 0,
)

class SettingsViewModel(application: Application) : AndroidViewModel(application) {

    private val _state = MutableStateFlow(SettingsUiState())
    val state: StateFlow<SettingsUiState> = _state.asStateFlow()

    init {
        refresh()
    }

    fun refresh() {
        viewModelScope.launch {
            val context = getApplication<Application>()
            val enabled = ServiceLocator.preferences(context).isHistoryEnabled
            // The role is asked about on every refresh rather than remembered.
            // It can be handed to another app from system settings without this
            // app hearing anything, which is the same silent revocation #93
            // found for force-stop — where the UI went on claiming protection
            // that had already stopped.
            val held = CallScreeningRole.isHeld(context)
            val supported = CallScreeningRole.isAvailable(context)

            val reputation = ServiceLocator.callReputation(context)
            val count = withContext(Dispatchers.IO) {
                reputation.refresh()
                ServiceLocator.scanStore(context).count()
            }
            _state.value = SettingsUiState(
                historyEnabled = enabled,
                storedCount = count,
                callScreeningSupported = supported,
                callScreeningHeld = held,
                knownNumberCount = reputation.size,
            )
        }
    }

    /**
     * Turning history off also deletes what is already stored.
     *
     * A switch that stops new records while leaving the old ones is a setting
     * that lies: the user reads "off" and believes their messages are not on
     * the phone. #29 §2 asks for one-tap clearing, and this is the tap most
     * people will actually find.
     */
    fun setHistoryEnabled(enabled: Boolean) {
        viewModelScope.launch {
            val context = getApplication<Application>()
            ServiceLocator.preferences(context).isHistoryEnabled = enabled
            if (!enabled) {
                withContext(Dispatchers.IO) { clearEverything(context) }
            }
            refresh()
        }
    }

    fun clearHistory() {
        viewModelScope.launch {
            withContext(Dispatchers.IO) { clearEverything(getApplication()) }
            refresh()
        }
    }

    /**
     * Empties the store **and** the reputation set built from it.
     *
     * Clearing the store alone is not enough and the gap is invisible from the
     * UI: [ai.raksha.app.call.CallReputation] holds its answers in memory so a
     * ringing phone never waits on disk, so a cleared store leaves a live copy
     * of the user's numbers behind until the process dies. The user would have
     * pressed delete, been told everything was gone, and still been warned about
     * a caller on the strength of a message that no longer exists — a shadow
     * list, which is exactly what makes an off switch a lie.
     */
    private fun clearEverything(context: Application) {
        ServiceLocator.scanStore(context).clear()
        ServiceLocator.callReputation(context).refresh()
    }
}

@Composable
fun SettingsScreen(viewModel: SettingsViewModel = viewModel()) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    var confirmClear by remember { mutableStateOf(false) }

    // Granting the role happens in a system screen, and taking it away happens
    // in a different one the app never sees. Re-reading on resume is what stops
    // this screen reporting a role the user revoked ten seconds ago — the same
    // reason MainActivity re-reads notification permission on every resume.
    LifecycleResumeEffect(Unit) {
        viewModel.refresh()
        onPauseOrDispose { }
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(24.dp)
            .verticalScroll(rememberScrollState()),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Text(stringResource(R.string.settings_history_heading), style = MaterialTheme.typography.titleMedium)
        Text(
            stringResource(R.string.settings_history_explainer),
            style = MaterialTheme.typography.bodySmall,
        )

        Switch(
            checked = state.historyEnabled,
            onCheckedChange = viewModel::setHistoryEnabled,
            modifier = Modifier
                .heightIn(min = 48.dp)
                .semantics {
                    // Without this TalkBack says "on"/"off" with no subject.
                    stateDescription = ""
                },
        )
        Text(
            stringResource(
                if (state.historyEnabled) R.string.settings_history_on else R.string.settings_history_off,
            ),
            style = MaterialTheme.typography.bodyMedium,
        )

        HorizontalDivider()

        Text(
            stringResource(R.string.settings_stored_count, state.storedCount),
            style = MaterialTheme.typography.bodyMedium,
        )

        OutlinedButton(
            onClick = { confirmClear = true },
            enabled = state.storedCount > 0,
            modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp),
        ) {
            Text(stringResource(R.string.settings_clear_history))
        }

        Text(
            stringResource(R.string.settings_storage_note),
            style = MaterialTheme.typography.bodySmall,
        )

        HorizontalDivider()

        CallScreeningSection(state = state, onGranted = viewModel::refresh)
    }

    // Deleting a user's own record of why they were warned is not undoable, so
    // it asks first.
    if (confirmClear) {
        AlertDialog(
            onDismissRequest = { confirmClear = false },
            title = { Text(stringResource(R.string.settings_clear_confirm_title)) },
            text = { Text(stringResource(R.string.settings_clear_confirm_body)) },
            confirmButton = {
                Button(onClick = { viewModel.clearHistory(); confirmClear = false }) {
                    Text(stringResource(R.string.settings_clear_confirm_action))
                }
            },
            dismissButton = {
                TextButton(onClick = { confirmClear = false }) {
                    Text(stringResource(R.string.settings_clear_cancel))
                }
            },
        )
    }
}

/**
 * Layer 3's switch, and the only place the app says anything about calls.
 *
 * **Deliberately not on the protection screen.** `protected_status` there says
 * "Messages are checked and warnings can reach you", which stays true whatever
 * the call role is doing — so leaving calls out of it means the home screen
 * cannot overclaim about a layer that may have been switched off behind the
 * app's back. #93 built that honesty by adding a state; here it is kept by not
 * making the claim in the first place.
 *
 * Three things a user is told plainly, because each is a way this feature does
 * less than its name suggests:
 *
 *  - **The Android version cannot do it.** Below API 30 there is no honest
 *    version of this feature (see `CallScreeningRole`), so there is no switch —
 *    a control that does nothing is worse than an explanation.
 *  - **The role is not held.** Including after the user granted it once and the
 *    system handed it elsewhere.
 *  - **Nothing is known yet.** The set is empty on a new install and fills only
 *    when a number sends a message that gets flagged. A user who turns this on
 *    and is told nothing else would reasonably believe they are covered against
 *    a first call from a stranger, and they are not.
 */
@Composable
private fun CallScreeningSection(state: SettingsUiState, onGranted: () -> Unit) {
    val context = LocalContext.current

    // The system's own grant dialog. Its result code is ignored on purpose:
    // "granted" from the dialog and "holds the role now" are different claims,
    // and only the second one matters — so the state is re-read either way.
    val requestRole = rememberLauncherForActivityResult(
        ActivityResultContracts.StartActivityForResult(),
    ) { onGranted() }

    Text(
        stringResource(R.string.call_screening_heading),
        style = MaterialTheme.typography.titleMedium,
    )
    Text(
        stringResource(R.string.call_screening_explainer),
        style = MaterialTheme.typography.bodySmall,
    )

    if (!state.callScreeningSupported) {
        Text(
            stringResource(R.string.call_screening_unsupported),
            style = MaterialTheme.typography.bodyMedium,
        )
        return
    }

    Text(
        stringResource(
            if (state.callScreeningHeld) R.string.call_screening_on else R.string.call_screening_off,
        ),
        style = MaterialTheme.typography.bodyMedium,
    )

    if (!state.callScreeningHeld) {
        Button(
            onClick = { CallScreeningRole.requestIntent(context)?.let(requestRole::launch) },
            modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp),
        ) {
            Text(stringResource(R.string.call_screening_enable))
        }
        return
    }

    // Unconditional, and that is the whole point.
    //
    // This was `if (state.knownNumberCount == 0)`, which made an empty-state
    // message do the job of a permanent limitation notice: the caveat was shown
    // to the person with no protection yet and hidden from the person with some
    // — disappearing exactly when the user starts to trust the feature.
    //
    // The limit is true at zero known numbers and true at fifty, so it is stated
    // at zero and at fifty. #116 §6 also requires that nothing here implies the
    // app hears the call, which is why the sentence says so outright rather than
    // leaving it to be inferred from what is absent.
    Text(
        stringResource(R.string.call_screening_limitation),
        style = MaterialTheme.typography.bodySmall,
    )
}
