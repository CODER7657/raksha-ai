package ai.raksha.app.data

/**
 * A sender this phone's own rules fired on, and the scan that proves it.
 *
 * Deliberately not a [ScanRecord]: layer 1 needs to build its set at the moment
 * a call screening service is cold-starting, and reading two hundred full
 * records — message bodies, matched text and all — to extract a column of
 * senders would put the whole history through memory to answer a question about
 * phone numbers. This is the narrow projection that question actually needs.
 *
 * It carries [scanId] because a warning the user cannot audit is the thing this
 * product exists not to ship. The number is flagged *because of a specific
 * message*, and the user can open it.
 */
data class FlaggedSender(
    /** As the platform reported it. Not yet normalised — see `NumberIdentity`. */
    val sender: String,
    /** The scan that flagged it, resolvable through [ScanStore.byId]. */
    val scanId: Long,
    val scannedAtMillis: Long,
    /** Which rules fired on that message, for naming the reason to the user. */
    val ruleIds: List<String>,
)
