package ai.raksha.app.core

import android.app.ActivityManager
import android.app.ApplicationExitInfo
import android.content.Context
import android.os.Build

/**
 * Reports when Android last stopped the app outright.
 *
 * A force-stopped app receives no broadcasts until it is launched again —
 * measured: `am force-stop`, then an SMS, produced no scan, no process, and
 * `stopped=true`. That is deliberate platform behaviour and not ours to change.
 *
 * What *is* ours is the claim the UI makes. `protected_status` says "Messages
 * are checked and warnings can reach you", and it said exactly that to a user
 * who had been unprotected since whenever the app was last killed. A user who
 * believes they are protected and is not is this product's own failure mode
 * arriving from our side (#91 §2).
 *
 * The app cannot know *which* messages it missed — nothing is stored, and the
 * platform does not replay them — so it does not pretend to. It reports the
 * interruption and its time, and leaves the inference to the reader.
 *
 * Only detectable on API 30+, where `getHistoricalProcessExitReasons` exists.
 * Below that this reports nothing rather than guessing, and the UI simply does
 * not show the notice: a false reassurance is bad, but a fabricated alarm on a
 * cheap old handset is worse.
 */
object InterruptionMonitor {

    /**
     * When the app was last force-stopped, or null if it was not, if the reason
     * is not one of ours to report, or if the platform is too old to say.
     */
    fun lastForceStopMillis(context: Context): Long? {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.R) return null

        val manager = context.getSystemService(ActivityManager::class.java) ?: return null
        val exits = try {
            manager.getHistoricalProcessExitReasons(context.packageName, 0, MAX_EXITS)
        } catch (error: Exception) {
            // Documented to throw only on a bad package name, but this runs on
            // every resume and is not worth a crash.
            SafeLog.failure("exit-reason lookup", error)
            return null
        }

        return exits
            .firstOrNull { it.reason in USER_STOP_REASONS }
            ?.timestamp
    }

    /**
     * True when the app was force-stopped more recently than the user last
     * acknowledged, so the notice is shown once per interruption rather than
     * on every launch.
     */
    fun hasUnacknowledgedInterruption(context: Context, preferences: ScanPreferences): Boolean {
        // Nothing was being scanned anyway, so an interruption is not news.
        if (!preferences.isScanningEnabled) return false
        val stoppedAt = lastForceStopMillis(context) ?: return false
        return stoppedAt > preferences.acknowledgedInterruptionMillis
    }

    private const val MAX_EXITS = 8

    /**
     * REASON_USER_REQUESTED is force-stop from Settings; REASON_USER_STOPPED is
     * the user or profile being stopped. Both leave the app unable to receive
     * broadcasts, which is the only property that matters here.
     *
     * Deliberately excludes crashes, ANRs and low-memory kills: those restart on
     * the next broadcast, so they do not produce the silent window this notice
     * is about, and reporting them would train the user to ignore it.
     */
    private val USER_STOP_REASONS: Set<Int>
        get() = setOf(
            ApplicationExitInfo.REASON_USER_REQUESTED,
            ApplicationExitInfo.REASON_USER_STOPPED,
        )
}
