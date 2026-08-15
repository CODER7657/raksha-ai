package ai.raksha.app.core

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.os.Build
import androidx.core.app.NotificationManagerCompat
import androidx.core.content.ContextCompat

/**
 * What the app can actually do for the user right now.
 *
 * The reason this is an enum rather than a pair of booleans is
 * [SCANNING_WITHOUT_WARNINGS]. Before #49 the UI had one "permission denied"
 * message covering every unhappy path, which flattened the two very different
 * failures into one:
 *
 *  - SMS denied: nothing is scanned. The user is unprotected and it is obvious.
 *  - **SMS granted, notifications denied: everything is scanned, scams are
 *    detected, and every warning goes nowhere.** The user believes they are
 *    covered and they are not, which is worse than being plainly switched off.
 *
 * A Play reviewer testing the deny path lands in the second state, sends a scam,
 * sees nothing, and has no way to tell a permission problem from a broken app —
 * which is why #49 puts this ahead of the demo video in #39.
 */
enum class ProtectionState {

    /** Scanning is switched off in the app. Nothing is read. */
    OFF,

    /** The user refused SMS access. Nothing can be scanned. */
    NO_SMS_PERMISSION,

    /**
     * Messages are being scanned and warnings cannot be delivered.
     * Detection works; the user just never hears about it.
     */
    SCANNING_WITHOUT_WARNINGS,

    /** Scanning and warnings both working. */
    PROTECTED,
    ;

    companion object {

        fun of(context: Context): ProtectionState {
            if (!ScanPreferences(context).isScanningEnabled) return OFF
            if (!hasSmsPermission(context)) return NO_SMS_PERMISSION
            if (!canShowWarnings(context)) return SCANNING_WITHOUT_WARNINGS
            return PROTECTED
        }

        fun hasSmsPermission(context: Context): Boolean =
            ContextCompat.checkSelfPermission(context, Manifest.permission.RECEIVE_SMS) ==
                PackageManager.PERMISSION_GRANTED

        /**
         * Both the runtime permission and the system-settings switch, because
         * either one being off produces the same silence. `areNotificationsEnabled`
         * covers the app being muted after the permission was granted, which is a
         * separate and equally invisible way to end up in
         * [SCANNING_WITHOUT_WARNINGS].
         */
        fun canShowWarnings(context: Context): Boolean {
            val permitted = Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU ||
                ContextCompat.checkSelfPermission(
                    context,
                    Manifest.permission.POST_NOTIFICATIONS,
                ) == PackageManager.PERMISSION_GRANTED
            return permitted && NotificationManagerCompat.from(context).areNotificationsEnabled()
        }
    }
}
