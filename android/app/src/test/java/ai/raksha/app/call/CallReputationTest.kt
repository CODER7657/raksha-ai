package ai.raksha.app.call

import ai.raksha.app.data.FlaggedSender
import ai.raksha.app.data.RuleHitRecord
import ai.raksha.app.data.ScanRecord
import ai.raksha.app.data.ScanStore
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertNotNull
import kotlin.test.assertNull
import kotlin.test.assertTrue

/**
 * Layer 1's answer, and the evidence behind it.
 *
 * The reputation set here is not a bought list — it is the phone's memory of
 * layer 2. An entry exists because *this* phone read an SMS from that number
 * and its own rules fired. That gives every entry a trace the user can open,
 * which is constraint 1 met by construction rather than bolted on.
 *
 * The cases that matter most are the ones asserting the set stays *empty*.
 * A reputation set that fills up with things it should not hold is how a
 * benign caller gets warned about, and #116 is explicit that the benign half is
 * the important half.
 */
class CallReputationTest {

    private class FakeStore : ScanStore {
        private val records = mutableListOf<ScanRecord>()
        private var nextId = 1L
        var recording = true

        override fun recent(limit: Int) =
            records.sortedByDescending { it.scannedAtMillis }.take(limit)

        override fun byId(id: Long) = records.firstOrNull { it.id == id }

        override fun record(
            scannedAtMillis: Long,
            sender: String,
            language: String,
            body: String,
            hits: List<RuleHitRecord>,
            ruleReviewStatus: String,
        ): ScanRecord? {
            if (!recording) return null
            val stored = ScanRecord(
                nextId++, scannedAtMillis, sender, language, body, hits, ruleReviewStatus,
            )
            records += stored
            return stored
        }

        override fun clear() = records.clear()
        override fun count() = records.size

        override fun flaggedSenders(): List<FlaggedSender> =
            records.filter { it.isFlagged }
                .sortedByDescending { it.scannedAtMillis }
                .map {
                    FlaggedSender(it.sender, it.id, it.scannedAtMillis, it.hits.map { hit -> hit.ruleId })
                }
    }

    private val otpHit = listOf(RuleHitRecord("otp_share", "\\bOTP\\b", "share your OTP"))

    private fun storeWith(vararg scans: Triple<String, Long, List<RuleHitRecord>>): FakeStore {
        val store = FakeStore()
        scans.forEach { (sender, at, hits) ->
            store.record(at, sender, "en", "Share your OTP now", hits, "in-service")
        }
        return store
    }

    // --- What earns an entry -------------------------------------------------

    @Test
    fun `a number whose message was flagged is known`() {
        val reputation = CallReputation(storeWith(Triple("+919876543210", 1_000L, otpHit)))
        reputation.refresh()

        assertNotNull(reputation.lookup("9876543210"))
    }

    @Test
    fun `the caller and the sender need not be written the same way`() {
        // The SMS arrived national, the call arrives international. This is the
        // whole reason NumberIdentity exists.
        val reputation = CallReputation(storeWith(Triple("09876543210", 1_000L, otpHit)))
        reputation.refresh()

        assertNotNull(reputation.lookup("tel:+919876543210"))
    }

    // --- What must never earn one -------------------------------------------

    @Test
    fun `a number whose message was clean is not known`() {
        // The benign half. A sender the app looked at and cleared must not be
        // warned about when it rings.
        val reputation = CallReputation(storeWith(Triple("+919876543210", 1_000L, emptyList())))
        reputation.refresh()

        assertNull(reputation.lookup("9876543210"))
        assertEquals(0, reputation.size)
    }

    @Test
    fun `an alphanumeric sender never enters the set`() {
        // A flagged message from VM-HDFCBK is a real thing that happens. It is
        // also not dialable, so it can never match a caller — admitting it would
        // leave the set looking populated and unable to fire.
        val reputation = CallReputation(storeWith(Triple("VM-HDFCBK", 1_000L, otpHit)))
        reputation.refresh()

        assertEquals(0, reputation.size)
    }

    @Test
    fun `an unidentifiable caller is never known`() {
        val reputation = CallReputation(storeWith(Triple("+919876543210", 1_000L, otpHit)))
        reputation.refresh()

        // A withheld number is an inability to identify. #123: that is a caveat,
        // never a signal — so it resolves to "no warning", not "warn anyway".
        for (absent in listOf(null, "", "   ", "unknown")) {
            assertNull(reputation.lookup(absent), "should not have matched: $absent")
        }
    }

    // --- Failing safe --------------------------------------------------------

    @Test
    fun `a lookup before the set is loaded answers no, and says it is not ready`() {
        // The phone is ringing and the answer is not in memory yet. Failing safe
        // means the call rings through unwarned — never that the screener stalls
        // waiting, which would miss the window and screen nothing at all.
        val reputation = CallReputation(storeWith(Triple("+919876543210", 1_000L, otpHit)))

        assertFalse(reputation.isReady)
        assertNull(reputation.lookup("9876543210"))
    }

    @Test
    fun `a store that refuses to record produces no reputation`() {
        // History switched off. No records, so no reputation — stated as a test
        // because it is a promise the settings screen makes to the user.
        val store = FakeStore().apply { recording = false }
        store.record(1_000L, "+919876543210", "en", "Share your OTP", otpHit, "in-service")

        val reputation = CallReputation(store)
        reputation.refresh()

        assertEquals(0, reputation.size)
        assertNull(reputation.lookup("9876543210"))
    }

    @Test
    fun `clearing history clears reputation`() {
        // A "clear history" button that leaves a shadow list of numbers behind
        // would make the settings screen a lie.
        val store = storeWith(Triple("+919876543210", 1_000L, otpHit))
        val reputation = CallReputation(store)
        reputation.refresh()
        assertEquals(1, reputation.size)

        store.clear()
        reputation.refresh()

        assertEquals(0, reputation.size)
        assertNull(reputation.lookup("9876543210"))
        // Still ready: an empty set is a loaded answer of "no", which is a
        // different state from not knowing yet, and the screener treats them
        // the same way only by coincidence. Worth pinning so it stays true.
        assertTrue(reputation.isReady)
    }

    // --- Staleness, found on the emulator ------------------------------------

    @Test
    fun `a set loaded before a message arrives does not answer for it`() {
        // The defect this pins, measured on an emulator before it was fixed: the
        // set is held in memory and was loaded once, so a number that texted the
        // user AFTER the load was reported "not known" when it rang. That is the
        // scam sequence this layer exists for — the message, then the call — and
        // it failed silently, because a caller nobody warns about looks exactly
        // like a caller nobody needed to.
        //
        // Asserted as the behaviour it IS rather than the behaviour we want, so
        // the reason `invalidate` has to be called is written down next to it.
        val store = FakeStore()
        val reputation = CallReputation(store)
        reputation.refresh()

        store.record(1_000L, "+919876543210", "en", "Share your OTP", otpHit, "in-service")

        assertNull(reputation.lookup("9876543210"), "a stale set cannot know this yet")
    }

    @Test
    fun `invalidating makes the next lookup reload`() {
        val store = FakeStore()
        val reputation = CallReputation(store)
        reputation.refresh()
        store.record(1_000L, "+919876543210", "en", "Share your OTP", otpHit, "in-service")

        reputation.invalidate()
        assertFalse(reputation.isReady, "invalidate must make the set ask again")

        reputation.refresh()
        assertNotNull(reputation.lookup("9876543210"))
    }

    // --- The evidence the warning has to carry -------------------------------

    @Test
    fun `the answer carries the scan it came from, so the user can open the trace`() {
        // Constraint 1. A warning the user cannot audit is the thing this
        // product exists not to ship.
        val store = storeWith(Triple("+919876543210", 4_000L, otpHit))
        val reputation = CallReputation(store)
        reputation.refresh()

        val answer = assertNotNull(reputation.lookup("9876543210"))
        assertEquals(4_000L, answer.scannedAtMillis)
        assertEquals(listOf("otp_share"), answer.ruleIds)
        assertNotNull(store.byId(answer.scanId), "the scan id must resolve to a real trace")
    }

    @Test
    fun `the most recent flagged message from a number is the one cited`() {
        val store = storeWith(
            Triple("+919876543210", 1_000L, otpHit),
            Triple("+919876543210", 9_000L, listOf(RuleHitRecord("kyc_expiry", "x", "KYC expired"))),
        )
        val reputation = CallReputation(store)
        reputation.refresh()

        val answer = assertNotNull(reputation.lookup("9876543210"))
        assertEquals(9_000L, answer.scannedAtMillis)
        assertEquals(listOf("kyc_expiry"), answer.ruleIds)
        assertEquals(1, reputation.size, "one number is one entry, however often it wrote")
    }

    @Test
    fun `lookup does not read the store`() {
        // The latency rule for this layer: read an answer, do not compute one.
        // A lookup that touched SQLite would put disk I/O in the window the
        // platform gives us while a phone is ringing.
        val store = storeWith(Triple("+919876543210", 1_000L, otpHit))
        val reputation = CallReputation(store)
        reputation.refresh()

        store.clear()

        assertTrue(
            reputation.lookup("9876543210") != null,
            "lookup answered from the store rather than from memory",
        )
    }
}
