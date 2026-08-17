package ai.raksha.app.core

import java.lang.reflect.Modifier
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

/**
 * `SafeLog` is a privacy boundary, not a convenience wrapper. Its guarantee is
 * that there is nowhere in its API to put message text, so a careless call site
 * cannot leak one into logcat — which is readable from bug reports and on
 * rooted devices (#29 §2).
 *
 * **What this test can and cannot do.** Reflection cannot tell a `stage: String`
 * naming a code path from a `body: String` carrying someone's SMS; both are
 * `java.lang.String`. So it does not try. Instead it pins the *surface*: the
 * exact set of public methods and their shapes. Adding a method, or widening an
 * existing one, fails here — which forces the question "can this be handed
 * message text?" to be answered by a human at review time rather than assumed.
 *
 * The detekt rule in #29 §2 is what will eventually check the call sites. Until
 * then, this is the tripwire.
 */
class SafeLogContractTest {

    private val methods = SafeLog::class.java.declaredMethods
        .filter { Modifier.isPublic(it.modifiers) && !it.isSynthetic }

    @Test
    fun `the logging surface is exactly what has been reviewed`() {
        // Every String parameter below is a fixed literal at its call site — a
        // stage name or a suppression reason, never anything derived from a
        // message. If this fails, a method was added or changed: check the new
        // call sites cannot pass message text, then update this list.
        val expected = setOf(
            "scanCompleted",       // List<String> rule ids, Long duration
            "duplicateSkipped",    // no parameters
            "partsAssembled",      // Int count
            "warningSuppressed",   // List<String> rule ids, String reason literal
            "failure",             // String stage literal, Throwable
            "callScreened",        // ScreeningOutcome, Long - reviewed in #116 §4, see below
        )
        assertEquals(
            expected,
            methods.map { it.name }.toSet(),
            "SafeLog's public surface changed. Each String parameter must be a " +
                "fixed literal, never message-derived — confirm that, then update " +
                "this test.",
        )
    }

    @Test
    fun `no method takes a CharSequence that could be a whole message`() {
        // CharSequence is the shape message bodies actually arrive in
        // (SmsMessage.displayMessageBody). String parameters are allowed above
        // because each is a reviewed literal; a bare CharSequence never is.
        val offenders = methods.filter { method ->
            method.parameterTypes.any {
                CharSequence::class.java.isAssignableFrom(it) && it != String::class.java
            }
        }.map { it.name }
        assertTrue(offenders.isEmpty(), "CharSequence parameters found: $offenders")
    }

    @Test
    fun `failure takes a Throwable rather than its message`() {
        val failure = methods.single { it.name == "failure" }
        assertTrue(
            failure.parameterTypes.any { Throwable::class.java.isAssignableFrom(it) },
            "failure() must take the Throwable so only its class name is logged — " +
                "an exception's own message can echo the input that caused it",
        )
    }

    @Test
    fun `callScreened cannot be handed a phone number`() {
        // The review this test forced, recorded as an assertion rather than a
        // promise. A phone number is user data in the way a message body is, and
        // logcat is the same open door for both — so the call-screening path got
        // a method with nowhere to put one. No String parameter at all, which is
        // stricter than the rest of this surface and is the point: every other
        // String here is a reviewed literal, and a caller identity never could
        // be one.
        val method = methods.single { it.name == "callScreened" }
        assertTrue(
            method.parameterTypes.none { CharSequence::class.java.isAssignableFrom(it) },
            "callScreened must take no text at all, or a number can reach logcat",
        )
    }

    @Test
    fun `warningSuppressed reports rule ids, not text`() {
        val method = methods.single { it.name == "warningSuppressed" }
        assertTrue(
            method.parameterTypes.any { List::class.java.isAssignableFrom(it) },
            "rule ids should arrive as a list, so the closed vocabulary is obvious",
        )
    }
}
