package ai.raksha.app.core

import android.content.Context
import ai.raksha.app.call.CallReputation
import ai.raksha.app.data.ScanStore
import ai.raksha.app.data.SqliteScanStore

/**
 * Dependency wiring, by hand.
 *
 * **#116 §3 asks for a deliberate choice between manual and Hilt, so: manual.**
 *
 * The app has two dependencies worth injecting — a [ScanStore] and a
 * [ScanPreferences] — and four screens that need them. Hilt would add an
 * annotation processor to a module that currently has none, and there is no
 * KSP release built for Kotlin 2.4.x (the newest is 2.3.11, against 2.3.20), so
 * it would mean either KAPT or a Kotlin downgrade. That is the same trade
 * `ScanStore` documents for Room, and the same answer: not worth it for two
 * objects.
 *
 * The honest cost of this choice is that it is a global, and a test cannot get
 * a fresh one per case without [resetForTest]. That is acceptable while the
 * graph is this small and stops being acceptable somewhere around the point a
 * second store or a real network layer appears — at which point Hilt is the
 * right answer and this file is the seam to replace.
 *
 * Initialised from [MainActivity] and from the SMS receiver, both of which can
 * be the first thing the process runs.
 */
object ServiceLocator {

    @Volatile
    private var store: ScanStore? = null

    /**
     * The scan store, created on first use.
     *
     * Double-checked rather than `by lazy` because the first caller may be the
     * SMS receiver's executor while the user is opening the app, and a lazy
     * initialiser would block whichever arrived second on the other's disk I/O.
     */
    fun scanStore(context: Context): ScanStore {
        store?.let { return it }
        return synchronized(this) {
            store ?: SqliteScanStore(context.applicationContext).also { store = it }
        }
    }

    @Volatile
    private var reputation: CallReputation? = null

    /**
     * Layer 1's set, shared between the screening service and the UI that
     * reports how much is in it.
     *
     * One instance per process rather than one per caller, because it holds the
     * loaded set: a screening service constructing its own would re-read the
     * store on every call. Built over the same [ScanStore] as everything else,
     * which is what makes clearing history clear reputation.
     */
    fun callReputation(context: Context): CallReputation {
        reputation?.let { return it }
        return synchronized(this) {
            reputation ?: CallReputation(scanStore(context)).also { reputation = it }
        }
    }

    fun preferences(context: Context): ScanPreferences = ScanPreferences(context)

    /** Lets a test supply a fake, and undo it afterwards. */
    fun resetForTest(replacement: ScanStore? = null) {
        synchronized(this) {
            store = replacement
            // Dropped with the store it was built over, or the next test reads a
            // reputation set belonging to the previous one's fake.
            reputation = null
        }
    }
}
