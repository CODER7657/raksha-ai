"""LLM classification, grounded by RAG context. Groq is primary (fast, free
tier, good Llama models); Gemini is the fallback if Groq errors or is
rate-limited — this avoids a single point of failure on a free API key
during the live demo.
"""

import json
import logging
import random
import time
from dataclasses import dataclass

from app.core import languages
from app.core.config import get_settings

logger = logging.getLogger(__name__)

#: Which key pool a call draws on. See Settings for why there are two.
INTERACTIVE = "interactive"
BATCH = "batch"

#: Attempts per pool. Interactive gets exactly one: a person is waiting, often
#: mid-scam, and falling to the next provider immediately beats making them sit
#: through a backoff. Batch retries, because nobody is waiting and a loop that
#: dies on a rate limit throws away every call it already paid for.
_ATTEMPTS = {INTERACTIVE: 1, BATCH: 3}

GROQ_MODEL = "llama-3.3-70b-versatile"
# `gemini-1.5-flash` was retired and now 404s, which had quietly left the
# fallback dead — see the note on `classify_message`. Pinned to an exact
# version rather than the `gemini-flash-latest` alias on purpose: an
# auto-advancing model would move verdicts underneath a stamped
# PROMPT_VERSION, and reproducing a six-month-old decision is the whole reason
# the stamp exists (ARCHITECTURE.md §03).
GEMINI_MODEL = "gemini-2.5-flash"

# Bump whenever SYSTEM_PROMPT or _build_user_prompt changes in a way that could
# move a verdict. Without it, a decision made six months ago cannot be
# reproduced or defended, because the prompt will have moved underneath it —
# see ARCHITECTURE.md §03.
PROMPT_VERSION = "scan-v1"

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


def keys_for(pool: str) -> tuple[str, str]:
    """(groq, gemini) for this pool.

    Batch falls back to the interactive keys when its own are unset, with a
    warning rather than silently — a fresh clone with one key should still be
    able to run the benchmark, but nobody should be surprised later about which
    quota an agent spent.
    """
    settings = get_settings()
    if pool == BATCH:
        groq = settings.groq_api_key_batch
        gemini = settings.gemini_api_key_batch
        if not (groq or gemini):
            logger.warning(
                "No batch API keys set; batch work is drawing on the interactive "
                "pool and can rate-limit live scans. Set GROQ_API_KEY_BATCH."
            )
            return settings.groq_api_key, settings.gemini_api_key
        return groq or settings.groq_api_key, gemini or settings.gemini_api_key
    return settings.groq_api_key, settings.gemini_api_key


def _is_rate_limited(error: Exception) -> bool:
    text = str(error).lower()
    return "429" in text or "rate limit" in text or "resource_exhausted" in text


def _call_groq(system_prompt: str, user_prompt: str, pool: str = INTERACTIVE) -> str:
    from groq import Groq

    client = Groq(api_key=keys_for(pool)[0])
    completion = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.2,
        response_format={"type": "json_object"},
    )
    return completion.choices[0].message.content


def _call_gemini(system_prompt: str, user_prompt: str, pool: str = INTERACTIVE) -> str:
    import google.generativeai as genai

    genai.configure(api_key=keys_for(pool)[1])
    model = genai.GenerativeModel(
        GEMINI_MODEL,
        system_instruction=system_prompt,
        generation_config={"response_mime_type": "application/json"},
    )
    response = model.generate_content(user_prompt)
    return response.text


@dataclass(frozen=True)
class Classification:
    """A verdict plus the identity of whatever produced it. The stamp travels
    with the verdict into the audit record, so which provider answered — the
    primary or the fallback — is recoverable later."""

    result: dict
    provider: str
    model: str
    prompt_version: str = PROMPT_VERSION


@dataclass(frozen=True)
class Completion:
    """Raw model output plus which provider produced it."""

    text: str
    provider: str
    model: str


def complete(system_prompt: str, user_prompt: str, pool: str = INTERACTIVE) -> Completion:
    """The Groq-primary, Gemini-fallback ladder, for any prompt.

    Public so that callers with a different job — the red-team agent, an
    evaluation harness — use the same ladder instead of reaching for
    `_call_groq`. The ladder is the part worth sharing: duplicating it would
    mean a Groq outage degrades one caller gracefully and breaks another.

    Note this returns text and does not parse it. Only `classify_message` knows
    what shape its answer must be, and validating someone else's schema here
    would make this function lie about what it does.
    """
    last_error: Exception | None = None

    for attempt in range(_ATTEMPTS.get(pool, 1)):
        if attempt:
            # Only reachable on the batch pool. Jittered so two agents started
            # by the same cron do not retry in lockstep and re-limit each other.
            delay = min(2**attempt, 8) + random.uniform(0, 1)
            logger.info("Both providers rate-limited, retrying in %.1fs", delay)
            time.sleep(delay)

        try:
            return Completion(
                _call_groq(system_prompt, user_prompt, pool), "groq", GROQ_MODEL
            )
        except Exception as error:
            # Logged, not swallowed. If Groq is failing every request we quietly
            # degrade to the slower fallback for every scan, and without this
            # line nothing anywhere says why. Same reasoning as ruff.toml.
            logger.warning("Groq call failed, falling back to Gemini", exc_info=True)
            last_error = error

        try:
            return Completion(
                _call_gemini(system_prompt, user_prompt, pool), "gemini", GEMINI_MODEL
            )
        except Exception as error:
            last_error = error
            # Retrying only helps a rate limit. A dead model or a bad key will
            # fail identically three times, and sleeping through that just makes
            # the error slower to arrive.
            if not _is_rate_limited(error):
                break

    # The cause has to survive. "Both Groq and Gemini failed" reads like a
    # provider outage, which is how a retired model id sat unnoticed for weeks
    # (#45, #56) — the 404 was never written down anywhere.
    #
    # `exc_info=last_error` rather than `logger.exception()`: this runs after the
    # retry loop, outside any `except`, where `exception()` would helpfully log
    # "NoneType: None" and throw away the very cause this line exists to keep.
    # Hem's test in #45 caught exactly that when I restructured this.
    logger.error("Gemini fallback failed as well", exc_info=last_error)
    raise RuntimeError("Both Groq and Gemini failed") from last_error


def classify_message(
    message: str, language: str, context_block: str, pool: str = INTERACTIVE
) -> Classification:
    """Groq first, Gemini second.

    Both failures are logged. They used to be swallowed, and that is how the
    fallback came to be dead without anyone noticing: `gemini-1.5-flash` was
    retired, every fallback attempt 404'd, and the only visible symptom was the
    combined "Both Groq and Gemini failed" — which reads like a provider outage
    rather than a model id we needed to change. A two-provider ladder whose
    second rung fails silently is a one-provider ladder that looks like two.
    """
    user_prompt = _build_user_prompt(message, language, context_block)
    completion = complete(SYSTEM_PROMPT, user_prompt, pool)

    result = json.loads(completion.text)
    _validate_result_shape(result)
    return Classification(
        result=result, provider=completion.provider, model=completion.model
    )


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
