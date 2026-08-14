"""The shared corpus, enforced against the Python engine.

`testdata/rule_corpus.jsonl` is the specification; this file is one of its two
consumers (the Kotlin port in #28 is the other). See `testdata/README.md`.

The design decision worth knowing: `known_gap` rows are checked **strictly**, in
both directions. A documented defect that quietly starts working fails the build
and asks whoever fixed it to update the corpus. That is deliberate — closing a
gap should be a visible edit to the specification, not a silent change in
behaviour discovered later when the numbers move.
"""

import json
import pathlib

import pytest

from app.services.rule_engine import RULES, offline_rule_hits

CORPUS = pathlib.Path(__file__).resolve().parents[2] / "testdata" / "rule_corpus.jsonl"

# Mirrors LanguageCode in app/routes/scan.py. Duplicated rather than imported so
# that importing this test never pulls in FastAPI and the whole route module.
LANGUAGES = {"en", "hi", "gu", "mr", "bn", "ta", "te", "kn", "ml", "pa", "or", "ur"}

KNOWN_RULE_IDS = {
    "otp_share",
    "kyc_expiry",
    "account_lock",
    "lottery_win",
    "refund_click",
    "urgent_verify",
}


def load_corpus() -> list[dict]:
    cases = []
    for lineno, line in enumerate(CORPUS.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            cases.append(json.loads(line))
        except json.JSONDecodeError as exc:
            pytest.fail(f"{CORPUS.name} line {lineno} is not valid JSON: {exc}")
    return cases


CASES = load_corpus()


def fired(case: dict) -> list[str]:
    return sorted({hit.rule_id for hit in offline_rule_hits(case["text"], case["language"])})


def ids(cases: list[dict]) -> list[str]:
    return [case["id"] for case in cases]


def test_corpus_is_not_empty():
    assert CASES, f"no cases loaded from {CORPUS}"


@pytest.mark.parametrize("case", CASES, ids=ids(CASES))
def test_case_is_well_formed(case):
    """A malformed row is worse than a missing one: it looks like coverage."""
    for field in ("id", "language", "label", "status", "text", "expected_rule_ids", "source"):
        assert field in case, f"missing field {field!r}"

    assert case["language"] in LANGUAGES, f"unknown language {case['language']!r}"
    assert case["label"] in {"scam", "benign"}, f"unknown label {case['label']!r}"
    assert case["status"] in {"enforced", "known_gap"}, f"unknown status {case['status']!r}"
    assert isinstance(case["expected_rule_ids"], list)
    assert case["text"].strip(), "empty text"

    unknown = set(case["expected_rule_ids"]) - KNOWN_RULE_IDS
    assert not unknown, (
        f"unknown rule id(s) {sorted(unknown)}. Ids are concept-level and shared "
        f"across languages, and double as i18n keys (trace.rules.*) — reuse an "
        f"existing id rather than inventing one."
    )

    if case["label"] == "benign":
        assert case["expected_rule_ids"] == [], "a benign case expects no rule to fire"


def test_ids_are_unique():
    seen = [case["id"] for case in CASES]
    duplicates = {i for i in seen if seen.count(i) > 1}
    assert not duplicates, f"duplicate case ids: {sorted(duplicates)}"


ENFORCED = [c for c in CASES if c["status"] == "enforced"]
GAPS = [c for c in CASES if c["status"] == "known_gap"]


@pytest.mark.parametrize("case", ENFORCED, ids=ids(ENFORCED))
def test_enforced_case_matches(case):
    assert fired(case) == sorted(case["expected_rule_ids"]), case.get("note") or case["id"]


@pytest.mark.parametrize("case", GAPS, ids=ids(GAPS))
def test_known_gap_still_fails(case):
    """Strict, so fixing a gap is forced to be a visible edit to the corpus."""
    assert fired(case) != sorted(case["expected_rule_ids"]), (
        f"{case['id']} is marked known_gap but now produces the expected rules. "
        f"If you fixed it, change status to 'enforced' in testdata/rule_corpus.jsonl "
        f"— and if it was a false positive, this is the row that proves it is gone."
    )


def test_every_supported_language_has_rules():
    """#31: nine of twelve languages have no offline rules, so a scam in those
    languages fires nothing — and scan.py raises 503 rather than degrading to a
    warning when both LLM providers are down.

    Marked xfail rather than skipped so it flips to a failure the moment #31 is
    fixed, which is the signal to delete this marker."""
    missing = sorted(LANGUAGES - set(RULES))
    if missing:
        pytest.xfail(f"no offline rules for: {', '.join(missing)} (#31)")
    assert not missing
