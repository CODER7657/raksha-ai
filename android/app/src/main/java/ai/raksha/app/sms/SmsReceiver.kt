package ai.raksha.app.sms

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.provider.Telephony
import ai.raksha.app.core.SafeLog
import ai.raksha.app.core.ScamNotifier
import ai.raksha.app.core.ScanPreferences
import ai.raksha.rules.offlineRuleHits
import java.util.concurrent.Executors

/**
 * Layer 2 of the interception model: reads an incoming SMS, scores it **on the
 * device**, and raises a notification. Zero user action — the victim does not
 * have to suspect anything, which is the entire point of V2.
 *
 * The message text does not leave the phone. It is not sent anywhere, not
 * written to disk, and not logged (see [SafeLog]).
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
        if (!ScanPreferences(appContext).isScanningEnabled) return

        // Extract on the main thread — the intent's extras are not guaranteed
        // to outlive the broadcast — but score off it.
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
        if (!DEDUPLICATOR.offer(sender, body, timestamp)) {
            SafeLog.duplicateSkipped()
            return
        }

        val preferences = ScanPreferences(context)
        val startedAt = System.nanoTime()
        val hits = offlineRuleHits(body, preferences.language)
        val elapsedMillis = (System.nanoTime() - startedAt) / 1_000_000

        SafeLog.scanCompleted(hits.map { it.ruleId }, elapsedMillis)

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
