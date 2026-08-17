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
from dataclasses import dataclass
from typing import Any

from app.services.pattern_review import DECISIONS, REJECTION_REASONS

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


@dataclass(frozen=True)
class Gap:
    """A reason to draft for one language, and how well founded it is."""

    language: str
    #: `unmeasured` — no corpus to speak of, so no miss can be recorded.
    #: `measured`   — the benchmark ran and missed these.
    kind: str
    missed: int
    #: Carried so a reviewer can see that `ta: 2/2 missed` rests on two cases.
    #: A miss count without its denominator reads as a rate and is not one.
    #:
    #: `None` when the caller did not supply case counts, for the same reason
    #: `patterns` distinguishes unknown from zero: rendering "2 missed of 0
    #: cases" is nonsense presented as a measurement, and a reviewer deciding
    #: where to spend an hour should be able to tell it from a real denominator.
    cases: int | None
    patterns: int


def rank_gaps(
    missed_by_language: dict[str, list],
    *,
    corpus_cases: dict[str, int] | None = None,
    pattern_counts: dict[str, int] | None = None,
) -> list[Gap]:
    """Languages worth drafting for, strongest reason first.

    **Unmeasured gaps outrank measured ones**, and that reverses what this
    function did originally. Ranking on `missed_cases` alone looked principled
    and was structurally backwards:

        en 42   hi 14   gu 5   mr bn ta ur te kn ml pa or  2 each

    A language's miss count is ceilinged by its case count, so nine of twelve
    can never report more than two. Sorting by count therefore promotes English
    and Hindi permanently, regardless of how well they are served — and the nine
    at the bottom are exactly the ones with **no rows in the pattern corpus at
    all**, where retrieval returns nothing and the model judges unaided.

    That inverts this module's own argument. "Drafting where drafting is easy
    spends reviewers on languages that already work" is precisely what a
    miss-count ranking does, by a different route: it spends them on the
    languages that have a corpus, because having a corpus is what lets you
    record a miss.

    A rate would fix the ordering and inherit the blind spot. Recall of 1.000
    over two cases means the plumbing works, not that the vocabulary is right,
    and one case flipping moves a rate over that denominator by 0.5. So the
    ranking is on the gap that can be stated **without** a benchmark: no
    patterns is a stronger reason to draft than a measured miss, and it is
    knowable today.

    `pattern_counts` is passed in rather than read here. This module must not
    reach the pattern database — see `test_discovery_never_writes_to_the_pattern_database`
    — and taking the counts as an argument keeps that true while letting the
    caller supply them.

    **Absent `pattern_counts` means unknown, not zero.** Without it nothing is
    reported as unmeasured, whatever else was supplied: claiming a language has
    no pattern coverage when nobody looked is the confidently-wrong direction,
    and this function's output directs the scarcest resource in the project.
    """
    # Whether the counts were SUPPLIED, kept separate from what they contain.
    # `pattern_counts or {}` alone conflates "nobody told us" with "we looked and
    # there are none", and the consequence is not cosmetic: with `corpus_cases`
    # supplied and this absent, every language came back `unmeasured,
    # patterns=0` — English included, which has forty — and the order collapsed
    # back to miss count wearing a label that was false for the three languages
    # that are actually served.
    #
    # The same distinction `acceptance_rate` makes by returning None rather than
    # 0.0, and the trace makes with `language_covered: null` being a third state
    # rather than a falsy second.
    counts_known = pattern_counts is not None
    cases_known = corpus_cases is not None

    missed_by_language = missed_by_language or {}
    corpus_cases = corpus_cases or {}
    pattern_counts = pattern_counts or {}

    languages = set(missed_by_language) | set(corpus_cases) | set(pattern_counts)
    gaps: list[Gap] = []
    for language in languages:
        missed = len(missed_by_language.get(language) or [])
        patterns = pattern_counts.get(language, 0)
        cases = corpus_cases.get(language, 0) if cases_known else None

        if counts_known and patterns == 0:
            # Nothing to retrieve against. The strongest reason available, and
            # it needs no benchmark to state.
            gaps.append(Gap(language, "unmeasured", missed, cases, patterns))
        elif missed:
            gaps.append(Gap(language, "measured", missed, cases, patterns))

    # Unmeasured first; within each kind, more misses first, then by name so the
    # order is stable for a reviewer coming back to a queue.
    return sorted(
        gaps,
        key=lambda gap: (0 if gap.kind == "unmeasured" else 1, -gap.missed, gap.language),
    )


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


def _decided(decisions: dict[str, dict]) -> list[dict]:
    """Drafts a human has ruled on, in any direction.

    Reads `pattern_review.DECISIONS` rather than restating it. The tuple was
    written out twice here — once in `acceptance_rate` and once in `report` —
    and neither copy was the definition. A fourth decision state would have made
    a draft in it leave the numerator AND the denominator, so it would stop
    being counted rather than being counted wrong, which is far harder to notice
    in a rate.

    A module whose whole argument is that a closed vocabulary makes the loop
    safe should be reading the closed vocabulary.
    """
    return [
        record for record in (decisions or {}).values()
        if record.get("decision") in DECISIONS
    ]


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
    decided = _decided(decisions)
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
    decided = _decided(decisions)
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
