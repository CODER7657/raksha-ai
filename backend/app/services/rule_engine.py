"""Offline-first fallback: catches obvious scams with zero network call, in
case both LLM providers are down (or the user has no connectivity and this
runs against a bundled copy client-side later). Deliberately conservative —
this only flags, never clears; the LLM+RAG path is still the primary judge.
"""

import re

# Keyword/pattern fragments per language. Intentionally small and
# maintainable by hand — this is a safety net, not the main classifier.
PATTERNS: dict[str, list[str]] = {
    "en": [
        r"\bOTP\b.{0,20}\bshare\b",
        r"\bKYC\b.{0,20}\b(update|expire|suspend)",
        r"\byou\s+have\s+won\b",
        r"\block\b.{0,20}\baccount\b",
        r"\brefund\b.{0,20}\bclick\b",
        r"\burgent(ly)?\b.{0,20}\bverify\b",
    ],
    "hi": [
        r"ओटीपी.{0,20}शेयर",
        r"केवाईसी.{0,20}(अपडेट|बंद)",
        r"खाता.{0,20}ब्लॉक",
        r"लॉटरी.{0,20}जीत",
    ],
    "gu": [
        r"ઓટીપી.{0,20}શેર",
        r"કેવાયસી.{0,20}અપડેટ",
        r"ખાતું.{0,20}બ્લોક",
    ],
}


def offline_flag(text: str, language: str) -> list[str]:
    """Returns matched pattern fragments, empty if nothing obvious found."""
    patterns = PATTERNS.get(language, []) + PATTERNS["en"]
    matches = []
    for pattern in patterns:
        if re.search(pattern, text, flags=re.IGNORECASE):
            matches.append(pattern)
    return matches
