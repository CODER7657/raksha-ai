package ai.raksha.app.core

/**
 * What happened when a call was screened, in a vocabulary that cannot contain a
 * phone number.
 *
 * An enum rather than a string because [SafeLog] is a privacy boundary: a
 * `String` parameter is only safe while every call site passes a literal, and
 * "describe what happened to this caller" is exactly the parameter someone would
 * eventually pass the caller's number to. There is no way to put one here.
 *
 * The distinction between [CALLER_UNIDENTIFIED] and [NOT_KNOWN] is not
 * cosmetic. Both end in silence, so from the outside they are the same event —
 * and they mean opposite things. One is the set answering "no"; the other is the
 * set never having been asked, because there was no number to ask about. A run
 * where every call is unidentified looks exactly like a run where the user is
 * simply not being scammed, which is the shape of silent failure #93 and #102
 * were both about.
 */
enum class ScreeningOutcome {

    /** No dialable number on the call — withheld, or a handle we cannot read. */
    CALLER_UNIDENTIFIED,

    /** Identified, and this phone has nothing against it. The common case. */
    NOT_KNOWN,

    /** Identified, and it has sent this phone a message that was flagged. */
    KNOWN,
}
