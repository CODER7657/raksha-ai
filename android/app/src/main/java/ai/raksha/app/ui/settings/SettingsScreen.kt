package ai.raksha.app.ui.settings

import android.app.Application
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
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.stateDescription
import androidx.compose.ui.unit.dp
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.compose.viewModel
import ai.raksha.app.R
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
            val count = withContext(Dispatchers.IO) { ServiceLocator.scanStore(context).count() }
            _state.value = SettingsUiState(historyEnabled = enabled, storedCount = count)
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
                withContext(Dispatchers.IO) { ServiceLocator.scanStore(context).clear() }
            }
            refresh()
        }
    }

    fun clearHistory() {
        viewModelScope.launch {
            withContext(Dispatchers.IO) { ServiceLocator.scanStore(getApplication()).clear() }
            refresh()
        }
    }
}

@Composable
fun SettingsScreen(viewModel: SettingsViewModel = viewModel()) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    var confirmClear by remember { mutableStateOf(false) }

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
