package ai.raksha.rules

import kotlinx.serialization.json.Json
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import java.io.File
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue
import kotlin.test.fail

/**
 * The Kotlin half of the shared corpus.
 *
 * `testdata/rule_corpus.jsonl` is the specification; this suite and the Python
 * `test_rule_corpus.py` are two implementations of it. If this fails, do not
 * edit the corpus to make it pass — either the port drifted, or the corpus is
 * changing deliberately and the Python suite needs the same change in the same
 * commit.
 *
 * `known_gap` rows are checked **strictly, in both directions**, matching the
 * Python. A documented defect that quietly starts working fails the build and
 * asks whoever fixed it to update the corpus, so closing a gap is a visible
 * edit to the specification rather than a silent behaviour change — and, since
 * both engines read the same file, it cannot be closed on one platform only.
 *
 * See `testdata/README.md`, `docs/RULE-PARITY.md`, and issues #28 and #33.
 */
class RuleCorpusTest {

    private data class Case(
        val id: String,
        val language: String,
        val label: String,
        val status: String,
        val text: String,
        val expectedRuleIds: List<String>,
    ) {
        val isEnforced: Boolean get() = status == "enforced"
        val isKnownGap: Boolean get() = status == "known_gap"
    }

    private companion object {
        val KNOWN_RULE_IDS = setOf(
            "otp_share", "kyc_expiry", "account_lock",
            "lottery_win", "refund_click", "urgent_verify",
        )

        /** Mirrors LanguageCode in backend/app/routes/scan.py. */
        val LANGUAGES = setOf(
            "en", "hi", "gu", "mr", "bn", "ta", "te", "kn", "ml", "pa", "or", "ur",
        )

        /**
         * Walks up from the module directory to find the repo root. Hardcoding
         * a relative path would break the moment the module moves, and the
         * failure would look like a corpus problem rather than a path problem.
         */
        fun corpusFile(): File {
            var dir: File? = File(System.getProperty("user.dir"))
            while (dir != null) {
                val candidate = File(dir, "testdata/rule_corpus.jsonl")
                if (candidate.isFile) return candidate
                dir = dir.parentFile
            }
            fail("Could not find testdata/rule_corpus.jsonl from ${System.getProperty("user.dir")}")
        }

        val cases: List<Case> by lazy {
            corpusFile().readLines()
                .map(String::trim)
                .filter { it.isNotEmpty() }
                .map { line ->
                    val obj = Json.parseToJsonElement(line).jsonObject
                    Case(
                        id = obj.getValue("id").jsonPrimitive.content,
                        language = obj.getValue("language").jsonPrimitive.content,
                        label = obj.getValue("label").jsonPrimitive.content,
                        status = obj.getValue("status").jsonPrimitive.content,
                        text = obj.getValue("text").jsonPrimitive.content,
                        expectedRuleIds = obj.getValue("expected_rule_ids")
                            .jsonArray.map { it.jsonPrimitive.content }.sorted(),
                    )
                }
        }
    }

    private fun fired(case: Case): List<String> =
        offlineRuleHits(case.text, case.language).map { it.ruleId }.distinct().sorted()

    @Test
    fun `corpus is present and non-empty`() {
        assertTrue(cases.isNotEmpty(), "no cases loaded")
    }

    @Test
    fun `every case is well formed`() {
        cases.forEach { case ->
            assertTrue(case.text.isNotBlank(), "${case.id}: empty text")
            assertTrue(case.label in setOf("scam", "benign"), "${case.id}: bad label ${case.label}")
            assertTrue(
                case.status in setOf("enforced", "known_gap"),
                "${case.id}: bad status ${case.status}",
            )
            val unknown = case.expectedRuleIds.toSet() - KNOWN_RULE_IDS
            assertTrue(unknown.isEmpty(), "${case.id}: unknown rule ids $unknown")
            if (case.label == "benign") {
                assertEquals(emptyList(), case.expectedRuleIds, "${case.id}: benign expects nothing")
            }
        }
    }

    @Test
    fun `case ids are unique`() {
        val duplicates = cases.groupBy { it.id }.filterValues { it.size > 1 }.keys
        assertTrue(duplicates.isEmpty(), "duplicate case ids: $duplicates")
    }

    @Test
    fun `every enforced case matches exactly`() {
        // Exact set equality, not containment: a rule that starts firing where
        // it should not is as much a regression as one that stops firing.
        val failures = cases.filter { it.isEnforced }.mapNotNull { case ->
            val got = fired(case)
            if (got == case.expectedRuleIds) null else
                "  ${case.id} [${case.language}]\n    want: ${case.expectedRuleIds}\n    got:  $got"
        }
        assertTrue(
            failures.isEmpty(),
            "${failures.size} enforced case(s) diverge from the specification:\n" +
                failures.joinToString("\n"),
        )
    }

    @Test
    fun `every known gap still fails`() {
        // Strict, and identical to the Python assertion. When a gap closes, both
        // suites fail together, so the corpus cannot be updated for one engine
        // and not the other.
        val unexpectedlyPassing = cases.filter { it.isKnownGap }
            .filter { fired(it) == it.expectedRuleIds }
            .map { it.id }
        assertTrue(
            unexpectedlyPassing.isEmpty(),
            "known_gap case(s) now produce the expected rules: $unexpectedlyPassing. " +
                "If you fixed the gap, change status to 'enforced' in " +
                "testdata/rule_corpus.jsonl — and update the Python suite in the same commit.",
        )
    }

    @Test
    fun `known rule ids match the engine`() {
        val engineIds = RULES.values.flatten().map { it.ruleId }.toSet()
        assertEquals(KNOWN_RULE_IDS, engineIds, "KNOWN_RULE_IDS has drifted from RULES")
    }

    @Test
    fun `every rule id is exercised by at least one case`() {
        val covered = cases.flatMap { it.expectedRuleIds }.toSet()
        assertEquals(emptySet(), KNOWN_RULE_IDS - covered, "rule ids with no corpus case")
    }

    @Test
    fun `rule ids are shared across languages`() {
        // The trace viewer looks an id up in one `trace.rules.*` bundle, so an
        // id must mean the same thing in every language it appears in.
        val english = RULES.getValue("en").map { it.ruleId }.toSet()
        RULES.forEach { (language, rules) ->
            val unknown = rules.map { it.ruleId }.toSet() - english
            assertTrue(unknown.isEmpty(), "$language has rule ids absent from en: $unknown")
        }
    }

    @Test
    fun `a hit carries the text that tripped it`() {
        val text = "Please share OTP 123456 now"
        val hit = offlineRuleHits(text, "en").first { it.ruleId == "otp_share" }
        assertTrue(hit.matchedText.isNotEmpty())
        assertTrue(text.contains(hit.matchedText), "matched text should be a substring")
        assertTrue(hit.pattern.isNotEmpty())
    }

    @Test
    fun `each rule fires at most once`() {
        val hits = offlineRuleHits("Share OTP, share OTP, share the OTP again", "en")
        assertEquals(hits.size, hits.map { it.ruleId }.toSet().size)
    }

    @Test
    fun `an unknown language still runs the english rules`() {
        // Mirrors the Python: `COMPILED.get(language, []) + COMPILED["en"]`.
        // A user on an unsupported language must not silently get zero coverage.
        assertTrue(offlineRuleHits("Share your OTP now", "ta").any { it.ruleId == "otp_share" })
    }

    @Test
    fun `offlineFlag stays backwards compatible`() {
        assertTrue(offlineFlag("Share your OTP now", "en").isNotEmpty())
    }

    // --- Language coverage (#31) --------------------------------------------

    @Test
    fun `every supported language has rules`() {
        // Before #31, nine of twelve languages had no rules, so a scam in those
        // languages fired nothing at all. This assertion is what stops a
        // thirteenth language being added the same way.
        val missing = LANGUAGES - RESOLVED_RULES.keys
        assertTrue(
            missing.isEmpty(),
            "no offline rule coverage for: ${missing.sorted()}. Every language needs " +
                "native rules, or an entry in SCRIPT_INHERITANCE pointing at a " +
                "language whose script it shares.",
        )
        RESOLVED_RULES.forEach { (language, rules) ->
            assertTrue(rules.isNotEmpty(), "$language resolves to an empty rule list")
        }
    }

    @Test
    fun `every language has a stated review status`() {
        assertEquals(LANGUAGES, REVIEW_STATUS.keys, "REVIEW_STATUS must cover every language")
        val allowed = setOf("in-service", "inherited", "unreviewed")
        REVIEW_STATUS.forEach { (language, status) ->
            assertTrue(status in allowed, "$language has unknown review status '$status'")
        }
    }

    @Test
    fun `inherited languages point at a language that has rules`() {
        SCRIPT_INHERITANCE.forEach { (child, parent) ->
            assertTrue(
                RULES[parent]?.isNotEmpty() == true,
                "$child inherits from $parent, which has no rules of its own",
            )
            assertEquals("inherited", REVIEW_STATUS[child], "$child should be marked inherited")
        }
    }

    @Test
    fun `the language tables match the Python engine`() {
        // The two engines are held together by the corpus for behaviour, but
        // these tables are structure rather than behaviour, so nothing else
        // would catch them drifting. Hardcoded from rule_engine.py deliberately:
        // if that file changes, this fails and someone has to look.
        assertEquals(mapOf("mr" to "hi"), SCRIPT_INHERITANCE)
        assertEquals(
            setOf("en", "hi", "gu", "bn", "ta", "te", "kn", "ml", "pa", "or", "ur"),
            RULES.keys,
            "languages with native rules have drifted from the Python engine",
        )
    }
}
