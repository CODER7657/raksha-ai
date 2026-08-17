package ai.raksha.app.sms

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.provider.Telephony
import ai.raksha.app.core.SafeLog
import ai.raksha.app.core.ServiceLocator
import ai.raksha.app.core.ScamNotifier
import ai.raksha.app.core.ScanPreferences
import ai.raksha.app.data.RuleHitRecord
import ai.raksha.rules.REVIEW_STATUS
import ai.raksha.rules.offlineRuleHits
import java.util.concurrent.Executors

/**
 * Layer 2 of the interception model: reads an incoming SMS, scores it **on the
 * device**, and raises a notification. Zero user action — the victim does not
 * have to suspect anything, which is the entire point of V2.
 *
 * The message text does not leave the phone. It is not sent anywhere and not
 * logged (see [SafeLog]).
 *
 * It **is** written to disk now, which it was not before #116 §3. The scan is
 * recorded so the user can answer "why did it flag that?" later — constraint 1
 * of the project, and the thing the phone could not do while the website
 * could. The terms that storage is held to are on [ai.raksha.app.data.ScanStore]:
 * capped, clearable, gone on uninstall, and structurally unable to leave the
 * device because the app holds no `INTERNET` permission. The user can switch it
 * off, and switching it off clears what is already there.
 *
 * ### Why not WorkManager
 *
 * #29 §5 suggests `goAsync()` and handing off to WorkManager. Half of that is
 * right and half would defeat the feature. A broadcast receiver has ~10 seconds
 * before an ANR and must not do work on the main thread, so [goAsync] plus a
 * background executor is correct. But WorkManager is a *deferrable* scheduler —
 * its whole contract is that work runs eventually, and under Doze "eventually"
 * can be minutes. A fraud warning that arrives after the user has already
 * replied with an OTP is worth nothing.
 *
 * A rule sweep is around a millisecond (`RuleLatencyTest`), so it comfortably
 * fits the receiver's own window. WorkManager becomes the right tool in Phase 3,
 * where an opt-in cloud escalation can genuinely be retried later.
 */
class SmsReceiver : BroadcastReceiver() {

    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action != Telephony.Sms.Intents.SMS_RECEIVED_ACTION) return

        val appContext = context.applicationContext

        // The scanning-enabled check used to happen here, on the main thread.
        // First access to SharedPreferences reads from disk, and this is the
        // main thread of a broadcast with a ~10s ANR budget — on a cheap handset
        // that is exactly the kind of small cost that adds up (#49). It now
        // happens inside the executor, alongside the scan.
        //
        // Extraction stays here on purpose: the intent's extras are not
        // guaranteed to outlive the broadcast, so they must be read before
        // going async.
        val parts = try {
            Telephony.Sms.Intents.getMessagesFromIntent(intent)
        } catch (error: Exception) {
            SafeLog.failure("intent parsing", error)
            return
        } ?: return

        if (parts.isEmpty()) return

        // Multipart reassembly: score the whole message, never a fragment.
        val sender = parts.first().displayOriginatingAddress.orEmpty()
        val timestamp = parts.first().timestampMillis
        val body = assembleMultipart(parts.mapNotNull { it.displayMessageBody })
        if (parts.size > 1) SafeLog.partsAssembled(parts.size)
        if (body.isBlank()) return

        val pendingResult = goAsync()
        EXECUTOR.execute {
            try {
                scoreAndNotify(appContext, sender, body, timestamp)
            } catch (error: Throwable) {
                SafeLog.failure("scan", error)
            } finally {
                // Must always run, or the receiver is held alive and the
                // process is killed for taking too long.
                pendingResult.finish()
            }
        }
    }

    private fun scoreAndNotify(context: Context, sender: String, body: String, timestamp: Long) {
        // Off the main thread: this is the first touch of SharedPreferences and
        // therefore the disk read. Checked before deduplication so a disabled
        // app does no work at all beyond the read itself.
        val preferences = ScanPreferences(context)
        if (!preferences.isScanningEnabled) return

        if (!DEDUPLICATOR.offer(sender, body, timestamp)) {
            SafeLog.duplicateSkipped()
            return
        }

        val startedAt = System.nanoTime()
        val hits = offlineRuleHits(body, preferences.language)
        val elapsedMillis = (System.nanoTime() - startedAt) / 1_000_000

        SafeLog.scanCompleted(hits.map { it.ruleId }, elapsedMillis)

        // Recorded before notifying, and recorded whether or not anything fired.
        // A history that only holds the flagged ones cannot answer "did it even
        // look at that message?", which is the question a user asks when they
        // were NOT warned about something that worried them.
        //
        // Deliberately outside the latency measurement above: the number
        // reported is what the rule sweep costs, and folding a disk write into
        // it would quietly inflate the figure the ~200ms budget is checked
        // against.
        if (preferences.isHistoryEnabled) {
            try {
                ServiceLocator.scanStore(context).record(
                    scannedAtMillis = timestamp,
                    sender = sender,
                    language = preferences.language,
                    body = body,
                    hits = hits.map { RuleHitRecord(it.ruleId, it.pattern, it.matchedText) },
                    ruleReviewStatus = REVIEW_STATUS[preferences.language] ?: "unreviewed",
                )
                // Layer 1 reads its set from this store and caches it in memory,
                // so a scan recorded now is invisible to a call arriving in a
                // moment unless the set is told to reload. Message-then-call is
                // the sequence layer 3 exists for, and on the first emulator run
                // it came back NOT_KNOWN.
                //
                // No I/O here: the rebuild is paid for by the screening path,
                // which has already released the call before it looks anything
                // up.
                ServiceLocator.callReputation(context).invalidate()
            } catch (error: Exception) {
                // A failed write must not cost the user their warning, which is
                // the part that matters in the next few seconds.
                SafeLog.failure("history write", error)
            }
        }

        if (hits.isEmpty()) return
        ScamNotifier(context).warn(sender, hits.map { it.ruleId })
    }

    private companion object {
        /**
         * Single thread, shared across broadcasts. Scoring is ~1ms, so there is
         * nothing to gain from a pool, and a single thread keeps the ordering
         * that makes deduplication meaningful.
         */
        val EXECUTOR = Executors.newSingleThreadExecutor { runnable ->
            Thread(runnable, "raksha-sms-scan").apply { isDaemon = true }
        }

        /**
         * Static so it survives the receiver instance, which Android recreates
         * per broadcast. Holds digests only, never text.
         */
        val DEDUPLICATOR = RecentMessageFilter()
    }
}
