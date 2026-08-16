package ai.raksha.app.call

import ai.raksha.app.core.SafeLog
import android.app.role.RoleManager
import android.content.Context
import android.content.Intent
import android.os.Build

/**
 * Whether this app is allowed to see calls before they are answered.
 *
 * **The permission story, which is why layer 3 could be built now.** A call
 * screening app holds `ROLE_CALL_SCREENING`, granted by the user through a
 * system dialog. There is no restricted permission, no Play declaration and no
 * review queue — which matters while `RECEIVE_SMS` sits in Google's, because it
 * makes this the one interception layer whose schedule nobody else controls
 * (#116 §4).
 *
 * **The reach, which is narrower than §4 implies.** Measured against the SDK
 * rather than assumed:
 *
 *  - `CallScreeningService` exists from API 24, but a non-dialer app has no way
 *    to be bound to one until `RoleManager` arrives at **API 29**. Below that
 *    the only route is replacing the user's dialer, which needs `CALL_PHONE`, a
 *    whole dialer UI, and lands right back in the restricted-permission queue
 *    this layer exists to avoid.
 *  - `Call.Details.getContactDisplayName()` arrives at **API 30**, and that is
 *    the guard that stops a number in the user's own contacts being warned
 *    about.
 *
 * So the floor here is 30, not 29 and not `minSdk` 24. Screening without the
 * ability to recognise the user's own contacts is the benign-half failure that
 * gets a feature switched off for good, and #116 is explicit that the benign
 * half is the important half. A user on 24–29 is told plainly that their
 * Android version cannot do this, in the same register as the force-stop
 * notice: the app does not claim a layer it does not have.
 */
object CallScreeningRole {

    /**
     * Whether this Android version can screen calls at all.
     *
     * `R` is API 30. See the class note for why the floor is not 29.
     */
    fun isSupported(): Boolean = Build.VERSION.SDK_INT >= Build.VERSION_CODES.R

    /**
     * Whether the role exists on this device. Distinct from [isSupported]:
     * a device with no telephony, or an OEM build without a screening role, can
     * be new enough and still have nothing to grant.
     */
    fun isAvailable(context: Context): Boolean {
        if (!isSupported()) return false
        val manager = context.getSystemService(RoleManager::class.java) ?: return false
        return try {
            manager.isRoleAvailable(RoleManager.ROLE_CALL_SCREENING)
        } catch (error: Exception) {
            SafeLog.failure("role availability", error)
            false
        }
    }

    /**
     * Whether the user has actually granted it.
     *
     * Re-read rather than remembered. The role can be handed to another app from
     * system settings at any time, and this app would never hear about it — the
     * same shape of silent revocation #93 found for force-stop, where the UI
     * went on claiming protection that had stopped.
     */
    fun isHeld(context: Context): Boolean {
        if (!isSupported()) return false
        val manager = context.getSystemService(RoleManager::class.java) ?: return false
        return try {
            manager.isRoleHeld(RoleManager.ROLE_CALL_SCREENING)
        } catch (error: Exception) {
            SafeLog.failure("role held", error)
            false
        }
    }

    /** The system dialog asking for the role, or null if it cannot be asked for. */
    fun requestIntent(context: Context): Intent? {
        if (!isAvailable(context)) return null
        val manager = context.getSystemService(RoleManager::class.java) ?: return null
        return try {
            manager.createRequestRoleIntent(RoleManager.ROLE_CALL_SCREENING)
        } catch (error: Exception) {
            SafeLog.failure("role request", error)
            null
        }
    }
}
