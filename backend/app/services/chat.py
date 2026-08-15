"""RAG-grounded conversational assistant. Same Groq-primary/Gemini-fallback
ladder as app/services/llm.py, but returns free-form text for a back-and-forth
conversation instead of a forced-JSON single classification.

The model ids are imported from `llm` rather than repeated here. They used to be
literal strings, and that is how this module kept a dead `gemini-1.5-flash` after
#45 fixed the one next door: the fallback was retired in one file and left
running in another, so the chat assistant had no second rung at all while the
scanner had two. A constant cannot drift from itself.

The ladder itself is still duplicated, because `llm.complete()` takes a single
system and user prompt while a conversation needs the whole turn history. Worth
unifying when that shape is worked out; the model ids should not wait for it.
"""

import logging

from app.core import languages
from app.core.config import get_settings
from app.services.llm import GEMINI_MODEL, GROQ_MODEL

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are the Raksha AI Assistant — a friendly, patient safety \
helper for first-time digital banking users in India. Your job is to help people \
understand scams, digital banking safety, UPI safety, and what to do if they've \
already been scammed.

Rules:
- Write in plain, simple words — assume no technical background. Your output \
language is fixed by the "OUTPUT LANGUAGE" instruction below; follow it exactly, \
regardless of what language the user typed in.
- Ground your answer in the "Known scam patterns" context below when it's relevant \
to the question, but you are not limited to it — answer novel questions sensibly too.
- Be concrete: give one or two practical next steps, not vague warnings.
- If someone says they already shared an OTP/PIN/card details, treat it as urgent: \
tell them to immediately call their bank's official helpline / block the card via \
the bank app, and never to share anything further with whoever contacted them.
- You are not a financial/investment/legal advisor — if asked for that, say so \
briefly and redirect to scam-safety topics you can actually help with.
- If the question is completely unrelated to scams/fraud/digital banking safety, \
politely say that's outside what you can help with and steer back on topic.
- Keep replies short: 2-5 sentences, unless the user is asking for a step-by-step \
"what do I do now" answer, then a short numbered list is fine.
- Never ask the user for their OTP, PIN, password, or card details yourself.
- When writing in a language with grammatical gender on verbs/adjectives (Hindi, \
Gujarati, Marathi, Punjabi, Urdu, etc.), address the reader using neutral \
imperative/infinitive verb forms that don't require guessing their gender, and \
stay consistent throughout the reply — it may be read aloud by text-to-speech, \
which should sound like one consistent voice, not switch gender mid-reply.
"""


def _build_messages(message: str, language: str, context_block: str, history: list[dict]) -> list[dict]:
    system = f"{SYSTEM_PROMPT}\n\n{languages.output_language_rule(language)}\n\n{context_block}"
    messages = [{"role": "system", "content": system}]
    for turn in history:
        messages.append({"role": turn["role"], "content": turn["content"]})
    # The reminder rides on the final user turn rather than a second system
    # message: it lands at the very end of the context for both providers, and
    # _call_gemini would otherwise coerce a trailing system role into "user".
    messages.append({"role": "user", "content": f"{message}\n\n{languages.reply_reminder(language)}"})
    return messages


def _call_groq(messages: list[dict]) -> str:
    from groq import Groq

    settings = get_settings()
    client = Groq(api_key=settings.groq_api_key)
    completion = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=messages,
        temperature=0.4,
        max_tokens=400,
    )
    return completion.choices[0].message.content


def _call_gemini(messages: list[dict]) -> str:
    import google.generativeai as genai

    settings = get_settings()
    genai.configure(api_key=settings.gemini_api_key)

    system_content = messages[0]["content"]
    turns = messages[1:]

    gemini_history = [
        {"role": "model" if turn["role"] == "assistant" else "user", "parts": [turn["content"]]}
        for turn in turns[:-1]
    ]
    last_message = turns[-1]["content"]

    model = genai.GenerativeModel(
        GEMINI_MODEL,
        system_instruction=system_content,
        generation_config={"max_output_tokens": 400},
    )
    chat = model.start_chat(history=gemini_history)
    response = chat.send_message(last_message)
    return response.text


def chat_reply(message: str, language: str, context_block: str, history: list[dict]) -> str:
    messages = _build_messages(message, language, context_block, history)

    try:
        return _call_groq(messages).strip()
    except Exception:
        # Fall through to Gemini. Logged rather than swallowed silently: if Groq
        # is failing every request we degrade to the slower provider and nothing
        # anywhere says why.
        logger.warning("Groq chat call failed, falling back to Gemini", exc_info=True)

    try:
        return _call_gemini(messages).strip()
    except Exception as exc:
        raise RuntimeError("Both Groq and Gemini failed") from exc
