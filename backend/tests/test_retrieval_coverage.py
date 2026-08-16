"""Whether a verdict was grounded at all (#88).

Nine of the twelve supported languages have zero rows in `scam_patterns`, so
retrieval returns nothing and the model judges unaided. Until now that produced
the same response shape as a grounded English scan, and told the model — in
words — that a corpus had been searched and come back empty.

The distinction is available for free, and these tests are what keep it sound:
`match_scam_patterns` applies no similarity floor, so an empty result means the
language has nothing to retrieve rather than nothing close. If someone adds a
floor to that SQL, `test_retrieval_has_no_similarity_floor` fails and says what
else has to change.
"""

import pathlib
import re

from app.services import rag
from app.services import trace as trace_service
from app.services.rag import RetrievedPattern

MIGRATIONS = pathlib.Path(__file__).resolve().parents[2] / "supabase/migrations"


def pattern(similarity: float, text: str = "Share your OTP") -> RetrievedPattern:
    return RetrievedPattern(
        pattern_text=text,
        category="otp_scam",
        similarity=similarity,
        provenance="human",
        drafted_by=None,
    )


# --- the invariant the whole inference rests on ---------------------------


def test_retrieval_has_no_similarity_floor():
    """`language_is_covered` reads an empty result as "this language has no
    patterns". That is only true while the SQL returns top-k unfiltered.

    Asserted against the live definition — the most recent migration that
    creates the function — rather than against a copy, because the copy is what
    would go stale.
    """
    definitions = sorted(
        p for p in MIGRATIONS.glob("*.sql")
        if "create function public.match_scam_patterns" in p.read_text(encoding="utf-8")
    )
    assert definitions, "no migration defines match_scam_patterns"

    latest = definitions[-1].read_text(encoding="utf-8")
    body = latest[latest.index("create function public.match_scam_patterns"):]
    body = body[: body.index("$$;")]

    # A floor would look like `where ... similarity > x` or `1 - (...) > x`.
    assert not re.search(r"similarity\s*[><]", body), (
        "match_scam_patterns now filters on similarity. rag.language_is_covered "
        "infers 'this language has no patterns' from an empty result, and that "
        "inference is no longer sound — an empty result could now mean 'nothing "
        "cleared the floor'. Rewrite it before shipping this."
    )
    assert "limit match_count" in body, (
        "match_scam_patterns no longer takes a plain top-k; re-check the "
        "empty-result inference in rag.language_is_covered"
    )


# --- the three outcomes, told apart ---------------------------------------


def test_an_uncovered_language_says_so_to_the_model():
    """The bug this closes. An empty corpus was described as 'no closely
    matching patterns were found', which offers absence of evidence to the model
    as evidence of absence — on exactly the languages we have least right to be
    confident about."""
    block = rag.format_context_block([])

    assert "NO reference scam patterns" in block
    assert "gap in our data" in block
    assert "do not treat the absence of matches as evidence that it is safe" in block.lower()


def test_a_covered_language_with_no_close_match_is_a_real_signal():
    block = rag.format_context_block([pattern(0.10)])

    assert "none were" in block and "similar" in block
    assert "NO reference scam patterns" not in block, (
        "a language with patterns must not be described as having none"
    )


def test_close_matches_reach_the_prompt():
    block = rag.format_context_block([pattern(0.91), pattern(0.10)])

    assert "Known scam patterns similar to this message" in block
    assert "0.91" in block
    assert "0.10" not in block, "a weak match must not be offered as evidence"


# --- the trace tells the same story ---------------------------------------


def test_the_trace_records_an_uncovered_language():
    trace = trace_service.build_trace([], [], None)

    assert trace["retrieval"]["language_covered"] is False
    assert trace["retrieval"]["patterns_retrieved"] == 0
    assert trace["retrieval"]["patterns_used"] == 0


def test_the_trace_separates_retrieved_from_used():
    """Five retrieved of which none cleared the floor is a different verdict
    from five retrieved and five used, and `retrieved_patterns` lists both
    kinds without distinguishing them."""
    trace = trace_service.build_trace([], [pattern(0.91), pattern(0.10), pattern(0.05)], None)

    assert trace["retrieval"]["language_covered"] is True
    assert trace["retrieval"]["patterns_retrieved"] == 3
    assert trace["retrieval"]["patterns_used"] == 1


def test_a_cached_trace_does_not_claim_the_language_is_uncovered():
    """Retrieval did not run, so coverage was never established. Reporting
    False would assert the #88 gap on a scan that never looked — the same class
    of error as replaying patterns that were not retrieved."""
    trace = trace_service.build_trace_from_cache([], "groq", "llama", "2026-08-16T00:00:00Z")

    assert trace["retrieval"]["language_covered"] is None
    assert trace["retrieval"]["skipped"] == "cache_hit"


# --- and so does the audit record -----------------------------------------


def test_the_audit_payload_records_whether_the_verdict_was_grounded():
    trace = trace_service.build_trace([], [], None)
    payload = trace_service.build_audit_payload(
        input_hash="abc",
        language="ta",
        input_type="text",
        verdict="suspicious",
        risk_score=60,
        trace=trace,
    )

    assert payload["retrieval_language_covered"] is False, (
        "an auditor asking whether a six-month-old verdict was grounded cannot "
        "reconstruct it from the pattern table, because the corpus will have grown"
    )


def test_the_benchmark_reports_how_many_cases_were_grounded():
    """#76 scored nine languages at precision 1.000 against a retrieval step
    that returned nothing, and the report had no way to say so. A 1.000 over two
    cases with an empty corpus is not the same number as 0.933 over forty-two
    with one, and it should not sit in the same column unannotated."""
    from app.services.benchmark_llm import score_language

    covered = ({"id": "a", "label": "scam", "text": "t"}, {
        "verdict": "high_risk", "risk_score": 90, "leaked": False, "retrieval_covered": True,
    })
    uncovered = ({"id": "b", "label": "scam", "text": "t"}, {
        "verdict": "high_risk", "risk_score": 90, "leaked": False, "retrieval_covered": False,
    })

    assert score_language("en", [covered, covered]).grounded_cases == 2
    assert score_language("ta", [uncovered, uncovered]).grounded_cases == 0
    assert score_language("hi", [covered, uncovered]).grounded_cases == 1


def test_an_older_record_without_the_field_counts_as_ungrounded():
    """Reports predate this field. Absent must not read as grounded — that is
    the direction that overstates what was measured."""
    from app.services.benchmark_llm import score_language

    legacy = ({"id": "a", "label": "scam", "text": "t"}, {
        "verdict": "high_risk", "risk_score": 90, "leaked": False,
    })
    assert score_language("en", [legacy]).grounded_cases == 0


def test_the_audit_payload_preserves_not_established():
    cached = trace_service.build_trace_from_cache([], "groq", "llama", None)
    payload = trace_service.build_audit_payload(
        input_hash="abc",
        language="ta",
        input_type="text",
        verdict="safe",
        risk_score=5,
        trace=cached,
    )

    assert payload["retrieval_language_covered"] is None, (
        "None must survive into the chain rather than flattening to False"
    )
