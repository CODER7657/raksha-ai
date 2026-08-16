package ai.raksha.app.call

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNotEquals
import kotlin.test.assertNotNull
import kotlin.test.assertNull

/**
 * The half of layer 1 that decides what is even a number.
 *
 * Most of these assert a *refusal*. That is the point: the reputation set is
 * built from SMS senders, and in India most SMS senders are not phone numbers
 * at all. Letting `VM-HDFCBK` into a set that is later compared against a
 * ringing caller is how a set quietly fills with entries that can never match.
 */
class NumberIdentityTest {

    // --- What counts as a number --------------------------------------------

    @Test
    fun `a plain ten digit number is accepted`() {
        assertEquals("9876543210", NumberIdentity.keyOf("9876543210"))
    }

    @Test
    fun `formatting is not part of the identity`() {
        // The same number written five ways by five parts of the platform.
        val expected = NumberIdentity.keyOf("9876543210")
        assertNotNull(expected)
        for (written in listOf(
            "+91 98765 43210",
            "098765-43210",
            "(+91) 9876543210",
            "+919876543210",
            "91 9876543210",
        )) {
            assertEquals(expected, NumberIdentity.keyOf(written), "failed on: $written")
        }
    }

    @Test
    fun `a tel URI from the telecom stack is accepted`() {
        // Call.Details.getHandle() is a tel: URI, not a bare string.
        assertEquals(
            NumberIdentity.keyOf("9876543210"),
            NumberIdentity.keyOf("tel:+919876543210"),
        )
    }

    // --- What is refused -----------------------------------------------------

    @Test
    fun `an alphanumeric sender id is refused`() {
        // The common case, and the one that matters. These are not dialable, so
        // a caller can never match one — but they would still occupy the set.
        for (senderId in listOf("VM-HDFCBK", "AD-SBIINB", "TX-ICICIB", "JD-PAYTM", "HDFCBK")) {
            assertNull(NumberIdentity.keyOf(senderId), "should have refused: $senderId")
        }
    }

    @Test
    fun `text carrying both letters and a full number is refused`() {
        // This is the case that justifies the letter check existing at all.
        //
        // Mutation-tested: disabling the letter check leaves every other refusal
        // above still passing, because a pure sender ID like VM-HDFCBK has no
        // digits and is already refused for being too short. Only a string with
        // letters AND enough digits can tell the two guards apart, and without
        // this test the letter check was untested code that looked covered.
        for (mixed in listOf("HDFCBK-9876543210", "Unknown 9876543210", "SBI 09876543210")) {
            assertNull(NumberIdentity.keyOf(mixed), "should have refused: $mixed")
        }
    }

    @Test
    fun `a short code is refused`() {
        // 121 is a carrier line, 1930 is India's cybercrime helpline. Neither is
        // a caller identity worth remembering, and 1930 in particular must never
        // end up warned about.
        for (shortCode in listOf("121", "1930", "555", "199")) {
            assertNull(NumberIdentity.keyOf(shortCode), "should have refused: $shortCode")
        }
    }

    @Test
    fun `a withheld or absent caller is refused`() {
        // A withheld number is an inability to identify, and #123 settled that
        // inability-to-verify is a caveat and never a signal. It must not become
        // an entry, and it must not become a warning.
        for (absent in listOf("", "   ", "unknown", "Unknown", "-", "+", "tel:")) {
            assertNull(NumberIdentity.keyOf(absent), "should have refused: $absent")
        }
    }

    // --- The comparison rule itself -----------------------------------------

    @Test
    fun `the same subscriber written nationally and internationally is one identity`() {
        // This is the whole reason the key is the last ten digits rather than a
        // region-prefixed E.164 string. An SMS sender arrives national, a caller
        // arrives international, and assuming +91 to reconcile them would be
        // wrong for a user holding a foreign SIM.
        assertEquals(NumberIdentity.keyOf("09876543210"), NumberIdentity.keyOf("+919876543210"))
    }

    @Test
    fun `two different subscribers are not one identity`() {
        assertNotEquals(NumberIdentity.keyOf("9876543210"), NumberIdentity.keyOf("9876543211"))
    }

    @Test
    fun `a number long enough to dial but shorter than ten digits is kept whole`() {
        // Landline and international formats vary; truncating a short number to
        // ten digits would pad nothing and match nothing.
        assertEquals("2226543210", NumberIdentity.keyOf("+91 22 2654 3210"))
        assertEquals("7654321", NumberIdentity.keyOf("7654321"))
    }
}
