package ai.raksha.rules

import java.util.regex.Pattern
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertTrue

/**
 * Executable notes on where Java's regex engine and Python's `re` disagree.
 *
 * Issue #28 predicted one divergence and prescribed `UNICODE_CHARACTER_CLASS`
 * as the fix. Measuring it showed the prescription is not safe as stated: the
 * flag repairs one divergence and introduces another. These tests pin both
 * directions so the decision in `RuleEngine.kt` is evidence, not opinion, and
 * so a future rule that would make the choice matter fails here first.
 *
 * The Python-side expectations were produced by running the same patterns
 * through CPython's `re`; they are recorded in the assertion messages.
 */
class RegexDialectTest {

    private fun matches(pattern: String, text: String, unicodeClasses: Boolean): Boolean {
        var flags = Pattern.CASE_INSENSITIVE
        if (unicodeClasses) flags = flags or Pattern.UNICODE_CHARACTER_CLASS or Pattern.UNICODE_CASE
        return Pattern.compile(pattern, flags).matcher(text).find()
    }

    // कृपया / शेयर / खाता, as escapes so no encoding step can corrupt them.
    private val kripya = "कृपया"
    private val share = "शेयर"
    private val khata = "खाता"

    @Test
    fun `ASCII-only word class cannot match Indic text - Python can`() {
        // Python: re.search(r"\bOTP\b\s*\w+", "OTP शेयर") -> MATCH
        val pattern = """\bOTP\b\s*\w+"""
        val text = "OTP $share"
        assertFalse(
            matches(pattern, text, unicodeClasses = false),
            "Java's default \\w is ASCII-only, so it cannot match Devanagari. " +
                "Python's \\w is Unicode-aware and DOES match here. This is the " +
                "divergence #28 warned about.",
        )
        assertTrue(
            matches(pattern, text, unicodeClasses = true),
            "UNICODE_CHARACTER_CLASS repairs this direction.",
        )
    }

    @Test
    fun `unicode word class breaks word boundaries around combining marks - Python does not`() {
        // Python: re.search(r"\bखाता\b", "आपका खाता बंद") -> NO MATCH
        //
        // खाता ends in ा (U+093E), a combining mark. Python's \w excludes
        // combining marks, so there is no word boundary after it and the match
        // fails. Java's Unicode \w explicitly INCLUDES them (\p{gc=Mn}), so the
        // boundary exists and it matches — the opposite answer.
        val pattern = """\b$khata\b"""
        val text = "आपका $khata बंद"

        assertFalse(
            matches(pattern, text, unicodeClasses = false),
            "Default flags agree with Python here (no match).",
        )
        assertTrue(
            matches(pattern, text, unicodeClasses = true),
            "With UNICODE_CHARACTER_CLASS, Java matches where Python does NOT. " +
                "Turning the flag on to fix the other case would introduce this one.",
        )
    }

    @Test
    fun `ASCII patterns are unaffected by the flag`() {
        val pattern = """\bshar\w*\b"""
        val text = "please stop sharing this"
        assertEquals(
            matches(pattern, text, unicodeClasses = false),
            matches(pattern, text, unicodeClasses = true),
            "Purely ASCII rules behave identically either way, which is why the " +
                "flag makes no difference to the current English rules.",
        )
    }

    @Test
    fun `no Indic rule uses a word class or boundary`() {
        // This is the guard that makes the flag decision safe. The Hindi and
        // Gujarati rules are literal alternations plus a negated-class gap, so
        // neither \w nor \b is ever evaluated against Indic characters and the
        // two engines cannot disagree.
        //
        // If this fails, someone added \w or \b to a non-English rule. Before
        // changing this test, work out which engine's answer you want, add a
        // corpus case that pins it, and revisit the flag choice in
        // RuleEngine.kt — the trade-off documented there is now live.
        val offenders = RULES
            .filterKeys { it != "en" }
            .flatMap { (language, rules) ->
                rules.filter { Regex("""\\[wb]""").containsMatchIn(it.pattern) }
                    .map { "$language/${it.ruleId}" }
            }
        assertTrue(
            offenders.isEmpty(),
            "Non-English rules now use \\w or \\b: $offenders. See the comment above.",
        )
    }

    @Test
    fun `the gap does not cross sentence punctuation`() {
        // Shared with the Python by construction, and the reason
        // xfail_cross_sentence_kyc is an expected failure rather than a bug.
        assertTrue(offlineRuleHits("Your KYC is expiring today", "en").any { it.ruleId == "kyc_expiry" })
        assertFalse(
            offlineRuleHits("Your KYC is pending. Please update it now.", "en")
                .any { it.ruleId == "kyc_expiry" },
        )
    }
}
