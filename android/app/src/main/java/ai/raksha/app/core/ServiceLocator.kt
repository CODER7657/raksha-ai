package ai.raksha.app.core

import android.content.Context
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

    fun preferences(context: Context): ScanPreferences = ScanPreferences(context)

    /** Lets a test supply a fake, and undo it afterwards. */
    fun resetForTest(replacement: ScanStore? = null) {
        synchronized(this) { store = replacement }
    }
}
