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
 * A gap that may cross one sentence boundary, for the rules where that is safe.
 *
 * [GAP] stays the default and is load-bearing: it is the only thing stopping
 * "OTP for your login is 449281. Never share it with anyone." from firing
 * `otp_share`, because the OTP and the word "share" sit in different sentences.
 * Relaxing it globally would trade a real recall gain for a false positive on
 * the single most common legitimate bank SMS there is.
 *
 * Scam copy splits across sentences constantly — "Refund pending. Click here."
 * — so refunds and KYC notices get the looser gap and OTP does not. A per-rule
 * judgement, which is why it is two constants rather than a flag.
 *
 * Mirrors `_GAP_ACROSS` in `rule_engine.py`.
 */
private const val GAP_ACROSS = """[^\n]{0,60}?"""

/**
 * Scam copy does not respect word order — "share your OTP" and "OTP ko share
 * karein" are the same rule. Matching only one direction is what made the
 * original `\bOTP\b.{0,20}\bshare\b` unable to fire on real messages.
 */
private fun eitherOrder(left: String, right: String, gap: String = GAP): String =
    "(?:$left$gap$right|$right$gap$left)"

// Verb stems, not whole words: real messages say "expiring", "blocked",
// "sharing" — matching only the dictionary form is why several of these
// silently never fired.
// The acronym AND the thing it stands for. Keying only on "OTP" is what the
// red-team loop walked straight past (#44): a paraphrase asking for "the
// numeric code sent to your phone" fired nothing at all, in a message the judge
// confirmed was the same fraud.
private const val OTP = """\b(?:OTP|O\.T\.P\.?|one[\s-]?time[\s-]?(?:password|passcode|pin|code))\b"""

// "code" alone is far too common in legitimate SMS ("coupon code", "referral
// code"), so it only counts when qualified by something implying
// authentication or delivery-to-your-phone.
private const val CODE_WORD =
    """\b(?:verification|security|authentication|auth|access|confirmation|""" +
        """numeric|numerical|\d[\s-]?digit|six[\s-]?digit|secret|confidential)""" +
        """[\s-]?(?:code|pin)\b""" +
        """|\bcode\s+(?:sent|received|texted|messaged)\b""" +
        """|\b(?:code|pin)\s+(?:sent|received|transmitted)\s+to\s+your\b"""

/** What an OTP rule matches on either side of the request (#46). */
private const val OTP_ANY = "(?:$OTP|$CODE_WORD)"

// reveal and disclose (#63) were found by the red-team loop under the
// formality_shift strategy — the register a scammer reaches for when imitating
// an official notice, which is exactly when a victim complies.
private const val SHARE_EN =
    """\b(?:shar\w*|send\w*|tell\w*|forward\w*|provid\w*|giv\w*|enter\w*""" +
        """|submit\w*|confirm\w*|reveal\w*|disclos\w*)\b"""

private const val KYC = """\bKYC\b"""

// suspen, not suspend: "suspension" is not "suspend" plus a suffix, so the old
// stem matched "suspended" and missed "suspension" entirely (#44). Every stem
// here is the longest prefix common to the verb and its noun form.
private const val KYC_ACTION = """\b(?:updat\w*|expir\w*|suspen\w*|deactivat\w*|re-?verif\w*|complet\w*)"""
private const val LOCK_EN = """\b(?:lock|block|freez|suspen|deactivat|clos|restrict|disabl)\w*\b"""
private const val ACCOUNT_EN = """\b(?:account|a/c|banking\s+services?)\b"""

val RULES: Map<String, List<Rule>> = mapOf(
    "en" to listOf(
        Rule("otp_share", eitherOrder(OTP_ANY, SHARE_EN)),
        Rule("kyc_expiry", eitherOrder(KYC, KYC_ACTION, GAP_ACROSS)),
        Rule(
            "lottery_win",
            """\byou(?:'ve|\s+have)?\s*won\b|\b(?:lottery|lucky\s+draw|prize\s+money)\b""",
        ),
        Rule("account_lock", eitherOrder(LOCK_EN, ACCOUNT_EN)),
        Rule(
            "refund_click",
            eitherOrder("""\brefund\w*\b""", """\b(?:click|link|tap|https?://)""", GAP_ACROSS),
        ),
        Rule(
            "urgent_verify",
            eitherOrder("""\b(?:urgent\w*|immediate\w*)\b""", """\b(?:verif\w*|updat\w*|confirm\w*)"""),
        ),
    ),
    // Hindi, in both scripts it is actually written in (#66).
    //
    // These rules were Devanagari-only, so they fired on the way a newsreader
    // writes Hindi and not on the way anyone texts it. Latin-script Hindi is the
    // default register for SMS and is what an STT transcript often produces too.
    //
    // ROMANISED STEMS USE [a-z], NOT \w, AND THAT IS DELIBERATE.
    //
    // `RegexDialectTest.no Indic rule uses a word class or boundary` forbids \w
    // in a non-English rule, because Java's \w is ASCII-only and Python's is
    // Unicode-aware — the divergence RULE-PARITY.md §03 documents. Porting
    // Python's `bata\w*` verbatim would trip that guard, and the guard is right
    // to be there.
    //
    // [a-z] is what these stems actually mean: they only ever extend romanised
    // words. It behaves identically in both engines, states the ASCII intent
    // rather than implying it, and closes a latent divergence Python still has
    // — `bata\w*` would match a Devanagari suffix in Python and not in Java.
    // `rule_engine.py` is changed to match, so the two are textually identical.
    "hi" to listOf(
        Rule(
            "otp_share",
            eitherOrder(
                """(?:ओटीपी|OTP|ek\s*time\s*password)""",
                // bataiye/batao "tell", bhejo/bhejein "send", denge/do "give",
                // plus the code-mixed "share karo" that is neither language.
                """(?:शेयर|साझा|भेज|बताइए|बताएं""" +
                    """|bata[a-z]*|bhej[a-z]*|sha?re\s*kar[a-z]*|send\s*kar[a-z]*|de\s*d[a-z]*)""",
            ),
        ),
        Rule(
            "kyc_expiry",
            eitherOrder(
                """(?:केवाईसी|KYC)""",
                """(?:अपडेट|समाप्त|एक्सपायर|बंद|निलंबित""" +
                    """|update\s*kar[a-z]*|samapt|khatam|band\s*ho)""",
                GAP_ACROSS,
            ),
        ),
        Rule(
            "account_lock",
            eitherOrder(
                """(?:खाता|खाते|अकाउंट|khata|khaata|account)""",
                """(?:ब्लॉक|बंद|फ्रीज|निलंबित|band\s*ho[a-z]*|block\s*ho[a-z]*|freeze)""",
            ),
        ),
        Rule("lottery_win", """(?:लॉटरी|इनाम|पुरस्कार|lottery|inaam|inam)|जीत|jeet[a-z]*"""),
        Rule(
            "urgent_verify",
            eitherOrder(
                """(?:तुरंत|जल्दी|शीघ्र|turant|jaldi|abhi)""",
                """(?:सत्यापित|वेरिफ़ाई|अपडेट|पुष्टि|verify|update\s*kar[a-z]*)""",
            ),
        ),
    ),
    "gu" to listOf(
        Rule("otp_share", eitherOrder("""(?:ઓટીપી|OTP)""", """(?:શેર|મોકલ|જણાવ|કહ)""")),
        Rule("kyc_expiry", eitherOrder("""(?:કેવાયસી|KYC)""", """(?:અપડેટ|સમાપ્ત|બંધ|રદ|પૂર્ણ કરો)""")),
        Rule("account_lock", eitherOrder("""(?:ખાતું|ખાતા|એકાઉન્ટ|કાર્ડ)""", """(?:બ્લોક|બંધ|ફ્રીઝ)""")),
        Rule("lottery_win", """(?:લોટરી|ઇનામ|બક્ષિસ)|જીત"""),
        Rule("urgent_verify", eitherOrder("""(?:તાત્કાલિક|તરત|જલદી|આજે જ|કલાકમાં)""", """(?:ચકાસ|વેરિફ|અપડેટ|પુષ્ટિ|પૂર્ણ કરો)""")),
    ),
    "bn" to listOf(
        Rule("otp_share", eitherOrder("""(?:ওটিপি|OTP)""", """(?:শেয়ার|পাঠান|পাঠিয়ে|বলুন|জানান)""")),
        Rule("kyc_expiry", eitherOrder("""(?:কেওয়াইসি|KYC)""", """(?:আপডেট|মেয়াদ|বন্ধ|স্থগিত|বাতিল)""")),
        Rule("account_lock", eitherOrder("""(?:অ্যাকাউন্ট|একাউন্ট|হিসাব)""", """(?:ব্লক|বন্ধ|স্থগিত|ফ্রিজ)""")),
        Rule("lottery_win", """(?:লটারি|পুরস্কার|লাকি\s*ড্র)|জিতেছেন"""),
        Rule("urgent_verify", eitherOrder("""(?:জরুরি|অবিলম্বে|এখনই)""", """(?:যাচাই|ভেরিফাই|আপডেট|নিশ্চিত)""")),
    ),
    "ta" to listOf(
        Rule("otp_share", eitherOrder("""(?:ஓடிபி|OTP)""", """(?:பகிர|அனுப்ப|சொல்ல|தெரிவி)""")),
        Rule("kyc_expiry", eitherOrder("""(?:கேஒய்சி|KYC)""", """(?:புதுப்ப|காலாவதி|முடக்க|ரத்து)""")),
        Rule("account_lock", eitherOrder("""(?:கணக்கு|கணக்கை|கணக்கின்)""", """(?:முடக்க|தடை|நிறுத்த|முடங்க)""")),
        Rule("lottery_win", """(?:லாட்டரி|பரிசு|குலுக்கல்)|வென்ற"""),
        Rule("urgent_verify", eitherOrder("""(?:அவசர|உடனடி|உடனே)""", """(?:சரிபார|உறுதிப்படுத்த|புதுப்ப)""")),
    ),
    "te" to listOf(
        Rule("otp_share", eitherOrder("""(?:ఓటీపీ|OTP)""", """(?:పంచ|పంపండి|చెప్పండి|తెలియజేయ)""")),
        Rule("kyc_expiry", eitherOrder("""(?:కేవైసీ|KYC)""", """(?:అప్‌డేట్|అప్డేట్|గడువు|నిలిపి|రద్ద)""")),
        Rule("account_lock", eitherOrder("""(?:ఖాతా|ఖాతాను|అకౌంట్)""", """(?:బ్లాక్|నిలిపి|మూసి|స్తంభింప)""")),
        Rule("lottery_win", """(?:లాటరీ|బహుమతి|లక్కీ\s*డ్రా)|గెలుచుకున్న"""),
        Rule("urgent_verify", eitherOrder("""(?:అత్యవసర|వెంటనే|తక్షణ)""", """(?:ధృవీకరించ|నిర్ధారించ|అప్‌డేట్|అప్డేట్)""")),
    ),
    "kn" to listOf(
        Rule("otp_share", eitherOrder("""(?:ಓಟಿಪಿ|OTP)""", """(?:ಹಂಚ|ಕಳುಹಿಸ|ಹೇಳ|ತಿಳಿಸ)""")),
        Rule("kyc_expiry", eitherOrder("""(?:ಕೆವೈಸಿ|KYC)""", """(?:ಅಪ್‌ಡೇಟ್|ಅಪ್ಡೇಟ್|ಅವಧಿ|ಸ್ಥಗಿತ|ರದ್ದು)""")),
        Rule("account_lock", eitherOrder("""(?:ಖಾತೆ|ಖಾತೆಯ|ಅಕೌಂಟ್)""", """(?:ಬ್ಲಾಕ್|ಸ್ಥಗಿತ|ಮುಚ್ಚ|ಫ್ರೀಜ್)""")),
        Rule("lottery_win", """(?:ಲಾಟರಿ|ಬಹುಮಾನ|ಅದೃಷ್ಟ\s*ಡ್ರಾ)|ಗೆದ್ದ"""),
        Rule("urgent_verify", eitherOrder("""(?:ತುರ್ತು|ತಕ್ಷಣ|ಕೂಡಲೇ)""", """(?:ಪರಿಶೀಲಿಸ|ದೃಢೀಕರಿಸ|ಅಪ್‌ಡೇಟ್|ಅಪ್ಡೇಟ್)""")),
    ),
    "ml" to listOf(
        Rule("otp_share", eitherOrder("""(?:ഒടിപി|OTP)""", """(?:പങ്കിട|അയയ്|അയക്ക|പറയ|അറിയിക്ക)""")),
        Rule("kyc_expiry", eitherOrder("""(?:കെവൈസി|KYC)""", """(?:അപ്ഡേറ്റ്|കാലാവധി|നിർത്ത|റദ്ദ)""")),
        Rule("account_lock", eitherOrder("""(?:അക്കൗണ്ട്|അക്കൌണ്ട്)""", """(?:ബ്ലോക്ക്|മരവിപ്പിക്ക|അടയ്ക്ക|നിർത്ത)""")),
        Rule("lottery_win", """(?:ലോട്ടറി|സമ്മാനം|ഭാഗ്യ\s*നറുക്ക്)|നേടി"""),
        Rule("urgent_verify", eitherOrder("""(?:അടിയന്തിര|ഉടൻ|ഉടനടി)""", """(?:പരിശോധിക്ക|സ്ഥിരീകരിക്ക|അപ്ഡേറ്റ്)""")),
    ),
    "pa" to listOf(
        Rule("otp_share", eitherOrder("""(?:ਓਟੀਪੀ|OTP)""", """(?:ਸਾਂਝਾ|ਸ਼ੇਅਰ|ਭੇਜ|ਦੱਸ)""")),
        Rule("kyc_expiry", eitherOrder("""(?:ਕੇਵਾਈਸੀ|KYC)""", """(?:ਅਪਡੇਟ|ਮਿਆਦ|ਖਤਮ|ਬੰਦ|ਮੁਅੱਤਲ)""")),
        Rule("account_lock", eitherOrder("""(?:ਖਾਤਾ|ਖਾਤੇ|ਅਕਾਊਂਟ)""", """(?:ਬਲਾਕ|ਬੰਦ|ਫ੍ਰੀਜ਼|ਮੁਅੱਤਲ)""")),
        Rule("lottery_win", """(?:ਲਾਟਰੀ|ਇਨਾਮ|ਲੱਕੀ\s*ਡਰਾਅ)|ਜਿੱਤ"""),
        Rule("urgent_verify", eitherOrder("""(?:ਤੁਰੰਤ|ਜਲਦੀ|ਫੌਰਨ)""", """(?:ਤਸਦੀਕ|ਵੈਰੀਫਾਈ|ਅਪਡੇਟ|ਪੁਸ਼ਟੀ)""")),
    ),
    "or" to listOf(
        Rule("otp_share", eitherOrder("""(?:ଓଟିପି|OTP)""", """(?:ସେୟାର|ପଠାନ୍ତୁ|କୁହନ୍ତୁ|ଜଣାନ୍ତୁ)""")),
        Rule("kyc_expiry", eitherOrder("""(?:କେୱାଇସି|KYC)""", """(?:ଅପଡେଟ|ମିଆଦ|ଶେଷ|ବନ୍ଦ|ସ୍ଥଗିତ)""")),
        Rule("account_lock", eitherOrder("""(?:ଖାତା|ଆକାଉଣ୍ଟ)""", """(?:ବ୍ଲକ|ବନ୍ଦ|ଫ୍ରିଜ|ସ୍ଥଗିତ)""")),
        Rule("lottery_win", """(?:ଲଟେରୀ|ପୁରସ୍କାର|ଲକି\s*ଡ୍ର)|ଜିତି"""),
        Rule("urgent_verify", eitherOrder("""(?:ତୁରନ୍ତ|ଶୀଘ୍ର|ଏବେ)""", """(?:ଯାଞ୍ଚ|ଭେରିଫାଏ|ଅପଡେଟ|ନିଶ୍ଚିତ)""")),
    ),
    "ur" to listOf(
        // Urdu is RTL, but the patterns are plain character alternations and the
        // engine matches logical order, so direction does not affect matching.
        Rule("otp_share", eitherOrder("""(?:او\s*ٹی\s*پی|OTP)""", """(?:شیئر|بھیج|بتائ|بتا)""")),
        Rule("kyc_expiry", eitherOrder("""(?:کے\s*وائی\s*سی|KYC)""", """(?:اپ\s*ڈیٹ|میعاد|ختم|بند|معطل)""")),
        Rule("account_lock", eitherOrder("""(?:اکاؤنٹ|کھاتہ)""", """(?:بلاک|بند|منجمد|معطل)""")),
        Rule("lottery_win", """(?:لاٹری|انعام|قرعہ\s*اندازی)|جیت"""),
        Rule("urgent_verify", eitherOrder("""(?:فوری|جلد|ابھی)""", """(?:تصدیق|توثیق|اپ\s*ڈیٹ|ویری\s*فائی)""")),
    ),
)

/**
 * Languages that take another language's rules wholesale.
 *
 * Marathi is written in Devanagari and shares this domain's vocabulary with
 * Hindi almost exactly. Before #31 it scored zero on a message Hindi scored
 * three rules on, and the only difference was a missing key.
 *
 * Stated here rather than implied by lookup order, so the borrowing is
 * reviewable: `mr` having no rules of its own is a different claim from `mr`
 * being covered.
 */
val SCRIPT_INHERITANCE: Map<String, String> = mapOf(
    "mr" to "hi",
)

/**
 * How much confidence each language's rules deserve.
 *
 * `unreviewed` is not a formality. A rule nobody who speaks the language has
 * read is a guess, and a guessed rule that never fires is invisible — which is
 * exactly how nine languages shipped with no coverage at all.
 *
 *   in-service — shipped, exercised by the corpus, corrected by #18
 *   inherited  — borrows another language's rules; see [SCRIPT_INHERITANCE]
 *   unreviewed — written from the concept list, NOT yet read by a native
 *                speaker. They fire on the corpus rows, which proves the
 *                plumbing, not the vocabulary.
 */
val REVIEW_STATUS: Map<String, String> = mapOf(
    "en" to "in-service",
    "hi" to "in-service",
    "gu" to "in-service",
    "mr" to "inherited",
    "bn" to "unreviewed",
    "ta" to "unreviewed",
    "te" to "unreviewed",
    "kn" to "unreviewed",
    "ml" to "unreviewed",
    "pa" to "unreviewed",
    "or" to "unreviewed",
    "ur" to "unreviewed",
)

/** The rules a language actually uses, following inheritance once. */
private fun resolve(language: String): List<Rule> =
    RULES[language] ?: SCRIPT_INHERITANCE[language]?.let { RULES[it] } ?: emptyList()

/** Every supported language mapped to the rules it uses, inheritance resolved. */
val RESOLVED_RULES: Map<String, List<Rule>> =
    REVIEW_STATUS.keys.associateWith { resolve(it) }

/**
 * Compiled once, at class-load. Rebuilding a [Regex] per message would recompile
 * every pattern on every SMS — the Python compiles at import for the same
 * reason, and the latency budget on a low-end handset does not have room for it.
 */
private val COMPILED: Map<String, List<Pair<Rule, Regex>>> =
    RESOLVED_RULES.mapValues { (_, rules) ->
        rules.map { rule -> rule to Regex(rule.pattern, RegexOption.IGNORE_CASE) }
    }

/** The languages this engine has rules for, inheritance included. */
val supportedLanguages: Set<String> get() = RESOLVED_RULES.keys

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
