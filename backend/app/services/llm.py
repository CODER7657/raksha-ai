"""LLM classification, grounded by RAG context. Groq is primary (fast, free
tier, good Llama models); Gemini is the fallback if Groq errors or is
rate-limited — this avoids a single point of failure on a free API key
during the live demo.
"""

import json

from app.core import languages
from app.core.config import get_settings

SYSTEM_PROMPT = """You are a financial-fraud detection assistant for first-time \
digital banking users in India. You will be given a message (SMS/WhatsApp/call \
transcript) and a list of known scam patterns retrieved from a reference database.

Use the known patterns as grounding context, but judge the actual message on its \
own merits — it may be a novel scam not in the database, or genuinely safe.

When writing in a language with grammatical gender on verbs/adjectives (Hindi, \
Gujarati, Marathi, Punjabi, Urdu, etc.), address the reader directly using \
imperative/infinitive verb forms that don't require picking a gender (e.g. Hindi \
"संपर्क करें" not "करो"/"करी", Gujarati "સંપર્ક કરો" as a neutral imperative) — never \
guess or vary the reader's gender between sentences, since a message read aloud by \
text-to-speech should sound like one consistent voice, not switch mid-explanation.

Respond with ONLY a JSON object, no markdown, no extra text, in this exact shape:
{
  "risk_score": <int 0-100>,
  "verdict": "safe" | "suspicious" | "high_risk",
  "flagged_phrases": [<exact substrings from the message that triggered concern>],
  "explanation": <one or two plain-language sentences, in the requested language, \
explaining WHY, understandable by someone with no technical background>,
  "recommended_action": <one concrete next step, in the requested language>
}
"""


def _build_user_prompt(message: str, language: str, context_block: str) -> str:
    lang = languages.get_language(language)
    return (
        f"{languages.output_language_rule(language)}\n"
        f'This applies to the "explanation" and "recommended_action" fields — the JSON '
        f'keys and the "verdict" value stay in English, and "flagged_phrases" must be '
        f"copied verbatim from the message in its original language.\n\n"
        f"{context_block}\n\n"
        f'Message to analyze:\n"""{message}"""\n\n'
        f"[Write explanation and recommended_action in {lang.english_name} "
        f"({lang.native_name}), in the {lang.script} script.]"
    )


def _call_groq(system_prompt: str, user_prompt: str) -> str:
    from groq import Groq

    settings = get_settings()
    client = Groq(api_key=settings.groq_api_key)
    completion = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.2,
        response_format={"type": "json_object"},
    )
    return completion.choices[0].message.content


def _call_gemini(system_prompt: str, user_prompt: str) -> str:
    import google.generativeai as genai

    settings = get_settings()
    genai.configure(api_key=settings.gemini_api_key)
    model = genai.GenerativeModel(
        "gemini-1.5-flash",
        system_instruction=system_prompt,
        generation_config={"response_mime_type": "application/json"},
    )
    response = model.generate_content(user_prompt)
    return response.text


def classify_message(message: str, language: str, context_block: str) -> dict:
    user_prompt = _build_user_prompt(message, language, context_block)

    raw: str | None = None
    try:
        raw = _call_groq(SYSTEM_PROMPT, user_prompt)
    except Exception:
        raw = None

    if raw is None:
        try:
            raw = _call_gemini(SYSTEM_PROMPT, user_prompt)
        except Exception as exc:
            raise RuntimeError("Both Groq and Gemini failed") from exc

    result = json.loads(raw)
    _validate_result_shape(result)
    return result


def _validate_result_shape(result: dict) -> None:
    required = {
        "risk_score",
        "verdict",
        "flagged_phrases",
        "explanation",
        "recommended_action",
    }
    missing = required - result.keys()
    if missing:
        raise ValueError(f"LLM response missing fields: {missing}")
    if result["verdict"] not in {"safe", "suspicious", "high_risk"}:
        raise ValueError(f"Invalid verdict: {result['verdict']}")
    if not (0 <= int(result["risk_score"]) <= 100):
        raise ValueError(f"risk_score out of range: {result['risk_score']}")
