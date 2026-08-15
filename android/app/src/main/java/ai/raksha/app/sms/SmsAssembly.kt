package ai.raksha.app.sms

import java.security.MessageDigest

/**
 * The parts of SMS handling that are pure logic, kept free of Android types so
 * they can be tested on the JVM in milliseconds instead of on an emulator.
 *
 * Two correctness problems from #29 §5 live here:
 *
 *  - **Multipart reassembly.** A long scam SMS arrives as several parts. Scoring
 *    each part alone misses any rule whose halves straddle the split — a silent
 *    recall hole, because nothing errors and the message simply looks clean.
 *  - **Deduplication.** The platform can redeliver a broadcast. Without a guard
 *    the user gets the same warning twice, which trains them to dismiss it.
 */

/**
 * Joins the parts of a multipart SMS back into the single message the sender
 * wrote.
 *
 * Parts arrive in order from `getMessagesFromIntent`, and the split can fall
 * mid-word, so the parts are concatenated with no separator — inserting a space
 * would corrupt a word and could break a pattern that the unsplit text matches.
 */
fun assembleMultipart(parts: List<String>): String = parts.joinToString(separator = "")

/**
 * Remembers which messages have already been scored, **by digest only**.
 *
 * The raw text is never retained: this object is reachable from a long-lived
 * receiver, and holding message content in memory — where it can reach a heap
 * dump or a bug report — would undercut the privacy claim in ARCHITECTURE §02.
 * A digest is enough to answer "have I seen this exact message".
 *
 * Bounded and insertion-ordered: the oldest fingerprint is evicted once
 * [capacity] is reached, so a device that receives thousands of messages does
 * not grow this without limit.
 */
class RecentMessageFilter(private val capacity: Int = DEFAULT_CAPACITY) {

    private val seen = LinkedHashSet<String>()

    /**
     * Returns true the first time a message is offered, false for a redelivery.
     *
     * [timestampMillis] is bucketed rather than used exactly: a redelivered
     * broadcast carries the same timestamp, while a genuinely repeated message
     * (a sender legitimately sending the same text twice) arrives later and
     * should warn again.
     */
    fun offer(sender: String, body: String, timestampMillis: Long): Boolean {
        val fingerprint = fingerprint(sender, body, timestampMillis)
        if (!seen.add(fingerprint)) return false
        while (seen.size > capacity) {
            val oldest = seen.first()
            seen.remove(oldest)
        }
        return true
    }

    /** Exposed for tests; never logged, never persisted. */
    internal fun fingerprint(sender: String, body: String, timestampMillis: Long): String {
        val bucket = timestampMillis / DEDUP_WINDOW_MILLIS
        val digest = MessageDigest.getInstance("SHA-256")
            .digest("$sender\u0000$body\u0000$bucket".toByteArray(Charsets.UTF_8))
        return digest.joinToString("") { "%02x".format(it) }
    }

    val size: Int get() = seen.size

    companion object {
        /**
         * Roughly a day of heavy SMS traffic. Small enough to be free, large
         * enough that a redelivery after a reboot storm is still caught.
         */
        const val DEFAULT_CAPACITY = 200

        /**
         * Two messages with identical sender and text inside this window are
         * treated as the same message. Wide enough to absorb a redelivery,
         * narrow enough that a sender repeating themselves an hour later still
         * gets scored.
         */
        const val DEDUP_WINDOW_MILLIS = 60_000L
    }
}
