"""Are the model ids we depend on still real?

`gemini-1.5-flash` was retired and every fallback attempt 404'd for an unknown
number of weeks. Nothing caught it, because nothing ever called it: Groq almost
never fails, so the second rung was only reached under load — and when it finally
was, the only symptom was "Both Groq and Gemini failed", which reads like an
outage rather than a model id that needed changing.

Unit tests cannot catch this. A retired model is only observable by calling the
API, and mocking the call is exactly what hides it. So this is a live check, run
on a schedule and before demos, not part of the test suite.

## The distinction this script exists to make

    404 / NOT_FOUND      the model is gone. Code change required. ALERT.
    429 / rate limited   working as intended under load. Not a failure.
    401 / 403            the key is wrong or revoked. ALERT.
    timeout / 5xx        their problem, probably transient. Warn, do not alert.

A check that alerts on 429 gets muted within a week, and a muted check is worse
than none — which is the same failure mode as `pytest || true` in #22. So a rate
limit is reported and passes.

Exit code is 0 unless something needs a human: a dead model or a bad key.
"""

import argparse
import pathlib
import sys
from dataclasses import dataclass

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from app.core.config import get_settings
from app.services import llm

#: Trivial prompts. The point is whether the endpoint answers at all, not
#: whether the answer is any good, so keep the token cost near zero.
_SYSTEM = "Reply with JSON only."
_USER = 'Return exactly {"ok": true}'


@dataclass
class Result:
    name: str
    status: str  # ok | rate_limited | dead | unauthorized | degraded | skipped
    detail: str = ""

    @property
    def needs_a_human(self) -> bool:
        return self.status in {"dead", "unauthorized"}


def classify_error(error: Exception) -> tuple[str, str]:
    """Map a provider exception onto one of our states.

    Matches on the message rather than exception type on purpose: three SDKs
    raise three different hierarchies, and every one of them puts the status
    code in the string. A type-based match would need updating whenever a
    provider bumps its client — which is the same maintenance trap that let the
    dead model sit unnoticed.
    """
    text = str(error)
    lowered = text.lower()
    first_line = text.splitlines()[0][:160] if text else type(error).__name__

    if "404" in text or "not found" in lowered or "no longer available" in lowered:
        return "dead", first_line
    if "429" in text or "rate limit" in lowered or "quota" in lowered or "resource_exhausted" in lowered:
        return "rate_limited", first_line
    if "401" in text or "403" in text or "api key" in lowered or "unauthorized" in lowered:
        return "unauthorized", first_line
    return "degraded", first_line


def check(name: str, call) -> Result:
    try:
        call()
    except Exception as error:
        # Broad on purpose: three provider SDKs raise three unrelated
        # exception hierarchies, and the point here is to survive all of
        # them and report, not to enumerate them.
        status, detail = classify_error(error)
        return Result(name, status, detail)
    return Result(name, "ok")


def check_groq() -> Result:
    if not get_settings().groq_api_key:
        return Result("groq (primary)", "skipped", "GROQ_API_KEY not set")
    return check("groq (primary)", lambda: llm._call_groq(_SYSTEM, _USER))


def check_gemini() -> Result:
    if not get_settings().gemini_api_key:
        return Result("gemini (fallback)", "skipped", "GEMINI_API_KEY not set")
    return check("gemini (fallback)", lambda: llm._call_gemini(_SYSTEM, _USER))


def check_embeddings() -> Result:
    """RAG dies quietly without this — retrieval returns nothing, the prompt
    loses its grounding context, and verdicts get worse with no error anywhere."""
    if not get_settings().gemini_api_key:
        return Result("gemini embeddings (RAG)", "skipped", "GEMINI_API_KEY not set")
    from app.services.embeddings import embed

    return check("gemini embeddings (RAG)", lambda: embed("smoke test", "retrieval_query"))


CHECKS = [check_groq, check_gemini, check_embeddings]

_SYMBOL = {
    "ok": "OK  ",
    "rate_limited": "LIMIT",
    "skipped": "SKIP",
    "degraded": "WARN",
    "dead": "DEAD",
    "unauthorized": "AUTH",
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--strict",
        action="store_true",
        help="also fail on degraded (5xx/timeout), for use before a demo",
    )
    args = parser.parse_args()

    print("Provider smoke check — one trivial call per rung\n")
    results = [fn() for fn in CHECKS]

    for result in results:
        line = f"  [{_SYMBOL[result.status]:<5}] {result.name}"
        if result.detail:
            line += f"\n           {result.detail}"
        print(line)

    dead = [r for r in results if r.needs_a_human]
    degraded = [r for r in results if r.status == "degraded"]
    limited = [r for r in results if r.status == "rate_limited"]

    print()
    if dead:
        print("ACTION REQUIRED — these need a code or credential change, not a retry:")
        for result in dead:
            print(f"  {result.name}: {result.status}")
        print("\nIf a model is dead, check the provider's current model list and update")
        print("the pinned id in app/services/llm.py. Do not switch to a `-latest` alias:")
        print("an auto-advancing model moves verdicts underneath a stamped PROMPT_VERSION.")
        return 1

    if limited:
        print("Rate limited, which is not a failure — the ladder is working as designed.")
    if degraded and args.strict:
        print("Degraded providers, and --strict was passed.")
        return 1
    if degraded:
        print("Some providers are degraded (probably transient). Not failing.")

    if all(r.status == "ok" for r in results):
        print("Every rung answered.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
