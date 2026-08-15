"""Offline-first fallback: catches obvious scams with zero network call, in
case both LLM providers are down (or the user has no connectivity and this
runs against a bundled copy client-side later). Deliberately conservative —
this only flags, never clears; the LLM+RAG path is still the primary judge.

Each rule carries a stable `rule_id` so a fired rule can be itemised in the
verdict trace and named in the user's own language (the frontend looks the id
up in its `trace.rules.*` bundle). Ids are concept-level, not per-regex: the
Hindi and English "share your OTP" patterns are the same rule, so a trace
reads the same whichever language the message arrived in.

**On false positives.** A legitimate bank SMS saying "never share your OTP
with anyone" will match `otp_share`. That is intended. Suppressing it needs a
negation heuristic, and any such heuristic can also suppress a real scam that
happens to contain a negation ("do not delay, share your OTP now") — which
inverts the module's stated contract. ARCHITECTURE.md is explicit that
over-warning is recoverable and wrongly clearing a real scam is not, so this
errs toward flagging.
"""

import re
from dataclasses import dataclass

# Separator between the two halves of a rule. Bounded so the halves have to be
# in the same breath, and stopping at sentence punctuation so a rule cannot
# span two unrelated sentences. Wider than it looks for Indic scripts, where
# combining marks each consume a character.
_GAP = r"[^.!?\n]{0,40}?"

#: A gap that may cross one sentence boundary, for the rules where that is safe.
#:
#: The strict `_GAP` above is load-bearing and stays the default: it is the only
#: thing stopping "OTP for your login is 449281. Never share it with anyone."
#: from firing `otp_share`, because the OTP and the word "share" sit in
#: different sentences. Relaxing it globally would trade a real recall gain for
#: a false positive on the single most common legitimate bank SMS there is.
#:
#: But scam copy splits across sentences constantly — "Refund pending. Click
#: here." — so the boundary costs recall on rules where no such benign shape
#: exists. Refunds and KYC notices have no equivalent of the OTP warning, so
#: they get the looser gap and OTP does not. This is a per-rule judgement, not
#: a setting, which is why it is two constants rather than a flag.
_GAP_ACROSS = r"[^\n]{0,60}?"


def _either_order(left: str, right: str, gap: str = _GAP) -> str:
    """Scam copy does not respect word order — "share your OTP" and "OTP ko
    share karein" are the same rule. Matching only one direction is what made
    the original `\\bOTP\\b.{0,20}\\bshare\\b` unable to fire on real messages."""
    return f"(?:{left}{gap}{right}|{right}{gap}{left})"


@dataclass(frozen=True)
class Rule:
    rule_id: str
    pattern: str


@dataclass(frozen=True)
class RuleHit:
    """One rule that fired, and the text in the message that tripped it."""

    rule_id: str
    pattern: str
    matched_text: str


# Verb stems, not whole words: real messages say "expiring", "blocked",
# "sharing" — matching only the dictionary form is why several of these
# silently never fired.
#
# The acronym AND the thing it stands for. Keying only on "OTP" is what the
# red-team loop walked straight past (#44): a paraphrase asking for "the numeric
# code sent to your phone" fired nothing at all, in a message the judge
# confirmed was the same fraud. Real scam copy avoids the acronym constantly —
# "verification code", "6-digit code", "one time password" — and a rule that
# only knows the abbreviation only catches lazy scammers.
_OTP = r"\b(?:OTP|O\.T\.P\.?|one[\s-]?time[\s-]?(?:password|passcode|pin|code))\b"
_CODE_WORD = (
    # "code" alone is far too common in legitimate SMS ("coupon code",
    # "referral code"), so it only counts when qualified by something that
    # implies authentication or delivery-to-your-phone.
    r"\b(?:verification|security|authentication|auth|access|confirmation|"
    r"numeric|numerical|\d[\s-]?digit|six[\s-]?digit|secret|confidential)"
    r"[\s-]?(?:code|pin)\b"
    r"|\bcode\s+(?:sent|received|texted|messaged)\b"
    r"|\b(?:code|pin)\s+(?:sent|received|transmitted)\s+to\s+your\b"
)
#: What an OTP rule matches on either side of the request. The union is what
#: makes `otp_share` robust to a scammer who never writes the acronym.
_OTP_ANY = f"(?:{_OTP}|{_CODE_WORD})"

_SHARE_EN = (
    # reveal and disclose (#63) were found by the red-team loop under the
    # formality_shift strategy — the register a scammer reaches for when
    # imitating an official notice, which is exactly when a victim complies.
    r"\b(?:shar\w*|send\w*|tell\w*|forward\w*|provid\w*|giv\w*|enter\w*"
    r"|submit\w*|confirm\w*|reveal\w*|disclos\w*)\b"
)
_KYC = r"\bKYC\b"
# suspen, not suspend: "suspension" is not "suspend" plus a suffix, so the old
# stem matched "suspended" and missed "suspension" entirely (#44). Every stem
# here is now the longest prefix common to the verb and its noun form.
_KYC_ACTION = r"\b(?:updat\w*|expir\w*|suspen\w*|deactivat\w*|re-?verif\w*|complet\w*)"
_LOCK_EN = r"\b(?:lock|block|freez|suspen|deactivat|clos|restrict|disabl)\w*\b"
_ACCOUNT_EN = r"\b(?:account|a/c|banking\s+services?)\b"

RULES: dict[str, list[Rule]] = {
    "en": [
        Rule("otp_share", _either_order(_OTP_ANY, _SHARE_EN)),
        Rule("kyc_expiry", _either_order(_KYC, _KYC_ACTION, _GAP_ACROSS)),
        Rule("lottery_win", r"\byou(?:'ve|\s+have)?\s*won\b|\b(?:lottery|lucky\s+draw|prize\s+money)\b"),
        Rule("account_lock", _either_order(_LOCK_EN, _ACCOUNT_EN)),
        Rule(
            "refund_click",
            _either_order(r"\brefund\w*\b", r"\b(?:click|link|tap|https?://)", _GAP_ACROSS),
        ),
        Rule("urgent_verify", _either_order(r"\b(?:urgent\w*|immediate\w*)\b", r"\b(?:verif\w*|updat\w*|confirm\w*)")),
    ],
    # Hindi, in both scripts it is actually written in.
    #
    # These rules were Devanagari-only, which meant they fired on the way a
    # newsreader writes Hindi and not on the way anyone texts it (#23). Latin-
    # script Hindi is the default register for SMS, and it is what an STT
    # transcript often produces too, so a Devanagari-only rule set misses the
    # majority of real messages in the language it claims to cover.
    #
    # The romanised alternatives are confined to the `hi` rule set rather than
    # added to English, because words like "band", "do" and "bata" are either
    # English words or fragments of them. Scoping them here means they are only
    # ever tried against a message already declared Hindi, which keeps the
    # false-positive blast radius inside the language they belong to.
    "hi": [
        Rule(
            "otp_share",
            _either_order(
                r"(?:ओटीपी|OTP|ek\s*time\s*password)",
                # bataiye/batao "tell", bhejo/bhejein "send", denge/do "give",
                # plus the code-mixed "share karo" that is neither language.
                r"(?:शेयर|साझा|भेज|बताइए|बताएं"
                r"|bata\w*|bhej\w*|sha?re\s*kar\w*|send\s*kar\w*|de\s*d\w*)",
            ),
        ),
        Rule(
            "kyc_expiry",
            _either_order(
                r"(?:केवाईसी|KYC)",
                r"(?:अपडेट|समाप्त|एक्सपायर|बंद|निलंबित"
                r"|update\s*kar\w*|samapt|khatam|band\s*ho)",
                _GAP_ACROSS,
            ),
        ),
        Rule(
            "account_lock",
            _either_order(
                r"(?:खाता|खाते|अकाउंट|khata|khaata|account)",
                r"(?:ब्लॉक|बंद|फ्रीज|निलंबित|band\s*ho\w*|block\s*ho\w*|freeze)",
            ),
        ),
        Rule("lottery_win", r"(?:लॉटरी|इनाम|पुरस्कार|lottery|inaam|inam)|जीत|jeet\w*"),
        Rule(
            "urgent_verify",
            _either_order(
                r"(?:तुरंत|जल्दी|शीघ्र|turant|jaldi|abhi)",
                r"(?:सत्यापित|वेरिफ़ाई|अपडेट|पुष्टि|verify|update\s*kar\w*)",
            ),
        ),
    ],
    "gu": [
        Rule("otp_share", _either_order(r"(?:ઓટીપી|OTP)", r"(?:શેર|મોકલ|જણાવ)")),
        Rule("kyc_expiry", _either_order(r"(?:કેવાયસી|KYC)", r"(?:અપડેટ|સમાપ્ત|બંધ|રદ)")),
        Rule("account_lock", _either_order(r"(?:ખાતું|ખાતા|એકાઉન્ટ)", r"(?:બ્લોક|બંધ|ફ્રીઝ)")),
        Rule("lottery_win", r"(?:લોટરી|ઇનામ|બક્ષિસ)|જીત"),
        Rule("urgent_verify", _either_order(r"(?:તાત્કાલિક|તરત|જલદી)", r"(?:ચકાસ|વેરિફાઈ|અપડેટ|પુષ્ટિ)")),
    ],
    "bn": [
        Rule("otp_share", _either_order(r"(?:ওটিপি|OTP)", r"(?:শেয়ার|পাঠান|পাঠিয়ে|বলুন|জানান)")),
        Rule("kyc_expiry", _either_order(r"(?:কেওয়াইসি|KYC)", r"(?:আপডেট|মেয়াদ|বন্ধ|স্থগিত|বাতিল)")),
        Rule("account_lock", _either_order(r"(?:অ্যাকাউন্ট|একাউন্ট|হিসাব)", r"(?:ব্লক|বন্ধ|স্থগিত|ফ্রিজ)")),
        Rule("lottery_win", r"(?:লটারি|পুরস্কার|লাকি\s*ড্র)|জিতেছেন"),
        Rule("urgent_verify", _either_order(r"(?:জরুরি|অবিলম্বে|এখনই)", r"(?:যাচাই|ভেরিফাই|আপডেট|নিশ্চিত)")),
    ],
    "ta": [
        Rule("otp_share", _either_order(r"(?:ஓடிபி|OTP)", r"(?:பகிர|அனுப்ப|சொல்ல|தெரிவி)")),
        Rule("kyc_expiry", _either_order(r"(?:கேஒய்சி|KYC)", r"(?:புதுப்ப|காலாவதி|முடக்க|ரத்து)")),
        Rule("account_lock", _either_order(r"(?:கணக்கு|கணக்கை|கணக்கின்)", r"(?:முடக்க|தடை|நிறுத்த|முடங்க)")),
        Rule("lottery_win", r"(?:லாட்டரி|பரிசு|குலுக்கல்)|வென்ற"),
        Rule("urgent_verify", _either_order(r"(?:அவசர|உடனடி|உடனே)", r"(?:சரிபார|உறுதிப்படுத்த|புதுப்ப)")),
    ],
    "te": [
        Rule("otp_share", _either_order(r"(?:ఓటీపీ|OTP)", r"(?:పంచ|పంపండి|చెప్పండి|తెలియజేయ)")),
        Rule("kyc_expiry", _either_order(r"(?:కేవైసీ|KYC)", r"(?:అప్‌డేట్|అప్డేట్|గడువు|నిలిపి|రద్ద)")),
        Rule("account_lock", _either_order(r"(?:ఖాతా|ఖాతాను|అకౌంట్)", r"(?:బ్లాక్|నిలిపి|మూసి|స్తంభింప)")),
        Rule("lottery_win", r"(?:లాటరీ|బహుమతి|లక్కీ\s*డ్రా)|గెలుచుకున్న"),
        Rule("urgent_verify", _either_order(r"(?:అత్యవసర|వెంటనే|తక్షణ)", r"(?:ధృవీకరించ|నిర్ధారించ|అప్‌డేట్|అప్డేట్)")),
    ],
    "kn": [
        Rule("otp_share", _either_order(r"(?:ಓಟಿಪಿ|OTP)", r"(?:ಹಂಚ|ಕಳುಹಿಸ|ಹೇಳ|ತಿಳಿಸ)")),
        Rule("kyc_expiry", _either_order(r"(?:ಕೆವೈಸಿ|KYC)", r"(?:ಅಪ್‌ಡೇಟ್|ಅಪ್ಡೇಟ್|ಅವಧಿ|ಸ್ಥಗಿತ|ರದ್ದು)")),
        Rule("account_lock", _either_order(r"(?:ಖಾತೆ|ಖಾತೆಯ|ಅಕೌಂಟ್)", r"(?:ಬ್ಲಾಕ್|ಸ್ಥಗಿತ|ಮುಚ್ಚ|ಫ್ರೀಜ್)")),
        Rule("lottery_win", r"(?:ಲಾಟರಿ|ಬಹುಮಾನ|ಅದೃಷ್ಟ\s*ಡ್ರಾ)|ಗೆದ್ದ"),
        Rule("urgent_verify", _either_order(r"(?:ತುರ್ತು|ತಕ್ಷಣ|ಕೂಡಲೇ)", r"(?:ಪರಿಶೀಲಿಸ|ದೃಢೀಕರಿಸ|ಅಪ್‌ಡೇಟ್|ಅಪ್ಡೇಟ್)")),
    ],
    "ml": [
        Rule("otp_share", _either_order(r"(?:ഒടിപി|OTP)", r"(?:പങ്കിട|അയയ്|അയക്ക|പറയ|അറിയിക്ക)")),
        Rule("kyc_expiry", _either_order(r"(?:കെവൈസി|KYC)", r"(?:അപ്ഡേറ്റ്|കാലാവധി|നിർത്ത|റദ്ദ)")),
        Rule("account_lock", _either_order(r"(?:അക്കൗണ്ട്|അക്കൌണ്ട്)", r"(?:ബ്ലോക്ക്|മരവിപ്പിക്ക|അടയ്ക്ക|നിർത്ത)")),
        Rule("lottery_win", r"(?:ലോട്ടറി|സമ്മാനം|ഭാഗ്യ\s*നറുക്ക്)|നേടി"),
        Rule("urgent_verify", _either_order(r"(?:അടിയന്തിര|ഉടൻ|ഉടനടി)", r"(?:പരിശോധിക്ക|സ്ഥിരീകരിക്ക|അപ്ഡേറ്റ്)")),
    ],
    "pa": [
        Rule("otp_share", _either_order(r"(?:ਓਟੀਪੀ|OTP)", r"(?:ਸਾਂਝਾ|ਸ਼ੇਅਰ|ਭੇਜ|ਦੱਸ)")),
        Rule("kyc_expiry", _either_order(r"(?:ਕੇਵਾਈਸੀ|KYC)", r"(?:ਅਪਡੇਟ|ਮਿਆਦ|ਖਤਮ|ਬੰਦ|ਮੁਅੱਤਲ)")),
        Rule("account_lock", _either_order(r"(?:ਖਾਤਾ|ਖਾਤੇ|ਅਕਾਊਂਟ)", r"(?:ਬਲਾਕ|ਬੰਦ|ਫ੍ਰੀਜ਼|ਮੁਅੱਤਲ)")),
        Rule("lottery_win", r"(?:ਲਾਟਰੀ|ਇਨਾਮ|ਲੱਕੀ\s*ਡਰਾਅ)|ਜਿੱਤ"),
        Rule("urgent_verify", _either_order(r"(?:ਤੁਰੰਤ|ਜਲਦੀ|ਫੌਰਨ)", r"(?:ਤਸਦੀਕ|ਵੈਰੀਫਾਈ|ਅਪਡੇਟ|ਪੁਸ਼ਟੀ)")),
    ],
    "or": [
        Rule("otp_share", _either_order(r"(?:ଓଟିପି|OTP)", r"(?:ସେୟାର|ପଠାନ୍ତୁ|କୁହନ୍ତୁ|ଜଣାନ୍ତୁ)")),
        Rule("kyc_expiry", _either_order(r"(?:କେୱାଇସି|KYC)", r"(?:ଅପଡେଟ|ମିଆଦ|ଶେଷ|ବନ୍ଦ|ସ୍ଥଗିତ)")),
        Rule("account_lock", _either_order(r"(?:ଖାତା|ଆକାଉଣ୍ଟ)", r"(?:ବ୍ଲକ|ବନ୍ଦ|ଫ୍ରିଜ|ସ୍ଥଗିତ)")),
        Rule("lottery_win", r"(?:ଲଟେରୀ|ପୁରସ୍କାର|ଲକି\s*ଡ୍ର)|ଜିତି"),
        Rule("urgent_verify", _either_order(r"(?:ତୁରନ୍ତ|ଶୀଘ୍ର|ଏବେ)", r"(?:ଯାଞ୍ଚ|ଭେରିଫାଏ|ଅପଡେଟ|ନିଶ୍ଚିତ)")),
    ],
    "ur": [
        # Urdu is RTL, but the patterns are plain character alternations and the
        # engine matches logical order, so direction does not affect matching.
        Rule("otp_share", _either_order(r"(?:او\s*ٹی\s*پی|OTP)", r"(?:شیئر|بھیج|بتائ|بتا)")),
        Rule("kyc_expiry", _either_order(r"(?:کے\s*وائی\s*سی|KYC)", r"(?:اپ\s*ڈیٹ|میعاد|ختم|بند|معطل)")),
        Rule("account_lock", _either_order(r"(?:اکاؤنٹ|کھاتہ)", r"(?:بلاک|بند|منجمد|معطل)")),
        Rule("lottery_win", r"(?:لاٹری|انعام|قرعہ\s*اندازی)|جیت"),
        Rule("urgent_verify", _either_order(r"(?:فوری|جلد|ابھی)", r"(?:تصدیق|توثیق|اپ\s*ڈیٹ|ویری\s*فائی)")),
    ],
}

#: Languages that take another language's rules wholesale.
#:
#: Marathi is written in Devanagari and shares this domain's vocabulary with
#: Hindi almost exactly — केवाईसी, ओटीपी, खाता, बंद are the same words. Before
#: #31 it scored zero on a message that Hindi scored three rules on, and the
#: only difference was a missing dictionary key.
#:
#: Stated here rather than implied by lookup order, so the borrowing is
#: reviewable: someone reading this table can see that `mr` has no rules of its
#: own, which is a different claim from `mr` being covered.
SCRIPT_INHERITANCE: dict[str, str] = {
    "mr": "hi",
}

#: How much confidence each language's rules deserve.
#:
#: `unreviewed` is not a formality. A rule nobody who speaks the language has
#: read is a guess, and a guessed rule that never fires is invisible — which is
#: exactly how nine languages shipped with no coverage at all. Recording the
#: status makes the gap countable instead of assumed away.
#:
#:   in-service  — shipped, exercised by the corpus, corrected by #18
#:   inherited   — borrows another language's rules; see SCRIPT_INHERITANCE
#:   unreviewed  — patterns written from the concept list, NOT yet read by a
#:                 native speaker. They fire on the corpus rows, which proves
#:                 the plumbing, not the vocabulary.
REVIEW_STATUS: dict[str, str] = {
    "en": "in-service",
    "hi": "in-service",
    "gu": "in-service",
    "mr": "inherited",
    "bn": "unreviewed",
    "ta": "unreviewed",
    "te": "unreviewed",
    "kn": "unreviewed",
    "ml": "unreviewed",
    "pa": "unreviewed",
    "or": "unreviewed",
    "ur": "unreviewed",
}


def _resolve(language: str) -> list[Rule]:
    """The rules a language actually uses, following inheritance once."""
    if language in RULES:
        return RULES[language]
    parent = SCRIPT_INHERITANCE.get(language)
    return RULES.get(parent, []) if parent else []


#: Every supported language mapped to the rules it uses, inheritance resolved.
#: Built once so the lookup in `offline_rule_hits` stays a dictionary hit.
RESOLVED_RULES: dict[str, list[Rule]] = {
    language: _resolve(language) for language in REVIEW_STATUS
}

# Compiled once at import — this runs on every scan, and is meant to stay fast
# enough to port onto a low-end Android device later.
_COMPILED: dict[str, list[tuple[Rule, re.Pattern[str]]]] = {
    lang: [(rule, re.compile(rule.pattern, re.IGNORECASE)) for rule in rules]
    for lang, rules in RESOLVED_RULES.items()
}


def offline_rule_hits(text: str, language: str) -> list[RuleHit]:
    """Every rule that fired, with the substring that tripped it.

    The message's own language rules run first, then English — Indian scam SMS
    is routinely code-mixed, so an English `OTP` appears inside Hindi copy."""
    seen_ids: set[str] = set()
    hits: list[RuleHit] = []

    for rule, compiled in _COMPILED.get(language, []) + _COMPILED["en"]:
        if rule.rule_id in seen_ids:
            continue
        match = compiled.search(text)
        if match:
            seen_ids.add(rule.rule_id)
            hits.append(
                RuleHit(
                    rule_id=rule.rule_id,
                    pattern=rule.pattern,
                    matched_text=match.group(0).strip(),
                )
            )
    return hits


def offline_flag(text: str, language: str) -> list[str]:
    """Backwards-compatible view of `offline_rule_hits` returning just the
    matched text, for callers that only need "did anything fire"."""
    return [hit.matched_text for hit in offline_rule_hits(text, language)]
