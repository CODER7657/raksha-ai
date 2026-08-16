package ai.raksha.app.ui.history

import android.app.Application
import android.text.format.DateUtils
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.clearAndSetSemantics
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.unit.dp
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.compose.viewModel
import ai.raksha.app.R
import ai.raksha.app.core.RuleLabels
import ai.raksha.app.core.ServiceLocator
import ai.raksha.app.data.ScanRecord
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

/** Immutable state, so a recomposition cannot see a half-updated screen. */
data class HistoryUiState(
    val loading: Boolean = true,
    val records: List<ScanRecord> = emptyList(),
    val historyEnabled: Boolean = true,
)

class HistoryViewModel(application: Application) : AndroidViewModel(application) {

    private val _state = MutableStateFlow(HistoryUiState())
    val state: StateFlow<HistoryUiState> = _state.asStateFlow()

    init {
        refresh()
    }

    /**
     * Re-read on every entry to the screen rather than observing the store.
     *
     * The only writer is the SMS receiver, in a different process component, and
     * a scan arriving while the user reads this list is not worth a live query
     * — they came to look at what already happened. When that stops being true
     * the store gains a Flow and this becomes a `collect`.
     */
    fun refresh() {
        viewModelScope.launch {
            val context = getApplication<Application>()
            val enabled = ServiceLocator.preferences(context).isHistoryEnabled
            val records = withContext(Dispatchers.IO) {
                if (enabled) ServiceLocator.scanStore(context).recent() else emptyList()
            }
            _state.value = HistoryUiState(loading = false, records = records, historyEnabled = enabled)
        }
    }
}

@Composable
fun HistoryScreen(
    onOpenTrace: (Long) -> Unit,
    viewModel: HistoryViewModel = viewModel(),
) {
    val state by viewModel.state.collectAsStateWithLifecycle()

    when {
        state.loading -> Unit

        !state.historyEnabled -> EmptyMessage(stringResource(R.string.history_disabled))

        state.records.isEmpty() -> EmptyMessage(stringResource(R.string.history_empty))

        else -> LazyColumn(
            modifier = Modifier.fillMaxSize().padding(horizontal = 24.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
            contentPadding = androidx.compose.foundation.layout.PaddingValues(vertical = 16.dp),
        ) {
            items(state.records, key = { it.id }) { record ->
                HistoryRow(record, onClick = { onOpenTrace(record.id) })
            }
        }
    }
}

@Composable
private fun EmptyMessage(text: String) {
    Column(Modifier.fillMaxSize().padding(24.dp)) {
        Text(text, style = MaterialTheme.typography.bodyMedium)
    }
}

@Composable
private fun HistoryRow(record: ScanRecord, onClick: () -> Unit) {
    val context = LocalContext.current

    val reasons = record.hits.map { RuleLabels.labelFor(context, it.ruleId) }
    val when_ = DateUtils.getRelativeTimeSpanString(
        record.scannedAtMillis, System.currentTimeMillis(), DateUtils.MINUTE_IN_MILLIS,
    ).toString()
    val sender = record.sender.ifBlank { stringResource(R.string.warning_summary_no_sender) }
    val status = if (record.isFlagged) {
        stringResource(R.string.history_flagged)
    } else {
        stringResource(R.string.history_clean)
    }

    // One announcement per row instead of five fragments. TalkBack reading
    // "From, +91…, 2 hours ago, Looks like a scam, Asks you to share an OTP" as
    // separate nodes makes a list of twenty scans unusable, and this list is for
    // people who are more likely than most to be using a screen reader.
    val spoken = buildString {
        append(status); append(". ")
        append(sender); append(". ")
        append(when_)
        if (reasons.isNotEmpty()) { append(". "); append(reasons.joinToString(". ")) }
    }

    Card(
        modifier = Modifier
            .fillMaxWidth()
            // 48dp is the documented minimum touch target, and the people this
            // is built for have unsteady hands; the rows are taller than that
            // anyway, but the floor is stated rather than assumed from padding.
            .heightIn(min = 48.dp)
            .clickable(onClickLabel = stringResource(R.string.history_open_trace), onClick = onClick)
            .clearAndSetSemantics { contentDescription = spoken },
        colors = CardDefaults.cardColors(
            containerColor = if (record.isFlagged) {
                MaterialTheme.colorScheme.errorContainer
            } else {
                MaterialTheme.colorScheme.surfaceContainer
            },
            contentColor = if (record.isFlagged) {
                MaterialTheme.colorScheme.onErrorContainer
            } else {
                MaterialTheme.colorScheme.onSurface
            },
        ),
    ) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Text(status, style = MaterialTheme.typography.titleSmall)
            Text(sender, style = MaterialTheme.typography.bodyMedium)
            Text(when_, style = MaterialTheme.typography.bodySmall)
            // Rule names, never the pattern that produced them.
            reasons.forEach { reason ->
                Text(
                    stringResource(R.string.warning_reason_bullet, reason),
                    style = MaterialTheme.typography.bodySmall,
                )
            }
        }
    }
}
