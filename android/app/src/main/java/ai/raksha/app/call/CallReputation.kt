package ai.raksha.app.call

import ai.raksha.app.data.FlaggedSender
import ai.raksha.app.data.ScanStore

/**
 * Layer 1: what this phone knows about a number, held in memory.
 *
 * **Where the reputation comes from.** Not a bought or bundled list — the
 * phone's own memory of layer 2. A number is in this set because an SMS it sent
 * to *this handset* was flagged by the on-device rules. Three things follow, and
 * they are the reason #116 §4's "bundled set updated per release" is not what
 * got built:
 *
 *  - **Every entry has a trace the user can open.** Constraint 1 is met by
 *    construction. A bought list can only ever say "someone says this is bad".
 *  - **Nothing goes stale**, because nothing is shipped. The staleness question
 *    §4 raises as a reason to consider syncing does not arise, and #83's bundle
 *    signing — the poisoning path signing exists to prevent — never opens.
 *  - **It is small and specific.** It holds numbers that have already targeted
 *    this person, not numbers that have targeted anyone.
 *
 * The honest cost: it is empty on a new install and stays empty for a user who
 * is never sent a scam SMS. Layer 1 protects the second contact from a number,
 * not the first. That is a real limitation and it is why this is the cheapest
 * signal in ARCHITECTURE §01's table rather than the strongest.
 *
 * **Why the whole set lives in memory.** `onScreenCall` runs while the phone is
 * ringing, inside a window the platform does not extend. §4's rule is to read an
 * answer rather than compute one, so [lookup] is a hash lookup over a set built
 * once at [refresh] and touches no disk at all.
 *
 * Not thread-confined: [refresh] runs on a background thread and [lookup] on
 * whichever thread the telecom stack calls us on. The set is swapped atomically
 * rather than mutated, so a lookup mid-refresh sees the old answer or the new
 * one, never a half-built one.
 */
class CallReputation(private val store: ScanStore) {

    @Volatile
    private var known: Map<String, FlaggedSender>? = null

    /**
     * True once a set has been built. Distinct from the set being empty:
     * "nothing known about this number" and "nothing known yet" are different
     * facts, and only one of them is worth retrying.
     */
    val isReady: Boolean get() = known != null

    /** How many numbers are known. Empty is the normal state on a new install. */
    val size: Int get() = known?.size ?: 0

    /**
     * Rebuilds the set from the store. Disk I/O — never call this from
     * `onScreenCall`.
     *
     * Because it reads the store every time, clearing history and refreshing
     * empties this. That is the mechanism behind the promise the settings screen
     * makes: there is no separate list of numbers to survive a clear.
     */
    fun refresh() {
        val built = LinkedHashMap<String, FlaggedSender>()
        // Newest first from the store, and the first write for a key wins, so a
        // number that wrote twice is cited by its most recent flagged message.
        for (flagged in store.flaggedSenders()) {
            val key = NumberIdentity.keyOf(flagged.sender) ?: continue
            built.putIfAbsent(key, flagged)
        }
        known = built
    }

    /**
     * Marks the set as needing rebuilding, without touching disk.
     *
     * **Why this exists, and it was not in the design.** The set is loaded once
     * and held in memory so a ringing phone never waits on I/O. On the first
     * emulator run that meant a number which sent a scam SMS *after* the set was
     * loaded came back `NOT_KNOWN` when it rang — and message-then-call is the
     * sequence this whole layer is for. It failed the way this project keeps
     * finding failures: silently, because a caller nobody warns about is
     * indistinguishable from a caller nobody needed to warn about.
     *
     * Called from the SMS path when a scan is recorded. Deliberately free of
     * I/O, so it costs the receiver nothing: the reload is paid for later, by
     * the screening path, which has already released the call by then.
     */
    fun invalidate() {
        known = null
    }

    /**
     * What this phone knows about [rawNumber], or null for "no warning".
     *
     * Null covers three different situations on purpose, because the screener's
     * response to all three is identical — let the call through and say nothing:
     * the number is not known, the number could not be identified at all, or the
     * set is not loaded yet. Only the last is a failure, and failing that way
     * costs an unwarned call rather than a missed one.
     */
    fun lookup(rawNumber: String?): FlaggedSender? {
        val loaded = known ?: return null
        val key = NumberIdentity.keyOf(rawNumber) ?: return null
        return loaded[key]
    }
}
