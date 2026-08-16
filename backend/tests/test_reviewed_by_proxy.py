"""`reviewed-by-proxy` — a review by someone who does not speak the language.

`testdata/review/ur-rule-review-devanagari.md` (#100) transliterates every Urdu
rule word into Devanagari so a Hindi speaker can read it. Hindi and Urdu are one
spoken language in two scripts, so that works — and it works least well exactly
where they diverge, which the sheet marks.

That produces a claim `REVIEW_STATUS` had no value for. It is stronger than
`unreviewed`: somebody with relevant linguistic access read the rules and gave a
judgement. It is weaker than `in-service`: they are not a speaker of the
language.

These tests pin the two properties that make the fourth value honest rather than
a promotion — that it is reported distinguishably, and that it can never quietly
become a native review.
"""

import pathlib

import pytest

from app.services import trace as trace_service
from app.services.rule_engine import REVIEW_STATUS, REVIEW_VIA, SCRIPT_INHERITANCE

RULE_ENGINE = pathlib.Path(__file__).resolve().parents[1] / "app/services/rule_engine.py"


# --- the vocabulary -------------------------------------------------------


def test_the_status_vocabulary_is_closed_and_documented():
    """A fifth value appearing without a docstring entry is how `unreviewed`
    stops meaning anything."""
    documented = {"in-service", "inherited", "reviewed-by-proxy", "unreviewed"}
    assert set(REVIEW_STATUS.values()) <= documented

    source = RULE_ENGINE.read_text(encoding="utf-8")
    for value in documented:
        assert value in source, f"{value} is not explained in rule_engine.py"


def test_every_proxy_reviewed_language_says_which_language_it_went_through():
    """`reviewed-by-proxy` with no `REVIEW_VIA` entry is an unfalsifiable claim
    — it asserts somebody reviewed it and declines to say how."""
    for language, status in REVIEW_STATUS.items():
        if status == "reviewed-by-proxy":
            assert language in REVIEW_VIA, (
                f"{language} is reviewed-by-proxy but REVIEW_VIA does not say "
                f"through which language"
            )


def test_a_proxy_review_never_points_at_itself():
    for language, via in REVIEW_VIA.items():
        assert via != language, f"{language} cannot be a proxy for itself"
        assert REVIEW_STATUS.get(via) == "in-service", (
            f"{language} is reviewed via {via}, which is not itself in-service — "
            f"a proxy review through unreviewed rules proves nothing"
        )


# --- the property that stops it becoming a promotion ----------------------


def test_proxy_is_not_native(monkeypatch):
    """The load-bearing one. Two proxy reviews are not a native one, and there
    is no path from `reviewed-by-proxy` to `in-service` except a speaker of the
    language reading the rules.

    Asserted rather than trusted to review, because the reasoning that gets
    someone there — "it has been read twice now, surely that counts" — is
    exactly the reasoning that arrives when the eighth language is the last one
    left and everyone is tired.
    """
    monkeypatch.setitem(REVIEW_STATUS, "ur", "reviewed-by-proxy")
    monkeypatch.setitem(REVIEW_VIA, "ur", "hi")

    review = trace_service.rule_review("ur")

    assert review["status"] == "reviewed-by-proxy"
    assert review["native_reviewed"] is False, (
        "a proxy review must never report as a native one"
    )
    assert review["reviewed_via"] == "hi"


def test_a_proxy_review_is_distinguishable_from_no_review(monkeypatch):
    """The failure this field exists to prevent: if a proxy-reviewed language
    read identically to an unreviewed one, the review would be invisible — which
    is the exact problem `REVIEW_STATUS` was added to solve, in a new place."""
    unreviewed = trace_service.rule_review("ta")

    monkeypatch.setitem(REVIEW_STATUS, "ur", "reviewed-by-proxy")
    monkeypatch.setitem(REVIEW_VIA, "ur", "hi")
    proxied = trace_service.rule_review("ur")

    assert proxied != unreviewed
    assert (proxied["status"], proxied["reviewed_via"]) != (
        unreviewed["status"],
        unreviewed["reviewed_via"],
    )


# --- kept separate from inheritance ---------------------------------------


def test_inheritance_and_proxy_review_are_different_claims():
    """`inherited_from` says whose rules these are. `reviewed_via` says who read
    them and through what. Marathi borrowing Hindi's rules involves no human at
    all; a Hindi speaker reading transliterated Urdu is a person making a
    judgement."""
    marathi = trace_service.rule_review("mr")

    assert marathi["inherited_from"] == "hi"
    assert marathi["reviewed_via"] is None, (
        "inheriting a rule set is not a review, and must not report as one"
    )
    assert marathi["native_reviewed"] is False


def test_inherited_from_is_read_from_the_table_not_hardcoded(monkeypatch):
    """`hi` is the only parent today. A second one was previously reported as
    Hindi regardless, because the value was a literal."""
    monkeypatch.setitem(SCRIPT_INHERITANCE, "bn", "en")
    monkeypatch.setitem(REVIEW_STATUS, "bn", "inherited")

    assert trace_service.rule_review("bn")["inherited_from"] == "en"


@pytest.mark.parametrize("language", sorted(REVIEW_STATUS))
def test_reviewed_via_is_null_for_every_language_that_is_not_proxied(language):
    if REVIEW_STATUS[language] != "reviewed-by-proxy":
        assert trace_service.rule_review(language)["reviewed_via"] is None
