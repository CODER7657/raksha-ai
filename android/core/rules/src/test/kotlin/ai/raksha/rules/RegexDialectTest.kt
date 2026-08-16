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
    fun `the strict gap does not cross sentence punctuation`() {
        // GAP is load-bearing, and this is the case it carries. The OTP and the
        // word "share" sit in different sentences, so a gap that could cross the
        // boundary would fire otp_share on the single most common legitimate
        // bank SMS there is — we would be warning about the message that tells
        // the user not to be scammed.
        //
        // Measured against CPython's re on the same two strings:
        //   "Please share your OTP now"                          -> ['otp_share']
        //   "OTP for your login is 449281. Never share it ..."    -> []
        //
        // en-benign-otp-warning-001 pins the second string in the shared corpus
        // too. This test is not redundant with it: the corpus row fails with
        // "expected no rules, got otp_share", while this one names the constant
        // that is responsible, so whoever widened GAP is told what they broke.
        assertTrue(
            offlineRuleHits("Please share your OTP now", "en").any { it.ruleId == "otp_share" },
            "Within one sentence, otp_share must still fire — otherwise this " +
                "test would pass with the rule simply broken.",
        )
        assertFalse(
            offlineRuleHits("OTP for your login is 449281. Never share it with anyone. -HDFC Bank", "en")
                .any { it.ruleId == "otp_share" },
            "GAP must not cross '.', or the benign bank OTP warning becomes a " +
                "false positive. Python agrees: no rules fire on this text.",
        )
    }

    @Test
    fun `the looser gap does cross one sentence boundary`() {
        // The counterpart, and deliberately the opposite answer. GAP_ACROSS
        // exists because scam copy splits across sentences constantly, and KYC
        // notices have no benign shape that depends on the boundary the way the
        // OTP warning does. #23 made that a per-rule judgement rather than a
        // global setting.
        //
        // This assertion used to read assertFalse, with a comment claiming the
        // strict gap was "shared with the Python by construction" and citing an
        // xfail that #23 had already closed. It passed only because the Kotlin
        // engine had not received #23 — it pinned the divergence rather than the
        // specification, and #128 removing that divergence is what surfaced it.
        //
        // Measured against CPython's re:
        //   "Your KYC verification is pending. Please update it now." -> ['kyc_expiry']
        //   "Your KYC is expiring today"                              -> ['kyc_expiry']
        assertTrue(
            offlineRuleHits("Your KYC is expiring today", "en").any { it.ruleId == "kyc_expiry" },
            "The within-sentence case must fire, or the cross-sentence " +
                "assertion below proves nothing about the gap.",
        )
        assertTrue(
            offlineRuleHits("Your KYC verification is pending. Please update it now.", "en")
                .any { it.ruleId == "kyc_expiry" },
            "kyc_expiry uses GAP_ACROSS, so it may cross one sentence boundary. " +
                "en-kyc-cross-sentence-002 enforces this same text in the shared " +
                "corpus; if this fails, the two engines have diverged again.",
        )
    }
}
