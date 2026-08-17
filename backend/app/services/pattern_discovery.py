"""A1 — drafting scam patterns, ranked by what we actually miss. #115 §4.

Everything downstream already exists. The review queue landed in #60, the
near-duplicate check with it, and #87 added an append-only decision store that
promotes an accepted draft with an approver the database enforces.
`pattern_drafts.jsonl` is **eight hand-written rows and nothing generates
more** — so the gate is real and the thing it gates is a fixture. This is the
missing half.

## Ranked by what we miss

Both benchmarks report `missed_cases` per language. Drafting wherever drafting
is easy spends the scarcest resource in this project — reviewer attention — on
languages that already work. #32 treats reviewer throughput as a security
property, and this is where that begins.

## Learning from rejections, and only there

#87's rejection vocabulary is closed: `duplicate`, `not_a_scam`, `too_broad`,
`wrong_language`, `low_quality`, `low_value`. **That is why it is closed rather
than free text.** Six values are a training signal a generator can act on; six
thousand sentences are not, and free text arriving from a review queue is
untrusted input on its way into a prompt.

**The loop learns at proposing, never at deciding.** A fraud detector that
updates itself without a human is a larger attack surface with a nicer story,
and `AGENT-LAYER.md` §03 names the consequence exactly: an attacker who gets a
pattern approved teaches the system that their scam is safe. So rejection
history shapes the next draft and touches nothing about how any draft is judged.
Nothing here writes to `scam_patterns` or records a decision, and two tests
assert that against the source rather than trusting review.

## The measure

**Acceptance rate, not draft count.** A generator nobody accepts from is noise
with a schedule, and draft count is precisely the number that would make it look
productive. `revoked` counts against acceptance: a revoked pattern was accepted
and then found wrong, and excluding it would let a generator score well by
producing plausible drafts that later degrade every verdict silently.
"""

from __future__ import annotations

import logging
from typing import Any

from app.services.pattern_review import REJECTION_REASONS

logger = logging.getLogger(__name__)

#: What each closed rejection reason should change about the next draft.
#:
#: Keyed by the vocabulary rather than accepting whatever a reviewer typed —
#: a reason arriving from outside this mapping is dropped, because the queue is
#: a place text arrives from and this text is on its way into a prompt.
_LESSONS: dict[str, str] = {
    "duplicate": (
        "Previous drafts were rejected as duplicates. Check the existing "
        "patterns first and propose only what is not already covered."
    ),
    "not_a_scam": (
        "Previous drafts were rejected because the source material was misread. "
        "Draft only from text that is actually attempting fraud."
    ),
    "too_broad": (
        "Previous drafts were rejected as too broad — they would match "
        "legitimate messages. Prefer the specific pretext over the general shape."
    ),
    "wrong_language": (
        "Previous drafts were rejected for script or language mismatch. Write "
        "the pattern in the language and script it is meant to detect."
    ),
    "low_quality": (
        "Previous drafts were rejected as garbled or unusable as written. "
        "Produce text a speaker would recognise as a real message."
    ),
    "low_value": (
        "Previous drafts were rejected as real but too rare to be worth a "
        "retrieval slot. Prefer scams that arrive at volume."
    ),
}


def rank_gaps(missed_by_language: dict[str, list]) -> list[tuple[str, int]]:
    """Languages worth drafting for, worst first.

    Ordered by how many cases the benchmark actually missed, not alphabetically
    and not by how easy drafting happens to be. A language we miss nothing in is
    omitted entirely — drafting there spends a reviewer to learn nothing.

    An empty benchmark proposes nothing. No measurement is not the same as no
    gap, and inventing work from an absent benchmark fills the queue with drafts
    nobody can justify.
    """
    gaps = [
        (language, len(missed))
        for language, missed in (missed_by_language or {}).items()
        if missed
    ]
    return sorted(gaps, key=lambda pair: (-pair[1], pair[0]))


def rejection_lessons(decisions: dict[str, dict], language: str) -> list[str]:
    """What previous rejections in this language should change.

    Per language on purpose: `too_broad` in Tamil says nothing about Hindi, and
    pooling them would teach the generator to avoid a mistake it never made
    there.

    Only the closed vocabulary is used. A reason outside it is dropped rather
    than passed through — the review queue is a place text arrives from, and
    this text is on its way into a prompt.
    """
    seen: list[str] = []
    for record in (decisions or {}).values():
        if record.get("decision") != "rejected":
            continue
        if record.get("language") != language:
            continue
        reason = record.get("reason")
        if reason not in REJECTION_REASONS:
            # Includes None and anything free-form. Not an error worth raising —
            # a malformed decision should cost a lesson, not a run.
            continue
        lesson = _LESSONS[reason]
        if lesson not in seen:
            seen.append(lesson)
    return seen


def acceptance_rate(decisions: dict[str, dict]) -> float | None:
    """Accepted over decided, or None when nothing has been decided.

    **Pending drafts are excluded.** They are not evidence in either direction,
    and counting them as failures would make a fresh queue look like a broken
    generator.

    **`revoked` counts against.** A revoked pattern was accepted and then found
    wrong; excluding it would let a generator score well by producing plausible
    drafts that later degrade every verdict. `revoked` exists because that
    failure is silent (§03), which is the same reason it belongs in this number.

    None rather than 0.0 for an empty set: zero and unknown are different
    claims, and reporting zero for a queue nobody has reviewed blames the
    generator for a reviewer backlog.
    """
    decided = [
        record for record in (decisions or {}).values()
        if record.get("decision") in ("accepted", "rejected", "revoked")
    ]
    if not decided:
        return None
    accepted = sum(1 for record in decided if record.get("decision") == "accepted")
    return accepted / len(decided)


def report(decisions: dict[str, dict]) -> dict[str, Any]:
    """What a run says about itself.

    Deliberately does **not** carry a draft count. #115 §4: *"the measure is
    acceptance rate, not draft count"* — and draft count is exactly the number
    that makes a generator nobody accepts from look productive.
    """
    rate = acceptance_rate(decisions)
    decided = [
        record for record in (decisions or {}).values()
        if record.get("decision") in ("accepted", "rejected", "revoked")
    ]
    return {
        "acceptance_rate": rate,
        "decided": len(decided),
        # Named individually so a poor rate can be read as what it is. "12
        # rejected, 9 of them duplicates" is actionable; "acceptance 0.2" is a
        # score, and #76 is the standing argument for naming rather than
        # counting.
        "rejections_by_reason": {
            reason: sum(
                1 for record in decided
                if record.get("decision") == "rejected" and record.get("reason") == reason
            )
            for reason in REJECTION_REASONS
        },
    }
