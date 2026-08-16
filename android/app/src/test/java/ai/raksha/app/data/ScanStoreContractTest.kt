package ai.raksha.app.data

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNotNull
import kotlin.test.assertNull
import kotlin.test.assertTrue

/**
 * The behaviour [ScanStore] promises, tested against an in-memory
 * implementation of the same interface.
 *
 * **What this does and does not prove.** `SqliteScanStore` needs a real Android
 * `Context` and the platform's SQLite, neither of which exists in a JVM unit
 * test, and the module has no Robolectric. So these cases pin the *contract* —
 * ordering, the cap, clearing, that a hit belongs to its scan — and the SQL
 * implementation is exercised on a device instead, which is where its
 * transaction and cascade behaviour actually lives.
 *
 * Saying so matters: a green run here is not evidence the SQL is right. It is
 * evidence that anything implementing this interface, including the Room
 * version that replaces it when KSP supports Kotlin 2.4, has to behave the same
 * way.
 */
class ScanStoreContractTest {

    /** The same contract, backed by a list. Also what a fake in a UI test uses. */
    private class InMemoryScanStore : ScanStore {
        private val records = mutableListOf<ScanRecord>()
        private var nextId = 1L

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
        ): ScanRecord {
            val stored = ScanRecord(
                nextId++, scannedAtMillis, sender, language, body, hits, ruleReviewStatus,
            )
            records += stored
            // Same trim the SQL does, in the same place.
            if (records.size > ScanStore.MAX_RECORDS) {
                val keep = records.sortedByDescending { it.scannedAtMillis }
                    .take(ScanStore.MAX_RECORDS)
                records.retainAll(keep)
            }
            return stored
        }

        override fun clear() = records.clear()
        override fun count() = records.size
    }

    private fun store() = InMemoryScanStore()

    /**
     * `record` is nullable because a real store returns null when history is
     * switched off. These cases are all about a store that is recording, so the
     * helper asserts that rather than making every call site carry `!!`.
     */
    private fun ScanStore.add(at: Long, hits: List<RuleHitRecord> = emptyList()): ScanRecord =
        requireNotNull(record(at, "+911234567890", "en", "Share your OTP now", hits, "in-service")) {
            "the in-memory store should always record"
        }

    @Test
    fun `newest first`() {
        val store = store()
        store.add(at = 1_000)
        store.add(at = 3_000)
        store.add(at = 2_000)

        assertEquals(listOf(3_000L, 2_000L, 1_000L), store.recent().map { it.scannedAtMillis })
    }

    @Test
    fun `a scan with no hits is still recorded`() {
        // The question a user asks when they were NOT warned is "did it even
        // look at that one?". A history of only the flagged messages cannot
        // answer it.
        val store = store()
        val stored = store.add(at = 1_000, hits = emptyList())
        assertNotNull(stored)
        assertEquals(1, store.count())
        assertTrue(!stored.isFlagged)
    }

    @Test
    fun `hits belong to their own scan`() {
        val store = store()
        val clean = store.add(at = 1_000)
        val flagged = store.add(
            at = 2_000,
            hits = listOf(RuleHitRecord("otp_share", "\\bOTP\\b", "share your OTP")),
        )

        assertEquals(emptyList(), store.byId(clean.id)?.hits)
        assertEquals(listOf("otp_share"), store.byId(flagged.id)?.hits?.map { it.ruleId })
    }

    @Test
    fun `history is capped`() {
        val store = store()
        repeat(ScanStore.MAX_RECORDS + 25) { index -> store.add(at = index.toLong()) }

        assertEquals(ScanStore.MAX_RECORDS, store.count())
        // The oldest go, not the newest: a cap that dropped recent scans would
        // be worse than no history at all.
        assertEquals(
            (ScanStore.MAX_RECORDS + 24).toLong(),
            store.recent().first().scannedAtMillis,
        )
    }

    @Test
    fun `clear removes everything`() {
        val store = store()
        repeat(5) { store.add(at = it.toLong()) }
        store.clear()

        assertEquals(0, store.count())
        assertEquals(emptyList(), store.recent())
    }

    @Test
    fun `an unknown id is null rather than an empty record`() {
        // A blank trace screen and "this is gone" are different statements, and
        // the UI can only tell them apart if the store does.
        assertNull(store().byId(404L))
    }

    @Test
    fun `the review status is stored with the scan, not looked up later`() {
        // A scan made while a language was unreviewed stays honest about that
        // after somebody reviews it.
        val store = store()
        val stored = store.record(
            1_000, "+91", "ta", "body", emptyList(), "unreviewed",
        )
        assertEquals("unreviewed", store.byId(stored!!.id)?.ruleReviewStatus)
    }
}
