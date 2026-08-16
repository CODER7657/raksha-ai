package ai.raksha.app.data

/**
 * One message this phone scanned, and what it concluded.
 *
 * This is the on-device half of the verdict trace described in
 * `testdata/trace_schema.json`. The phone has no network and no LLM, so it can
 * only ever fill the offline part: which rules fired, on what text, and how
 * much the rules for that language are worth. Everything the schema calls
 * `retrieved_patterns`, `model` or `audit` belongs to the server and is absent
 * here rather than faked.
 *
 * **Why this is stored at all.** Constraint 1 of the project is that a user can
 * always see their own data and their own trace. Until now the phone scanned,
 * notified, and forgot — so "why did it flag that?" had no answer an hour
 * later, while the website had the full trace. That was a promise made and not
 * kept, and for the users this is built for the phone is the only surface they
 * have.
 */
data class ScanRecord(
    val id: Long,
    /** Wall-clock time the message was scored, for display only. */
    val scannedAtMillis: Long,
    /** Sender as the platform reported it, or empty when unknown. */
    val sender: String,
    /** Language the message was scored in — the rules used depend on it. */
    val language: String,
    /** The message. Never leaves the device; see [ScanStore] for the terms. */
    val body: String,
    /** Which rules fired, in engine order. Empty means the message was clean. */
    val hits: List<RuleHitRecord>,
    /**
     * How much the rules for [language] are worth: `in-service`, `inherited`
     * or `unreviewed`.
     *
     * Kept per record rather than looked up at render time because it is a
     * property of the scan, not of the app today. A scan made while a language
     * was unreviewed stays honest about that after somebody reviews it.
     */
    val ruleReviewStatus: String,
) {
    val isFlagged: Boolean get() = hits.isNotEmpty()
}

/**
 * One rule that fired, mirroring `offline_rules_fired` in the trace schema.
 *
 * `pattern` is stored and deliberately never rendered — the UI shows the
 * localised rule name and the matched text. A raw regex in front of a user is
 * the thing #29 §7 rules out, and #37 built the label mechanism to prevent.
 * It is kept because support comparing a phone's decision against the server's
 * needs the same three fields the schema names.
 */
data class RuleHitRecord(
    val ruleId: String,
    val pattern: String,
    val matchedText: String,
)
