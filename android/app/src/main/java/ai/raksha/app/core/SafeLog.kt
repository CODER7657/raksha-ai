package ai.raksha.app.core

import android.util.Log

/**
 * Logging that cannot be handed a scanned message.
 *
 * `logcat` is readable from bug reports and on rooted devices, and it is the
 * classic way private content escapes an app that promised to keep it local.
 * #29 §2 asks for message text to be structurally un-loggable rather than
 * un-logged by discipline.
 *
 * So this is the only logger the SMS path uses, and its API offers nowhere to
 * put message content: callers pass a rule id, a count or a duration. There is
 * deliberately no `log(text: String)` overload taking free-form content.
 *
 * This is a guard rail, not a wall — someone determined can still call
 * [Log] directly. The detekt rule in #29 §2 is what makes that fail review;
 * `SafeLogTest` pins the intent in the meantime.
 */
object SafeLog {

    private const val TAG = "RakshaScan"

    /** A scan happened. Rule ids are safe: they are a closed vocabulary. */
    fun scanCompleted(ruleIds: List<String>, durationMillis: Long) {
        Log.i(TAG, "scan complete: ${ruleIds.size} rule(s) fired ${ruleIds.sorted()} in ${durationMillis}ms")
    }

    /** A message was skipped as a duplicate. No identifying detail. */
    fun duplicateSkipped() {
        Log.d(TAG, "duplicate message skipped")
    }

    /** Multipart reassembly, reported as a count only. */
    fun partsAssembled(partCount: Int) {
        Log.d(TAG, "assembled $partCount SMS part(s)")
    }

    /**
     * Something failed. Takes a [Throwable], not a message — an exception's own
     * text can carry content if the thrower was careless, so only the class
     * name is recorded.
     */
    fun failure(stage: String, error: Throwable) {
        Log.w(TAG, "failure during $stage: ${error.javaClass.simpleName}")
    }
}
