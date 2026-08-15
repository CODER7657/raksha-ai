package ai.raksha.rules

/**
 * On-device port of `backend/app/services/rule_engine.py`.
 *
 * This runs with no network, which is the whole reason it exists: forwarding a
 * message to the server to be scored would put every SMS a user receives into
 * our cloud, contradicting the privacy claim the product rests on.
 *
 * **This file is not free to diverge from the Python.** The two are held
 * together by `testdata/rule_corpus.jsonl`, which both test suites read. Change
 * a rule in the corpus first, then in both engines, in one commit. See
 * `docs/RULE-PARITY.md`.
 *
 * Structure is kept deliberately parallel to the Python — same constant names,
 * same rule order, same dedup behaviour — so a reviewer can diff them by eye.
 *
 * **On regex flags.** These patterns are compiled with case-insensitivity only,
 * and *not* with `UNICODE_CHARACTER_CLASS`, which is the opposite of what issue
 * #28 suggested. The reason is measured, not assumed, and is asserted in
 * `RegexDialectTest`:
 *
 *  - Java's `\w` is ASCII-only by default; Python's is Unicode-aware. That
 *    difference is real but unreachable here, because no rule asks `\w` to
 *    match a non-ASCII character — the verb stems only ever extend ASCII words.
 *  - Java's Unicode `\w` *includes* combining marks (`\p{gc=Mn}`); Python's
 *    excludes them. Turning the flag on therefore makes `\b` behave differently
 *    around Indic words, which is a new divergence in exchange for fixing one
 *    that never fires.
 *
 * So the flag stays off, and `RegexDialectTest` fails loudly if a future rule
 * puts `\w` or `\b` next to Indic text, where the choice would start to matter.
 */

/** One rule: a stable concept-level id, and the pattern that detects it. */
data class Rule(val ruleId: String, val pattern: String)

/** One rule that fired, and the text in the message that tripped it. */
data class RuleHit(
    val ruleId: String,
    val pattern: String,
    val matchedText: String,
)

/**
 * Separator between the two halves of a rule. Bounded so the halves have to be
 * in the same breath, and stopping at sentence punctuation so a rule cannot
 * span two unrelated sentences. Wider than it looks for Indic scripts, where
 * combining marks each consume a character.
 */
private const val GAP = """[^.!?\n]{0,40}?"""

/**
 * Scam copy does not respect word order — "share your OTP" and "OTP ko share
 * karein" are the same rule. Matching only one direction is what made the
 * original `\bOTP\b.{0,20}\bshare\b` unable to fire on real messages.
 */
private fun eitherOrder(left: String, right: String): String =
    "(?:$left$GAP$right|$right$GAP$left)"

// Verb stems, not whole words: real messages say "expiring", "blocked",
// "sharing" — matching only the dictionary form is why several of these
// silently never fired.
private const val OTP = """\bOTP\b"""
private const val SHARE_EN = """\b(?:shar\w*|send\w*|tell\w*|forward\w*|provid\w*|giv\w*)\b"""
private const val KYC = """\bKYC\b"""
private const val KYC_ACTION = """\b(?:updat\w*|expir\w*|suspend\w*|deactivat\w*|re-?verif\w*|complet\w*)"""
private const val LOCK_EN = """\b(?:lock|block|freez|suspend|deactivat|clos)\w*\b"""
private const val ACCOUNT_EN = """\baccount\b"""

val RULES: Map<String, List<Rule>> = mapOf(
    "en" to listOf(
        Rule("otp_share", eitherOrder(OTP, SHARE_EN)),
        Rule("kyc_expiry", eitherOrder(KYC, KYC_ACTION)),
        Rule(
            "lottery_win",
            """\byou(?:'ve|\s+have)?\s*won\b|\b(?:lottery|lucky\s+draw|prize\s+money)\b""",
        ),
        Rule("account_lock", eitherOrder(LOCK_EN, ACCOUNT_EN)),
        Rule("refund_click", eitherOrder("""\brefund\w*\b""", """\b(?:click|link|tap|https?://)""")),
        Rule(
            "urgent_verify",
            eitherOrder("""\b(?:urgent\w*|immediate\w*)\b""", """\b(?:verif\w*|updat\w*|confirm\w*)"""),
        ),
    ),
    "hi" to listOf(
        Rule("otp_share", eitherOrder("""(?:ओटीपी|OTP)""", """(?:शेयर|साझा|भेज|बताइए|बताएं)""")),
        Rule("kyc_expiry", eitherOrder("""(?:केवाईसी|KYC)""", """(?:अपडेट|समाप्त|एक्सपायर|बंद|निलंबित)""")),
        Rule("account_lock", eitherOrder("""(?:खाता|खाते|अकाउंट)""", """(?:ब्लॉक|बंद|फ्रीज|निलंबित)""")),
        Rule("lottery_win", """(?:लॉटरी|इनाम|पुरस्कार)|जीत"""),
        Rule("urgent_verify", eitherOrder("""(?:तुरंत|जल्दी|शीघ्र)""", """(?:सत्यापित|वेरिफ़ाई|अपडेट|पुष्टि)""")),
    ),
    "gu" to listOf(
        Rule("otp_share", eitherOrder("""(?:ઓટીપી|OTP)""", """(?:શેર|મોકલ|જણાવ)""")),
        Rule("kyc_expiry", eitherOrder("""(?:કેવાયસી|KYC)""", """(?:અપડેટ|સમાપ્ત|બંધ|રદ)""")),
        Rule("account_lock", eitherOrder("""(?:ખાતું|ખાતા|એકાઉન્ટ)""", """(?:બ્લોક|બંધ|ફ્રીઝ)""")),
        Rule("lottery_win", """(?:લોટરી|ઇનામ|બક્ષિસ)|જીત"""),
        Rule("urgent_verify", eitherOrder("""(?:તાત્કાલિક|તરત|જલદી)""", """(?:ચકાસ|વેરિફાઈ|અપડેટ|પુષ્ટિ)""")),
    ),
)

/**
 * Compiled once, at class-load. Rebuilding a [Regex] per message would recompile
 * every pattern on every SMS — the Python compiles at import for the same
 * reason, and the latency budget on a low-end handset does not have room for it.
 */
private val COMPILED: Map<String, List<Pair<Rule, Regex>>> =
    RULES.mapValues { (_, rules) ->
        rules.map { rule -> rule to Regex(rule.pattern, RegexOption.IGNORE_CASE) }
    }

/** The languages this engine has rules for. */
val supportedLanguages: Set<String> get() = RULES.keys

/**
 * Every rule that fired, with the substring that tripped it.
 *
 * The message's own language rules run first, then English — Indian scam SMS is
 * routinely code-mixed, so an English `OTP` appears inside Hindi copy. A rule id
 * reports once: the first match wins, which is why order matters and must match
 * the Python.
 */
fun offlineRuleHits(text: String, language: String): List<RuleHit> {
    val seenIds = mutableSetOf<String>()
    val hits = mutableListOf<RuleHit>()

    val ordered = (COMPILED[language] ?: emptyList()) + COMPILED.getValue("en")
    for ((rule, compiled) in ordered) {
        if (rule.ruleId in seenIds) continue
        val match = compiled.find(text) ?: continue
        seenIds += rule.ruleId
        hits += RuleHit(
            ruleId = rule.ruleId,
            pattern = rule.pattern,
            matchedText = match.value.trim(),
        )
    }
    return hits
}

/**
 * Backwards-compatible view of [offlineRuleHits] returning just the matched
 * text, mirroring `offline_flag` on the backend.
 */
fun offlineFlag(text: String, language: String): List<String> =
    offlineRuleHits(text, language).map { it.matchedText }
