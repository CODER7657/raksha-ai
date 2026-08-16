package ai.raksha.app.ui.detail

import android.app.Application
import android.text.format.DateUtils
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewModelScope
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

data class TraceUiState(
    val loading: Boolean = true,
    val record: ScanRecord? = null,
)

class TraceDetailViewModel(application: Application) : AndroidViewModel(application) {

    private val _state = MutableStateFlow(TraceUiState())
    val state: StateFlow<TraceUiState> = _state.asStateFlow()

    fun load(id: Long) {
        viewModelScope.launch {
            val record = withContext(Dispatchers.IO) {
                ServiceLocator.scanStore(getApplication()).byId(id)
            }
            _state.value = TraceUiState(loading = false, record = record)
        }
    }
}

/**
 * The evidence behind one verdict, mirroring `TraceViewer.tsx`.
 *
 * Same sections in the same order as the web: what fired, what it matched in
 * the message, and how much the rules for that language are worth. The website
 * also shows retrieved patterns, the model identity and the audit record —
 * absent here rather than faked, because the phone has no network and produced
 * none of them. An empty panel claiming to be evidence is worse than a missing
 * one.
 *
 * **Never a raw regex.** Rules are named through `trace.rules.*`, the same
 * bundle the site uses. `pattern` is stored (the trace schema names it) and is
 * not rendered: a regex in front of a user explains nothing and looks like a
 * malfunction.
 */
@Composable
fun TraceDetailScreen(
    scanId: Long,
    viewModel: TraceDetailViewModel,
) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    val context = LocalContext.current

    androidx.compose.runtime.LaunchedEffect(scanId) { viewModel.load(scanId) }

    val record = state.record
    if (state.loading) return

    if (record == null) {
        Column(Modifier.fillMaxSize().padding(24.dp)) {
            Text(stringResource(R.string.trace_missing), style = MaterialTheme.typography.bodyMedium)
        }
        return
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(24.dp)
            .verticalScroll(rememberScrollState()),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Text(
            stringResource(
                if (record.isFlagged) R.string.history_flagged else R.string.history_clean,
            ),
            style = MaterialTheme.typography.titleMedium,
        )
        Text(
            record.sender.ifBlank { stringResource(R.string.warning_summary_no_sender) },
            style = MaterialTheme.typography.bodyMedium,
        )
        Text(
            DateUtils.getRelativeTimeSpanString(
                record.scannedAtMillis, System.currentTimeMillis(), DateUtils.MINUTE_IN_MILLIS,
            ).toString(),
            style = MaterialTheme.typography.bodySmall,
        )

        HorizontalDivider()

        // --- The message ------------------------------------------------------
        Text(stringResource(R.string.trace_message), style = MaterialTheme.typography.titleSmall)
        Card(modifier = Modifier.fillMaxWidth()) {
            Text(
                record.body,
                modifier = Modifier.padding(16.dp),
                style = MaterialTheme.typography.bodyMedium,
            )
        }

        // --- What fired -------------------------------------------------------
        Text(stringResource(R.string.trace_rules_fired), style = MaterialTheme.typography.titleSmall)

        if (record.hits.isEmpty()) {
            // The web draws the same distinction: "no rule matched" is a
            // statement about the message, not an absence of information.
            Text(
                stringResource(R.string.trace_no_rules),
                style = MaterialTheme.typography.bodySmall,
            )
        } else {
            record.hits.forEach { hit ->
                Card(
                    modifier = Modifier.fillMaxWidth(),
                    colors = CardDefaults.cardColors(
                        containerColor = MaterialTheme.colorScheme.surfaceContainer,
                        contentColor = MaterialTheme.colorScheme.onSurface,
                    ),
                ) {
                    Column(
                        Modifier.padding(16.dp),
                        verticalArrangement = Arrangement.spacedBy(6.dp),
                    ) {
                        Text(
                            RuleLabels.labelFor(context, hit.ruleId),
                            style = MaterialTheme.typography.bodyMedium,
                        )
                        Text(
                            stringResource(R.string.trace_matched_text),
                            style = MaterialTheme.typography.labelSmall,
                        )
                        Text(hit.matchedText, style = MaterialTheme.typography.bodySmall)
                    }
                }
            }
        }

        HorizontalDivider()

        // --- How much the rules are worth ------------------------------------
        //
        // `rule_review` in the trace schema, and it exists for exactly this
        // screen: somebody scanning in one of the eight unreviewed languages had
        // no way to know how much to trust what they were being shown.
        Text(stringResource(R.string.trace_rule_review), style = MaterialTheme.typography.titleSmall)
        Text(
            stringResource(
                when (record.ruleReviewStatus) {
                    "in-service" -> R.string.trace_review_in_service
                    "inherited" -> R.string.trace_review_inherited
                    else -> R.string.trace_review_unreviewed
                },
            ),
            style = MaterialTheme.typography.bodySmall,
        )

        // What the phone cannot know, said plainly rather than left as a gap the
        // reader has to notice.
        Text(
            stringResource(R.string.trace_device_only),
            style = MaterialTheme.typography.bodySmall,
        )
    }
}
