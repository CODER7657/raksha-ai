package ai.raksha.app.sms

import ai.raksha.rules.offlineRuleHits
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertTrue

class SmsAssemblyTest {

    // --- Multipart reassembly ------------------------------------------------

    @Test
    fun `parts are joined without a separator`() {
        // A 160-character split can land mid-word. Inserting a space would
        // corrupt the word and could break a rule that the whole text matches.
        assertEquals("sharethe OTP", assembleMultipart(listOf("share", "the OTP")))
    }

    @Test
    fun `a rule spanning the split still fires once reassembled`() {
        // The regression this exists to prevent: scoring parts individually is
        // silent — nothing errors, the message just looks clean.
        val first = "Dear customer, please sha"
        val second = "re your OTP to continue"

        assertFalse(
            offlineRuleHits(first, "en").any { it.ruleId == "otp_share" },
            "the first part alone should not match — that is why reassembly matters",
        )
        assertFalse(offlineRuleHits(second, "en").any { it.ruleId == "otp_share" })

        val whole = assembleMultipart(listOf(first, second))
        assertTrue(
            offlineRuleHits(whole, "en").any { it.ruleId == "otp_share" },
            "reassembled message must fire otp_share",
        )
    }

    @Test
    fun `empty and single part lists are handled`() {
        assertEquals("", assembleMultipart(emptyList()))
        assertEquals("only", assembleMultipart(listOf("only")))
    }

    // --- Deduplication -------------------------------------------------------

    @Test
    fun `the same message offered twice is only accepted once`() {
        val filter = RecentMessageFilter()
        val now = 1_700_000_000_000L
        assertTrue(filter.offer("+911234567890", "Share your OTP", now))
        assertFalse(filter.offer("+911234567890", "Share your OTP", now))
    }

    @Test
    fun `the same text from a different sender is a different message`() {
        val filter = RecentMessageFilter()
        val now = 1_700_000_000_000L
        assertTrue(filter.offer("+911111111111", "Share your OTP", now))
        assertTrue(filter.offer("+912222222222", "Share your OTP", now))
    }

    @Test
    fun `the same text much later warns again`() {
        // A sender legitimately repeating themselves is a new event, not a
        // redelivery — the user should be warned again.
        val filter = RecentMessageFilter()
        val now = 1_700_000_000_000L
        assertTrue(filter.offer("+911234567890", "Share your OTP", now))
        assertTrue(
            filter.offer(
                "+911234567890",
                "Share your OTP",
                now + RecentMessageFilter.DEDUP_WINDOW_MILLIS * 3,
            ),
        )
    }

    @Test
    fun `the filter is bounded`() {
        val filter = RecentMessageFilter(capacity = 10)
        repeat(100) { index -> filter.offer("+9100000$index", "message $index", index.toLong()) }
        assertTrue(filter.size <= 10, "filter grew to ${filter.size}, past its capacity")
    }

    @Test
    fun `fingerprints do not contain the message text`() {
        // The filter is long-lived and reachable from a heap dump. It must hold
        // digests, not content — ARCHITECTURE §02.
        val filter = RecentMessageFilter()
        val body = "Share your OTP 998877 immediately"
        val fingerprint = filter.fingerprint("+911234567890", body, 1_700_000_000_000L)

        assertFalse(fingerprint.contains("998877"))
        assertFalse(fingerprint.contains("OTP", ignoreCase = true))
        assertFalse(fingerprint.contains("1234567890"))
        assertEquals(64, fingerprint.length, "expected a hex SHA-256 digest")
    }
}
