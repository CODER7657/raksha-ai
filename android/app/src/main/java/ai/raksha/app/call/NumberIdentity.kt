package ai.raksha.app.call

/**
 * Decides whether two pieces of telephony text name the same subscriber.
 *
 * Layer 1 compares an **SMS sender** against a **ringing caller**, and those two
 * arrive from different parts of the platform in different shapes: a sender may
 * be `98765 43210`, the caller `tel:+919876543210`. Something has to reconcile
 * them, and what that something assumes is the interesting part.
 *
 * **Why the key is the last ten digits and not E.164.** Turning `9876543210`
 * into `+919876543210` requires deciding the number is Indian. That is true for
 * almost every user this is built for and false for the ones holding a foreign
 * SIM, and a wrong region assumption fails *silently* — the number simply never
 * matches, and layer 1 protects nobody without ever erroring. Comparing the
 * trailing significant digits needs no region at all.
 *
 * The cost is a looser comparison: two subscribers in different countries whose
 * numbers share their last ten digits collapse to one identity. For that to
 * produce a wrong warning, the user would have to have received a scam SMS from
 * the number that collides with their caller. That is a worse trade than E.164
 * only if the region is knowable, and it is not.
 *
 * **Most of this class refuses.** In India the majority of SMS arrives from
 * alphanumeric sender IDs — `VM-HDFCBK` — which cannot be dialled and so can
 * never match a caller. Admitting them would leave the set looking populated
 * while being unable to fire.
 */
object NumberIdentity {

    /**
     * A comparable identity for [raw], or null when it does not name something
     * dialable.
     *
     * Null is not a weak yes. A caller this returns null for is one we cannot
     * identify, and #123 settled what that means: inability-to-verify is a
     * caveat, never a signal. It produces no entry and no warning.
     */
    fun keyOf(raw: String?): String? {
        val text = raw?.trim().orEmpty()
        if (text.isEmpty()) return null

        // Call.Details.getHandle() is a URI; SMS senders are bare strings.
        val withoutScheme = text.removePrefix(TEL_SCHEME).removePrefix(TEL_SCHEME.uppercase())

        // Any letter means this is a sender ID or a placeholder like "Unknown",
        // not a number. Checked before stripping punctuation, because stripping
        // first would turn "HDFCBK" into an empty string and lose the reason.
        if (withoutScheme.any { it.isLetter() }) return null

        val digits = withoutScheme.filter { it.isDigit() }
        if (digits.length < MIN_DIALABLE_DIGITS) return null

        return if (digits.length > SIGNIFICANT_DIGITS) {
            digits.takeLast(SIGNIFICANT_DIGITS)
        } else {
            digits
        }
    }

    private const val TEL_SCHEME = "tel:"

    /**
     * Below this, the digits are a short code rather than a subscriber: `121` is
     * a carrier line and `1930` is India's cybercrime helpline. Neither is an
     * identity worth remembering, and warning about 1930 — the number a victim
     * is told to ring — would be an actively harmful false positive.
     */
    private const val MIN_DIALABLE_DIGITS = 7

    /**
     * Enough to identify a subscriber once the country code and any trunk
     * prefix are dropped. Ten because Indian mobile numbers are ten digits, so
     * a national and an international rendering of the same number agree here.
     */
    private const val SIGNIFICANT_DIGITS = 10
}
