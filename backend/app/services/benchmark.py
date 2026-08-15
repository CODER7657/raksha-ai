"""Per-language benchmark over the shared rule corpus.

`testdata/rule_corpus.jsonl` is a labelled set, and the offline rule engine is
deterministic, so precision and recall for the offline safety net are computable
today — no agent layer and no LLM calls required. This is the data behind the
reviewer dashboard (#32 B), and the thing that turns #31 from a sentence in an
issue into a number somebody has to look at.

**Never aggregate across languages.** A single headline figure over twelve
languages hides that English has a dozen cases and Odia has none, and the
aggregate is then dominated by whichever language somebody happened to write
tests for. Every number here is per-language, and every number is returned with
the case count that produced it so a reader can see how much to trust it.

Scope: this measures the *offline rule engine*, which is the fallback that runs
when both LLM providers are down. It says nothing about the accuracy of the
RAG+LLM path, which is the primary judge. That benchmark needs the harness in
AGENT-BUILD-PLAN.md §09 item 1, and is not this.
"""

import json
import pathlib
from dataclasses import asdict, dataclass, field

from app.services.rule_engine import RESOLVED_RULES, REVIEW_STATUS, offline_rule_hits

CORPUS_PATH = (
    pathlib.Path(__file__).resolve().parents[3] / "testdata" / "rule_corpus.jsonl"
)

# Mirrors LanguageCode in app/routes/scan.py. Duplicated rather than imported so
# this module never pulls in FastAPI — the same call test_rule_corpus.py makes.
LANGUAGES = ("en", "hi", "gu", "mr", "bn", "ta", "te", "kn", "ml", "pa", "or", "ur")


@dataclass(frozen=True)
class LanguageBenchmark:
    """One language's slice. `precision` and `recall` are None rather than 0.0
    when undefined — no cases means "we do not know", and reporting 0.0 would
    read as "measured, and terrible", which is a different and false claim."""

    language: str
    has_rules: bool
    total_cases: int
    scam_cases: int
    benign_cases: int
    enforced_cases: int
    known_gap_cases: int
    true_positives: int
    false_negatives: int
    false_positives: int
    true_negatives: int
    exact_rule_matches: int
    precision: float | None
    recall: float | None
    # The scam cases that fired nothing. A recall figure tells a reviewer how
    # bad it is; these tell them what to fix. Corpus text is defanged test data
    # already in the repository, so surfacing it adds no exposure.
    #
    # A list rather than a tuple so the payload round-trips through JSON
    # unchanged — `frozen` protects the binding here, and the dict contents
    # were never deeply immutable anyway.
    missed_cases: list[dict] = field(default_factory=list)
    #: Benign cases a rule fired on. Mirrors the LLM half's field of the same
    #: name so the dashboard can render both with one component (#41).
    false_positive_cases: list[dict] = field(default_factory=list)


def load_corpus(path: pathlib.Path | None = None) -> list[dict]:
    source = path or CORPUS_PATH
    cases: list[dict] = []
    for line in source.read_text(encoding="utf-8").splitlines():
        if line.strip():
            cases.append(json.loads(line))
    return cases


def _ratio(numerator: int, denominator: int) -> float | None:
    if denominator == 0:
        return None
    return round(numerator / denominator, 4)


def score_language(language: str, cases: list[dict]) -> LanguageBenchmark:
    """Verdict-level scoring, matching what `label` means in the corpus README.

    A scam case counts as detected when *any* rule fires, not when the exact
    expected set does. That mirrors how the engine is actually consumed:
    `scan.py` degrades to a conservative warning if anything fired at all, so
    one right rule for a slightly wrong reason still protects the user. The
    stricter set-equality check is reported separately as `exact_rule_matches`,
    and is what the corpus test enforces."""
    mine = [c for c in cases if c["language"] == language]

    tp = fn = fp = tn = exact = 0
    missed: list[dict] = []
    false_positive_cases: list[dict] = []
    for case in mine:
        fired = sorted({hit.rule_id for hit in offline_rule_hits(case["text"], language)})
        if fired == sorted(case["expected_rule_ids"]):
            exact += 1

        if case["label"] == "scam":
            if fired:
                tp += 1
            else:
                fn += 1
                missed.append(
                    {
                        "id": case["id"],
                        "text": case["text"],
                        "expected_rule_ids": case["expected_rule_ids"],
                        "status": case["status"],
                        "note": case.get("note"),
                    }
                )
        else:
            if fired:
                fp += 1
                # Itemised for the same reason the LLM half itemises its own
                # (benchmark_llm.LlmLanguageBenchmark): over-warning is the
                # accepted failure direction, and "accepted" only means
                # something while we can name what is being warned about. A
                # precision figure alone cannot distinguish one odd edge case
                # from every bank alert in the country.
                false_positive_cases.append(
                    {
                        "id": case["id"],
                        "text": case["text"],
                        "fired_rule_ids": fired,
                        "note": case.get("note"),
                    }
                )
            else:
                tn += 1

    return LanguageBenchmark(
        language=language,
        # The load-bearing one for #31: a language with no rules at all falls
        # through to the English patterns, which cannot match native script.
        # RESOLVED_RULES, not RULES: Marathi has no rules of its own but
        # inherits Hindi's, and reporting it as uncovered would understate
        # coverage as badly as the reverse overstates it (#31).
        has_rules=bool(RESOLVED_RULES.get(language)),
        total_cases=len(mine),
        scam_cases=sum(1 for c in mine if c["label"] == "scam"),
        benign_cases=sum(1 for c in mine if c["label"] == "benign"),
        enforced_cases=sum(1 for c in mine if c["status"] == "enforced"),
        known_gap_cases=sum(1 for c in mine if c["status"] == "known_gap"),
        true_positives=tp,
        false_negatives=fn,
        false_positives=fp,
        true_negatives=tn,
        exact_rule_matches=exact,
        precision=_ratio(tp, tp + fp),
        recall=_ratio(tp, tp + fn),
        missed_cases=missed,
        false_positive_cases=false_positive_cases,
    )


def run(path: pathlib.Path | None = None) -> dict:
    """Every supported language, including the ones with no cases — an absent
    language must appear as a visible zero, not be missing from the report."""
    cases = load_corpus(path)
    languages = [asdict(score_language(code, cases)) for code in LANGUAGES]

    return {
        "languages": languages,
        "corpus": {
            "total_cases": len(cases),
            "languages_covered": sum(1 for lang in languages if lang["total_cases"] > 0),
            "languages_supported": len(LANGUAGES),
            "languages_with_rules": sorted(c for c in LANGUAGES if RESOLVED_RULES.get(c)),
            "languages_without_rules": sorted(
                c for c in LANGUAGES if not RESOLVED_RULES.get(c)
            ),
            # #31 closed the coverage gap but not the confidence gap: most
            # of these languages have rules no native speaker has read.
            # Reporting coverage without that would trade one comfortable
            # falsehood for another.
            "languages_unreviewed": sorted(
                c for c in LANGUAGES if REVIEW_STATUS.get(c) == "unreviewed"
            ),
        },
    }
