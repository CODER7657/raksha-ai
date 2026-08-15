package ai.raksha.app.core

import android.content.Context
import androidx.annotation.StringRes
import ai.raksha.app.R

/**
 * Turns a rule id into the sentence a user reads.
 *
 * The strings come from `build/generated/i18nRes`, generated at build time from
 * the web app's own i18n bundles — see the generator in `app/build.gradle.kts`.
 * They are not retyped here, so the phone and the website describe a rule with
 * the same words.
 *
 * #29 §7 is blunt that a raw regex must never reach a user. [labelFor] therefore
 * has no pattern-shaped fallback: an unmapped rule id returns a neutral generic
 * string rather than the pattern that produced it.
 */
object RuleLabels {

    private val labels: Map<String, Int> = mapOf(
        "otp_share" to R.string.trace_rules_otp_share,
        "kyc_expiry" to R.string.trace_rules_kyc_expiry,
        "lottery_win" to R.string.trace_rules_lottery_win,
        "account_lock" to R.string.trace_rules_account_lock,
        "refund_click" to R.string.trace_rules_refund_click,
        "urgent_verify" to R.string.trace_rules_urgent_verify,
    )

    /** The rule ids this app can describe in words. Asserted against the engine. */
    val knownRuleIds: Set<String> get() = labels.keys

    @StringRes
    fun stringResFor(ruleId: String): Int? = labels[ruleId]

    /**
     * The user-facing sentence for a rule.
     *
     * An unknown id falls back to a generic phrase, never to the pattern. A new
     * rule reaching this path is a bug caught by the build — the generator fails
     * when a rule has no label — but the fallback exists so that a bug shows a
     * vague warning rather than leaking a regex.
     */
    fun labelFor(context: Context, ruleId: String): String =
        labels[ruleId]?.let(context::getString)
            ?: context.getString(R.string.rule_generic_warning)
}
