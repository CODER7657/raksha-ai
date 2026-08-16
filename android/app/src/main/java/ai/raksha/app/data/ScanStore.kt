package ai.raksha.app.data

/**
 * Where scan history lives. The seam between the UI and persistence.
 *
 * **On Room.** #116 §3 asks for Room, and it is the right answer as soon as it
 * is available: compile-checked queries beat hand-written SQL. It is not
 * available on this toolchain today. Room needs an annotation processor, KSP
 * has no release built for Kotlin 2.4.x — the newest is 2.3.11, built against
 * Kotlin 2.3.20 — and the Kotlin version here comes from AGP 9's built-in
 * compiler. Adding Room would mean downgrading the Kotlin toolchain to acquire
 * a library, which is a worse trade than writing forty lines of SQL.
 *
 * So this interface exists, [SqliteScanStore] implements it against the
 * platform's own SQLite, and swapping in Room later is a change to one class
 * with the UI untouched. That is the value the seam was asked for.
 *
 * **The terms this storage is held to**, from #29 §2 and constraint 1:
 *
 *  - It never leaves the device. Nothing in this app can reach the network —
 *    there is no `INTERNET` permission — so "on the phone" is enforced by the
 *    platform rather than promised by us.
 *  - `allowBackup="false"` in the manifest, so it never rides out to a cloud
 *    backup.
 *  - Capped at [MAX_RECORDS]. An unbounded log of somebody's messages is a
 *    liability that grows on its own.
 *  - Clearable from inside the app in one action, and gone on uninstall.
 *  - Encrypted at rest by the platform: app-private storage sits under
 *    file-based encryption tied to the user's credential. There is no
 *    additional application-level encryption, which is worth stating plainly
 *    rather than implying more than is there.
 */
interface ScanStore {

    /** Newest first. */
    fun recent(limit: Int = MAX_RECORDS): List<ScanRecord>

    fun byId(id: Long): ScanRecord?

    /** Returns the stored record, or null when history is switched off. */
    fun record(
        scannedAtMillis: Long,
        sender: String,
        language: String,
        body: String,
        hits: List<RuleHitRecord>,
        ruleReviewStatus: String,
    ): ScanRecord?

    /**
     * Every sender whose message this phone flagged, newest scan first.
     *
     * This is what layer 1 builds its reputation set from, and the reason it is
     * a query rather than a filter over [recent] is latency: it runs while a
     * call screening service is cold-starting, and it must not pull two hundred
     * message bodies through memory to answer a question about phone numbers.
     *
     * Senders are returned raw. Deciding which of them are even dialable belongs
     * to `NumberIdentity`, not to SQL.
     */
    fun flaggedSenders(): List<FlaggedSender>

    /** Everything, irreversibly. */
    fun clear()

    fun count(): Int

    companion object {
        /**
         * Roughly a month of a heavily-targeted phone. Large enough that "why
         * did it flag that?" has an answer weeks later, small enough that the
         * file stays trivial and an old message does not linger for years
         * because nobody thought about it.
         */
        const val MAX_RECORDS = 200
    }
}
