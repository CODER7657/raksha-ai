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
 *  - `Call.Details.getContactDisplayName()` arrives at **API 30**.
 *
 * So the floor here is 30, and **the reason is not the one this class was
 * written with.** The floor was set believing `getContactDisplayName` was what
 * stopped a number in the user's own contacts being warned about. Measured on
 * an emulator at API 36, the platform never binds a third-party screening
 * service for a contact at all — `RakshaCallScreeningService` has the control
 * pair — so that check is a backstop rather than the mechanism, and the
 * benign-half argument for the floor does not hold.
 *
 * The floor stays at 30 anyway, for a weaker and honest reason: the platform's
 * exclusion is measured on 36 and **not** on 29, and on 29 there is no
 * `getContactDisplayName` to fall back on if it behaves differently. Choosing 30
 * is preferring an unmeasured feature gap to an unmeasured false positive, which
 * is the direction constraint 4 points.
 *
 * **Worth widening to 29 if someone measures it there**, since that is more of
 * the cheap handsets THREAT-LANDSCAPE §02 designs for. It needs an API 29 system
 * image, which this checkout does not have.
 *
 * A user below the floor is told plainly that their Android version cannot do
 * this, in the same register as the force-stop notice: the app does not claim a
 * layer it does not have.
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
