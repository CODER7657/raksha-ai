package ai.raksha.app.core

import android.Manifest
import android.app.NotificationChannel
import android.app.NotificationManager
import android.content.Context
import android.content.pm.PackageManager
import android.os.Build
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import androidx.core.content.ContextCompat
import ai.raksha.app.R

/**
 * Raises the warning for a message that tripped a rule.
 *
 * **What this deliberately does not include: the message text.** Showing it
 * would put scanned content on the lock screen and into the reach of every
 * installed notification-listener service — a route out of the device that the
 * "nothing leaves the phone" claim does not survive. The user has the message in
 * their SMS app already; what they lack is the interpretation, so that is what
 * the notification carries.
 *
 * The sender is included because it is what makes the warning actionable, and
 * it is already visible in the messaging app's own notification.
 *
 * This is the advisory surface of layer 2. ARCHITECTURE §01 is explicit that
 * layers 1–4 are advisory and only the payment interrupt is terminal, so this
 * is built expecting to be ignored sometimes.
 */
class ScamNotifier(private val context: Context) {

    fun warn(sender: String, ruleIds: List<String>) {
        if (ruleIds.isEmpty()) return
        ensureChannel()

        // On API 33+ the user can refuse notifications outright. Posting without
        // the permission throws, so there is nothing to do but stop — but it is
        // recorded on the way out, because silently returning here is
        // indistinguishable from "nothing was detected" (#49).
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU &&
            ContextCompat.checkSelfPermission(context, Manifest.permission.POST_NOTIFICATIONS) !=
            PackageManager.PERMISSION_GRANTED
        ) {
            SafeLog.warningSuppressed(ruleIds, "POST_NOTIFICATIONS denied")
            return
        }

        // Notifications can also be switched off wholesale in system settings,
        // or the channel muted, without the permission being revoked. Same
        // user-visible outcome — nothing appears — so it gets the same trace.
        if (!NotificationManagerCompat.from(context).areNotificationsEnabled()) {
            SafeLog.warningSuppressed(ruleIds, "notifications disabled in settings")
            return
        }

        val reasons = ruleIds.map { RuleLabels.labelFor(context, it) }
        val title = context.getString(R.string.warning_title)
        val summary = if (sender.isBlank()) {
            context.getString(R.string.warning_summary_no_sender)
        } else {
            context.getString(R.string.warning_summary, sender)
        }

        val style = NotificationCompat.InboxStyle().setBigContentTitle(title).addLine(summary)
        reasons.forEach { style.addLine(context.getString(R.string.warning_reason_bullet, it)) }

        val notification = NotificationCompat.Builder(context, CHANNEL_ID)
            .setSmallIcon(android.R.drawable.stat_sys_warning)
            .setContentTitle(title)
            .setContentText(reasons.first())
            .setStyle(style)
            // HIGH, not MAX: this is advisory. A full-screen interrupt is
            // reserved for the payment interrupt in layer 5, where the money is
            // actually about to move.
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .setCategory(NotificationCompat.CATEGORY_ERROR)
            .setAutoCancel(true)
            // Public visibility would put the reasons on the lock screen.
            .setVisibility(NotificationCompat.VISIBILITY_PRIVATE)
            .build()

        try {
            NotificationManagerCompat.from(context).notify(notificationId(sender), notification)
        } catch (securityError: SecurityException) {
            // Permission revoked between the check above and here.
            SafeLog.failure("notify", securityError)
        }
    }

    /** One notification per sender, so a second scam SMS replaces the first. */
    private fun notificationId(sender: String): Int =
        if (sender.isBlank()) 0 else sender.hashCode()

    private fun ensureChannel() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return
        val manager = context.getSystemService(NotificationManager::class.java) ?: return
        if (manager.getNotificationChannel(CHANNEL_ID) != null) return

        val channel = NotificationChannel(
            CHANNEL_ID,
            context.getString(R.string.warning_channel_name),
            NotificationManager.IMPORTANCE_HIGH,
        ).apply {
            description = context.getString(R.string.warning_channel_description)
            enableVibration(true)
        }
        manager.createNotificationChannel(channel)
    }

    private companion object {
        const val CHANNEL_ID = "scam_warnings"
    }
}
