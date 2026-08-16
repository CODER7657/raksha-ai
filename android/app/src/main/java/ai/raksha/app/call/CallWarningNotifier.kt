package ai.raksha.app.call

import ai.raksha.app.MainActivity
import ai.raksha.app.R
import ai.raksha.app.core.RuleLabels
import ai.raksha.app.core.SafeLog
import ai.raksha.app.data.FlaggedSender
import android.Manifest
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import androidx.core.content.ContextCompat

/**
 * The warning for a call from a number this phone has already seen scamming.
 *
 * A separate channel from the SMS warnings on purpose: they interrupt
 * differently and a user who wants one may not want the other, and a channel is
 * the only granularity Android gives them to say so.
 *
 * **It carries the evidence, not just the verdict.** The notification names the
 * rules that fired on that number's message and opens the trace for the exact
 * scan behind it. Constraint 1 is that a user can always see their own trace,
 * and a warning about a caller that cannot say *why* is the "trust us" this
 * product exists not to ship — especially here, where the claim is about a
 * person rather than a message.
 *
 * Advisory, like [ScamNotifier]: `PRIORITY_HIGH` and never a full-screen intent.
 * The call is ringing normally the whole time.
 */
class CallWarningNotifier(private val context: Context) {

    fun warn(known: FlaggedSender) {
        ensureChannel()

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU &&
            ContextCompat.checkSelfPermission(context, Manifest.permission.POST_NOTIFICATIONS) !=
            PackageManager.PERMISSION_GRANTED
        ) {
            SafeLog.warningSuppressed(known.ruleIds, "POST_NOTIFICATIONS denied")
            return
        }
        if (!NotificationManagerCompat.from(context).areNotificationsEnabled()) {
            SafeLog.warningSuppressed(known.ruleIds, "notifications disabled in settings")
            return
        }

        val title = context.getString(R.string.call_warning_title)
        val summary = context.getString(R.string.call_warning_summary, known.sender)
        val reasons = known.ruleIds.map { RuleLabels.labelFor(context, it) }

        val style = NotificationCompat.InboxStyle().setBigContentTitle(title).addLine(summary)
        reasons.forEach { style.addLine(context.getString(R.string.warning_reason_bullet, it)) }

        val notification = NotificationCompat.Builder(context, CHANNEL_ID)
            .setSmallIcon(android.R.drawable.stat_sys_warning)
            .setContentTitle(title)
            .setContentText(summary)
            .setStyle(style)
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .setCategory(NotificationCompat.CATEGORY_ERROR)
            .setAutoCancel(true)
            // The number is on the lock screen already, from the incoming-call
            // UI. The reasons are not, and they are an inference about the
            // person calling — so the expanded content stays private.
            .setVisibility(NotificationCompat.VISIBILITY_PRIVATE)
            .setContentIntent(traceIntent(known.scanId))
            .build()

        try {
            NotificationManagerCompat.from(context).notify(notificationId(known), notification)
        } catch (securityError: SecurityException) {
            SafeLog.failure("notify", securityError)
        }
    }

    /** Opens the app on the trace for the message that put this number in the set. */
    private fun traceIntent(scanId: Long): PendingIntent? {
        val intent = Intent(context, MainActivity::class.java)
            .setAction(Intent.ACTION_VIEW)
            .putExtra(MainActivity.EXTRA_SCAN_ID, scanId)
            .addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_SINGLE_TOP)
        return PendingIntent.getActivity(
            context,
            scanId.toInt(),
            intent,
            // IMMUTABLE because nothing should be able to rewrite which scan
            // this opens; required from API 31 and correct before it.
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
    }

    /**
     * One notification per number, so a second call from the same scammer
     * replaces the first rather than stacking.
     *
     * Offset from [ScamNotifier]'s ids, which are also sender hashes: without
     * it, an SMS warning and a call warning about the same number would collide
     * and one would silently replace the other.
     */
    private fun notificationId(known: FlaggedSender): Int = known.sender.hashCode() xor ID_SALT

    private fun ensureChannel() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return
        val manager = context.getSystemService(NotificationManager::class.java) ?: return
        if (manager.getNotificationChannel(CHANNEL_ID) != null) return

        val channel = NotificationChannel(
            CHANNEL_ID,
            context.getString(R.string.call_channel_name),
            NotificationManager.IMPORTANCE_HIGH,
        ).apply {
            description = context.getString(R.string.call_channel_description)
            enableVibration(true)
        }
        manager.createNotificationChannel(channel)
    }

    private companion object {
        const val CHANNEL_ID = "call_warnings"
        const val ID_SALT = 0x3110
    }
}
