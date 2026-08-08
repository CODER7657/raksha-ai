"""Single source of truth for the languages Raksha AI supports.

Why this exists: the chat and scan prompts used to interpolate the bare ISO
code into the prompt (`f"Reply in: {language}"` -> the model literally read
"Reply in: gu"). Two-letter codes are weak grounding — models often ignore
them, and the failure is silent: you get a fluent English reply to a Gujarati
request and nothing looks broken. Naming the language and its script
explicitly ("Gujarati (ગુજરાતી), written in the Gujarati script") is far
harder to misread.

Keep the codes here in sync with:
  - `LanguageCode` in app/routes/chat.py and app/routes/scan.py
  - `LANGUAGES` in frontend/src/lib/languages.ts
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Language:
    code: str
    english_name: str
    native_name: str
    script: str
    #: BCP-47 tag, used for browser speechSynthesis voice matching.
    bcp47: str


LANGUAGES: dict[str, Language] = {
    "en": Language("en", "English", "English", "Latin", "en-IN"),
    "hi": Language("hi", "Hindi", "हिन्दी", "Devanagari", "hi-IN"),
    "gu": Language("gu", "Gujarati", "ગુજરાતી", "Gujarati", "gu-IN"),
    "mr": Language("mr", "Marathi", "मराठी", "Devanagari", "mr-IN"),
    "bn": Language("bn", "Bengali", "বাংলা", "Bengali", "bn-IN"),
    "ta": Language("ta", "Tamil", "தமிழ்", "Tamil", "ta-IN"),
    "te": Language("te", "Telugu", "తెలుగు", "Telugu", "te-IN"),
    "kn": Language("kn", "Kannada", "ಕನ್ನಡ", "Kannada", "kn-IN"),
    "ml": Language("ml", "Malayalam", "മലയാളം", "Malayalam", "ml-IN"),
    "pa": Language("pa", "Punjabi", "ਪੰਜਾਬੀ", "Gurmukhi", "pa-IN"),
    "or": Language("or", "Odia", "ଓଡ଼ିଆ", "Odia", "or-IN"),
    "ur": Language("ur", "Urdu", "اردو", "Arabic (Nastaliq)", "ur-IN"),
}

DEFAULT_LANGUAGE = LANGUAGES["en"]


def get_language(code: str) -> Language:
    """Never raises — an unknown code falls back to English rather than 500ing
    a chat request over a bad language field."""
    return LANGUAGES.get(code, DEFAULT_LANGUAGE)


def describe(code: str) -> str:
    """Human-readable language name for embedding in a prompt.

    >>> describe("gu")
    'Gujarati (ગુજરાતી), written in the Gujarati script'
    """
    lang = get_language(code)
    if lang.code == "en":
        return "English"
    return f"{lang.english_name} ({lang.native_name}), written in the {lang.script} script"


def output_language_rule(code: str) -> str:
    """The strong, unmissable language directive placed in the system prompt.

    Also tells the model to ignore the language of earlier turns: when the user
    switches the selector mid-conversation, the history is still in the old
    language, and recency bias otherwise drags the reply back to it.
    """
    lang = get_language(code)
    if lang.code == "en":
        return (
            "OUTPUT LANGUAGE: Write your entire reply in English.\n"
            "Earlier turns in this conversation may be in a different language — "
            "ignore their language completely and reply only in English."
        )

    return (
        f"OUTPUT LANGUAGE (highest priority): Write your ENTIRE reply in "
        f"{lang.english_name} ({lang.native_name}), using the {lang.script} script.\n"
        f"- Do NOT reply in English, and do NOT transliterate {lang.english_name} into "
        f"Latin/Roman letters — use real {lang.script} characters.\n"
        f"- This applies even if the user typed to you in English or in another language.\n"
        f"- Earlier turns in this conversation may be in a different language. Ignore "
        f"their language completely; only the instruction above decides your output language.\n"
        f"- Keep widely-recognised proper nouns (UPI, OTP, KYC, bank names) as-is, but "
        f"write everything around them in {lang.english_name}."
    )


def reply_reminder(code: str) -> str:
    """Short trailing reminder appended to the final user turn.

    Belt-and-braces: instructions at the very end of the context window are
    followed noticeably more reliably than ones buried in a long system prompt,
    especially once a few turns of history have accumulated.
    """
    lang = get_language(code)
    if lang.code == "en":
        return "[Reply in English.]"
    return f"[Reply in {lang.english_name} ({lang.native_name}), in the {lang.script} script.]"
