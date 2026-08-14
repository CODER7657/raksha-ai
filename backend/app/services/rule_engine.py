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


def _either_order(left: str, right: str) -> str:
    """Scam copy does not respect word order — "share your OTP" and "OTP ko
    share karein" are the same rule. Matching only one direction is what made
    the original `\\bOTP\\b.{0,20}\\bshare\\b` unable to fire on real messages."""
    return f"(?:{left}{_GAP}{right}|{right}{_GAP}{left})"


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
_OTP = r"\bOTP\b"
_SHARE_EN = r"\b(?:shar\w*|send\w*|tell\w*|forward\w*|provid\w*|giv\w*)\b"
_KYC = r"\bKYC\b"
_KYC_ACTION = r"\b(?:updat\w*|expir\w*|suspend\w*|deactivat\w*|re-?verif\w*|complet\w*)"
_LOCK_EN = r"\b(?:lock|block|freez|suspend|deactivat|clos)\w*\b"
_ACCOUNT_EN = r"\baccount\b"

RULES: dict[str, list[Rule]] = {
    "en": [
        Rule("otp_share", _either_order(_OTP, _SHARE_EN)),
        Rule("kyc_expiry", _either_order(_KYC, _KYC_ACTION)),
        Rule("lottery_win", r"\byou(?:'ve|\s+have)?\s*won\b|\b(?:lottery|lucky\s+draw|prize\s+money)\b"),
        Rule("account_lock", _either_order(_LOCK_EN, _ACCOUNT_EN)),
        Rule("refund_click", _either_order(r"\brefund\w*\b", r"\b(?:click|link|tap|https?://)")),
        Rule("urgent_verify", _either_order(r"\b(?:urgent\w*|immediate\w*)\b", r"\b(?:verif\w*|updat\w*|confirm\w*)")),
    ],
    "hi": [
        Rule("otp_share", _either_order(r"(?:ओटीपी|OTP)", r"(?:शेयर|साझा|भेज|बताइए|बताएं)")),
        Rule("kyc_expiry", _either_order(r"(?:केवाईसी|KYC)", r"(?:अपडेट|समाप्त|एक्सपायर|बंद|निलंबित)")),
        Rule("account_lock", _either_order(r"(?:खाता|खाते|अकाउंट)", r"(?:ब्लॉक|बंद|फ्रीज|निलंबित)")),
        Rule("lottery_win", r"(?:लॉटरी|इनाम|पुरस्कार)|जीत"),
        Rule("urgent_verify", _either_order(r"(?:तुरंत|जल्दी|शीघ्र)", r"(?:सत्यापित|वेरिफ़ाई|अपडेट|पुष्टि)")),
    ],
    "gu": [
        Rule("otp_share", _either_order(r"(?:ઓટીપી|OTP)", r"(?:શેર|મોકલ|જણાવ)")),
        Rule("kyc_expiry", _either_order(r"(?:કેવાયસી|KYC)", r"(?:અપડેટ|સમાપ્ત|બંધ|રદ)")),
        Rule("account_lock", _either_order(r"(?:ખાતું|ખાતા|એકાઉન્ટ)", r"(?:બ્લોક|બંધ|ફ્રીઝ)")),
        Rule("lottery_win", r"(?:લોટરી|ઇનામ|બક્ષિસ)|જીત"),
        Rule("urgent_verify", _either_order(r"(?:તાત્કાલિક|તરત|જલદી)", r"(?:ચકાસ|વેરિફાઈ|અપડેટ|પુષ્ટિ)")),
    ],
}

# Compiled once at import — this runs on every scan, and is meant to stay fast
# enough to port onto a low-end Android device later.
_COMPILED: dict[str, list[tuple[Rule, re.Pattern[str]]]] = {
    lang: [(rule, re.compile(rule.pattern, re.IGNORECASE)) for rule in rules]
    for lang, rules in RULES.items()
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
