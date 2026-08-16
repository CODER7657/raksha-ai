package ai.raksha.app.call

import ai.raksha.app.core.SafeLog
import ai.raksha.app.core.ServiceLocator
import android.os.Build
import android.telecom.Call
import android.telecom.CallScreeningService
import androidx.annotation.RequiresApi
import java.util.concurrent.Executors

/**
 * Layer 3. Sees an incoming call before it is answered, and never interferes
 * with it.
 *
 * **It always allows the call.** `setRejectCall`, `setSilenceCall` and
 * `setSkipCallLog` are the four lines a future contributor will reach for, and
 * none of them is called anywhere in this file. ARCHITECTURE §01 is explicit
 * that layers 1–4 are advisory and only the payment interrupt is terminal, and
 * constraint 4 says over-warning is recoverable while being confidently wrong is
 * not. A wrong verdict here costs the user a glance at a notification; a wrong
 * verdict that rejected or silenced the call could cost them a hospital ringing
 * back. So the class holds the screening role in order to *observe*, not to
 * screen — which is also the only way to see a caller's number before answer
 * without asking for `READ_CALL_LOG`.
 *
 * **Why the latency problem §4 warns about does not arise.** §4 is right that
 * the platform gives a short window and that missing it means the call rings
 * through unscreened — a silent failure. The answer here is not to be fast
 * inside the window but to leave it immediately: the response is unconditional,
 * so it is sent before any reputation is consulted at all. Nothing the lookup
 * does can delay the call, because the call is already released. The reputation
 * work then happens on a background thread, where a slow disk read costs a
 * warning that arrives a moment later into a ring that lasts half a minute.
 *
 * That inverts §4's rule rather than following it — "read an answer, don't
 * compute one" matters when the answer gates the call, and here it does not.
 * The in-memory set is still worth having so the warning lands early in the
 * ring rather than late, but nothing depends on it being ready.
 */
@RequiresApi(Build.VERSION_CODES.N)
class RakshaCallScreeningService : CallScreeningService() {

    /**
     * One thread, created per service instance and shut down with it. The
     * telecom stack binds this service for the duration of a call and unbinds
     * after, so this is not a long-lived pool.
     */
    private val worker = Executors.newSingleThreadExecutor()

    override fun onScreenCall(callDetails: Call.Details) {
        // Unconditionally, and before anything else can throw. Every path below
        // this line has already released the call.
        allow(callDetails)

        // Read off the telecom thread while the object is certainly valid, then
        // hand the background thread plain strings rather than a Call.Details
        // whose lifetime belongs to the platform.
        val number = try {
            callDetails.handle?.schemeSpecificPart
        } catch (error: Exception) {
            SafeLog.failure("reading call handle", error)
            null
        }
        val contactName = knownContactName(callDetails)
        val incoming = isIncoming(callDetails)

        worker.execute { considerWarning(number, contactName, incoming) }
    }

    /**
     * The response that changes nothing: every flag left false means allow the
     * call, ring normally, log it normally, notify normally.
     *
     * Built explicitly rather than left implicit because `respondToCall` must be
     * called exactly once — a screening service that returns without responding
     * makes the user wait for the platform's timeout on every single call.
     */
    private fun allow(callDetails: Call.Details) {
        try {
            respondToCall(callDetails, CallResponse.Builder().build())
        } catch (error: Exception) {
            SafeLog.failure("responding to call", error)
        }
    }

    private fun considerWarning(number: String?, contactName: String?, incoming: Boolean) {
        val startedAt = System.currentTimeMillis()

        // The API 30 floor, enforced rather than only documented. On 29 the role
        // can be granted and this service bound, and there is no way to tell
        // whether the caller is one of the user's own contacts — so it would
        // warn about a number in their address book with no guard at all.
        // Allowing the call and saying nothing is the honest behaviour there.
        if (!CallScreeningRole.isSupported()) return

        // Outgoing calls are screened too from API 29. Warning someone about a
        // number they just dialled themselves is noise.
        if (!incoming) return

        // The benign half. Somebody in the user's own contacts is not a stranger
        // to be warned about, whatever their number once sent.
        //
        // A blank name is *not* evidence the caller is unknown — it is also what
        // an unavailable lookup returns, and #123 settled that inability to
        // verify is a caveat and never a signal. It therefore only ever
        // suppresses a warning and never causes one.
        if (!contactName.isNullOrBlank()) return

        val reputation = ServiceLocator.callReputation(applicationContext)
        if (!reputation.isReady) reputation.refresh()

        val known = reputation.lookup(number)
        SafeLog.callScreened(known != null, System.currentTimeMillis() - startedAt)
        if (known == null) return

        CallWarningNotifier(applicationContext).warn(known)
    }

    /**
     * The caller's name from the user's contacts, or null when the platform will
     * not say.
     *
     * **Unverified, and deliberately not asserted anywhere.** The SDK puts
     * `getContactDisplayName` on `Call.Details` from API 30, but whether it is
     * populated for a screening service holding only `ROLE_CALL_SCREENING` — as
     * opposed to one also holding `READ_CONTACTS`, which this app does not and
     * will not request — is a question for a device, not for a doc. It is
     * measured in the instrumentation notes rather than assumed here, and the
     * failure mode if it is always null is over-warning on a contact, which is
     * the recoverable direction.
     */
    private fun knownContactName(callDetails: Call.Details): String? {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.R) return null
        return try {
            callDetails.contactDisplayName
        } catch (error: Exception) {
            SafeLog.failure("reading contact name", error)
            null
        }
    }

    private fun isIncoming(callDetails: Call.Details): Boolean {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.Q) return true
        return try {
            callDetails.callDirection == Call.Details.DIRECTION_INCOMING
        } catch (error: Exception) {
            SafeLog.failure("reading call direction", error)
            true
        }
    }

    override fun onDestroy() {
        worker.shutdown()
        super.onDestroy()
    }
}
