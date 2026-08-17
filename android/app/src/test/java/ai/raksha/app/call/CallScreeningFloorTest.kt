package ai.raksha.app.call

import android.os.Build
import kotlin.test.Test
import kotlin.test.assertEquals

/**
 * The API floor for call screening, pinned to the measurement that set it.
 *
 * **Why a test and not a comment.** Until #140 the floor was protected by prose
 * alone — nothing in this tree referenced `isSupported` or `VERSION_CODES`, so
 * changing `R` to `Q` produced a green suite and would have been discovered on a
 * user's phone. A comment explains a decision to somebody who goes looking; a
 * failing test explains it to the person changing the value, which is the only
 * moment the explanation is worth anything.
 *
 * Needs no device and no Robolectric: `Build.VERSION_CODES.R` is a compile-time
 * constant, so this is a plain JVM assertion.
 *
 * Same shape as `SharedStringCoverageTest` reading `strings.xml` — source-level
 * pinning of a decision that nothing else in the build would notice changing.
 */
class CallScreeningFloorTest {

    @Test
    fun `the call screening floor is API 30, and 29 is a measured no`() {
        assertEquals(
            30,
            CallScreeningRole.MIN_SDK_FOR_SCREENING,
            """
            The call-screening floor changed. Before lowering it, read this.

            API 29 was measured (#140) and it is NOT a free widening. The role
            can be held there and screening works - a known number screens in
            7ms - which is exactly why it looks safe. The problem is contacts:

              API 36, caller is a contact   platform does not bind us   no warning
              API 29, caller is a contact   platform binds us           WARNED

            The contact exclusion API 36 enforces is not present at 29, and
            Call.Details.getContactDisplayName arrives at 30, so there is nothing
            to catch it. Lowering the floor ships a warning about the people the
            user deliberately saved, to the population least able to absorb a
            false positive - the benign-half failure that turns a feature off.

            Raising it is a different question and needs its own reason: it takes
            the layer away from handsets that currently have it.
            """.trimIndent(),
        )
    }

    @Test
    fun `the floor is expressed as a platform constant, not a bare number`() {
        // 30 and VERSION_CODES.R must stay the same thing. If someone replaces
        // the constant with a literal the assertion above still passes, and the
        // next reader loses the only clue about which platform release the floor
        // is tied to.
        assertEquals(Build.VERSION_CODES.R, CallScreeningRole.MIN_SDK_FOR_SCREENING)
    }
}
