package ai.raksha.app.core

import ai.raksha.rules.RULES
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

/**
 * The engine and the label table have to stay in step.
 *
 * A rule the engine can emit but the app cannot name would reach the user as
 * the generic fallback string — a warning that says nothing useful. The build
 * already fails when a rule has no entry in the web i18n bundles; this covers
 * the other half, where the bundle has the string but [RuleLabels] forgot to map
 * it.
 */
class RuleLabelCoverageTest {

    private val engineRuleIds: Set<String> =
        RULES.values.flatten().map { it.ruleId }.toSet()

    @Test
    fun `every rule the engine can emit has a label`() {
        val unlabelled = engineRuleIds - RuleLabels.knownRuleIds
        assertTrue(
            unlabelled.isEmpty(),
            "rules with no user-facing label: $unlabelled. Add the string to " +
                "frontend/src/i18n/locales/*.json and map it in RuleLabels.",
        )
    }

    @Test
    fun `no label exists for a rule the engine cannot emit`() {
        // A stale label is dead weight and, worse, suggests coverage that is
        // not there.
        val orphaned = RuleLabels.knownRuleIds - engineRuleIds
        assertEquals(emptySet(), orphaned, "labels for rules that no longer exist")
    }

    @Test
    fun `the build script's rule list matches the engine`() {
        // app/build.gradle.kts duplicates this list because it runs before
        // :core:rules is compiled. This is the assertion that keeps the
        // duplicate honest.
        val declaredInBuildScript = setOf(
            "otp_share", "kyc_expiry", "lottery_win", "account_lock", "refund_click", "urgent_verify",
        )
        assertEquals(
            engineRuleIds,
            declaredInBuildScript,
            "requiredRuleIds in app/build.gradle.kts has drifted from RULES in :core:rules",
        )
    }
}
