"""Property-based tests for the offline rule engine (roadmap §2.3 item 2).

Example tests pin the cases someone thought of; these state what must hold for
*every* input and let Hypothesis look for a counterexample. 200 examples per
property, derandomised so CI is reproducible.

The engine has no numeric score: its output is the set of rules that fired, and
the scan route turns any non-empty set into a conservative verdict. So "risk
never goes down" is stated on that set: adding text can add rules, never remove
one. The module's contract (it only flags, never clears) is exactly this.
"""

import string

from hypothesis import given, settings
from hypothesis import strategies as st

from app.services import trace
from app.services.benchmark import load_corpus
from app.services.rule_engine import RESOLVED_RULES, REVIEW_STATUS, offline_rule_hits

PROPERTY_SETTINGS = settings(max_examples=200, deadline=None, derandomize=True)

CORPUS = load_corpus()
SCAMS = [row for row in CORPUS if row["label"] == "scam"]
ENGLISH_ROWS = [row for row in CORPUS if row["language"] == "en"]
LANGUAGES = sorted(REVIEW_STATUS)

DEVANAGARI_DIGITS = str.maketrans("0123456789", "०१२३४५६७८९")
GUJARATI_DIGITS = str.maketrans("0123456789", "૦૧૨૩૪૫૬૭૮૯")

rows = st.sampled_from(CORPUS)
scam_rows = st.sampled_from(SCAMS)
# Filler without newlines, joined to a message with one: no rule's gap crosses a
# newline (`_GAP` and `_GAP_ACROSS` both exclude it), so the property is about
# the engine, not about two halves accidentally forming a new phrase.
filler = st.text(st.characters(blacklist_characters="\n\r"), min_size=20, max_size=300)


def fired(text: str, language: str) -> set[str]:
    return {hit.rule_id for hit in offline_rule_hits(text, language)}


def test_the_corpus_gives_the_properties_something_to_bite_on():
    """A property over rows that fire nothing would pass vacuously."""
    firing = [row for row in SCAMS if fired(row["text"], row["language"])]
    assert len(firing) >= 40


# --- Monotonicity: more text never means fewer warnings ---------------------


@PROPERTY_SETTINGS
@given(row=scam_rows, before=filler, after=filler)
def test_surrounding_text_never_removes_a_fired_rule(row, before, after):
    language = row["language"]
    alone = fired(row["text"], language)
    wrapped = fired(f"{before}\n{row['text']}\n{after}", language)
    assert alone <= wrapped


@PROPERTY_SETTINGS
@given(first=rows, second=rows)
def test_joining_two_messages_keeps_every_rule_either_fired(first, second):
    language = first["language"]
    joined = fired(f"{first['text']}\n{second['text']}", language)
    assert fired(first["text"], language) | fired(second["text"], language) <= joined


# --- Total and well-formed on any input -------------------------------------


@PROPERTY_SETTINGS
@given(text=st.text(max_size=500), language=st.sampled_from(LANGUAGES + ["xx", ""]))
def test_any_text_in_any_language_yields_well_formed_hits(text, language):
    hits = offline_rule_hits(text, language)

    ids = [hit.rule_id for hit in hits]
    assert len(ids) == len(set(ids)), "a rule is reported once"

    allowed = {rule.rule_id for rule in RESOLVED_RULES.get(language, []) + RESOLVED_RULES["en"]}
    for hit in hits:
        assert hit.rule_id in allowed
        assert hit.matched_text in text, "the evidence is a real substring"


@PROPERTY_SETTINGS
@given(text=st.text(max_size=300), language=st.sampled_from(LANGUAGES))
def test_the_engine_is_deterministic(text, language):
    assert offline_rule_hits(text, language) == offline_rule_hits(text, language)


@PROPERTY_SETTINGS
@given(text=st.text(max_size=300))
def test_an_unknown_language_falls_back_to_english_rules(text):
    assert fired(text, "xx") == fired(text, "en")


# --- Invariances: same message, different surface ---------------------------


@PROPERTY_SETTINGS
@given(row=rows, digits=st.sampled_from([DEVANAGARI_DIGITS, GUJARATI_DIGITS]))
def test_indian_digit_scripts_do_not_change_detection(row, digits):
    """A Hindi or Gujarati SMS may write the amount or OTP in its own digits.
    No rule keys on a digit, so detection must not depend on the script used."""
    language = row["language"]
    assert fired(row["text"].translate(digits), language) == fired(row["text"], language)


@PROPERTY_SETTINGS
@given(row=st.sampled_from(ENGLISH_ROWS), flips=st.lists(st.booleans(), min_size=1))
def test_ascii_case_does_not_change_english_detection(row, flips):
    text = row["text"]
    mutated = "".join(
        (ch.swapcase() if flips[i % len(flips)] else ch) if ch in string.ascii_letters else ch
        for i, ch in enumerate(text)
    )
    assert fired(mutated, "en") == fired(text, "en")


# --- The community-counter normaliser ---------------------------------------


@PROPERTY_SETTINGS
@given(text=st.text(max_size=300))
def test_normalisation_is_idempotent(text):
    once = trace._normalise(text)
    assert trace._normalise(once) == once


@PROPERTY_SETTINGS
@given(text=st.text(string.ascii_letters + string.digits + " .,!?", max_size=200))
def test_forwarded_variants_share_a_digest(text):
    """Re-forwarding adds whitespace and shouting; the counter must not split."""
    assert trace.hash_text(f"  {text.upper()}\n") == trace.hash_text(text)


def test_digest_folds_devanagari_digits():
    """Was a strict xfail (known gap); hash_text folds digit scripts since 2026-11-08."""
    assert trace.hash_text("OTP 452189") == trace.hash_text("OTP ४५२१८९")
