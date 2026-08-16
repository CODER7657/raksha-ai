"""A2's labelled corpus — precision and recall, and where they come from.

`testdata/link_evasions.jsonl` asks *"can a mutation get past the checks?"*.
This asks the other question: **on a realistic mix, how often are we right, and
what do we get wrong?**

Its own file rather than rows added to `rule_corpus.jsonl`, per review of #121:
that corpus is the specification for the two rule engines and is held by both
parity suites, so link rows would trigger the Kotlin engine for no reason. A2
needs labelled URLs *with context*, which is a different artefact.

## The benign half is larger, and it is the work

47 benign against 22 phishing. Anyone can write twenty phishing URLs; writing
forty-seven benign ones that our own checks find suspicious is the part that
makes the precision number mean anything. Every benign row is a place we could
warn about a legitimate site during a fraud alert, which is us causing the harm
the product exists to prevent.

**All 47 benign domains were verified to resolve** over WHOIS — they are real
sites, not plausible-sounding inventions.

The phishing half is deliberately **invented shapes, not live URLs**. A
repository of working phishing targets is not something to ship, and #121
established that an unresolvable domain cannot be used to benchmark
`domain_age`; every phishing row records `resolves: false` so nobody tries.

## Four labels, because "benign" and "silent" are not the same thing

    silent       benign, and nothing should fire
    weak_signal  benign, and something correctly fires — a shortener really
                 does hide its destination, `.xyz` really is a cheap TLD. True
                 statements that are not evidence of fraud
    caught       phishing, and at least one signal fires
    known_gap    phishing, and nothing fires, with the reason recorded

Collapsing `weak_signal` into a false positive would push us to delete correct
signals. Collapsing it into a pass would hide a real cost. It is neither.

## Measured at the time of writing

    recall     0.864   19/22 phishing caught
    precision  0.826   19 true of 23 flagged
    floored    0/47    benign rows reaching the verdict floor

**The last number is the one that matters.** Precision counts every signal;
the floor is what actually changes what a user sees. Four benign rows carry a
true weak signal and not one of them reaches two independent bases, so none can
turn a `safe` verdict into `suspicious`. That is the floor's calibration
measured rather than argued.
"""

import json
import pathlib

import pytest

from app.services import link_signals

CORPUS = pathlib.Path(__file__).resolve().parents[2] / "testdata" / "link_corpus.jsonl"

#: Raised only by a deliberate edit. See `known_gap` rows for the reasons.
EXPECTED_KNOWN_GAPS = 3

#: Recall floor. Below this something has regressed; above it, raise the floor.
MIN_RECALL = 0.80

#: Precision floor. Counts `weak_signal` rows against us on purpose — they are a
#: real cost even though the signals are true.
MIN_PRECISION = 0.75

ROWS = [json.loads(line) for line in CORPUS.read_text(encoding="utf-8").splitlines() if line.strip()]
BENIGN = [r for r in ROWS if r["label"] == "benign"]
PHISHING = [r for r in ROWS if r["label"] == "phishing"]


def _signals(row: dict) -> list:
    return link_signals.evaluate(row["url"])


def _would_floor(row: dict) -> bool:
    """The rule from #126 — restated rather than imported so this file measures
    the policy rather than one implementation of it."""
    signals = _signals(row)
    if any(s.name == "known_bad_feed" for s in signals):
        return True
    return link_signals.independent_witnesses(signals) >= 2 and any(
        s.deterministic for s in signals
    )


# --- the corpus itself -----------------------------------------------------


def test_the_benign_half_is_larger_than_the_phishing_half():
    """Not a style preference. A2's benign set is larger in the world, and a
    corpus weighted the other way would report a precision number that flatters
    us on the half that does not cost users."""
    assert len(BENIGN) > len(PHISHING)


def test_every_row_is_well_formed():
    for row in ROWS:
        assert set(row) >= {"id", "label", "url", "context", "shape", "resolves", "expect", "note"}
        assert row["label"] in {"benign", "phishing"}
        assert row["expect"] in {"silent", "weak_signal", "caught", "known_gap"}
        assert row["context"].strip(), f"{row['id']} has no context — a URL alone loses the pretext"


def test_every_benign_domain_is_a_real_one():
    """Verified over WHOIS when the corpus was built. A benign half made of
    invented domains would measure our imagination, not our precision."""
    assert all(r["resolves"] is True for r in BENIGN)


def test_no_phishing_row_claims_to_be_a_live_url():
    """#121: an unresolvable domain cannot be used to benchmark `domain_age`,
    and shipping working phishing targets is not something to do either."""
    assert all(r["resolves"] is False for r in PHISHING)


def test_every_weak_signal_and_known_gap_records_why():
    for row in ROWS:
        if row["expect"] in {"weak_signal", "known_gap"}:
            assert row["note"].strip(), f"{row['id']} is {row['expect']} with no reason recorded"


# --- per row ---------------------------------------------------------------


@pytest.mark.parametrize("row", [r for r in BENIGN if r["expect"] == "silent"], ids=lambda r: r["id"])
def test_a_benign_site_expected_to_be_silent_stays_silent(row):
    """The half that costs users. Each failure here is a real site we would warn
    about — named, not counted (#76)."""
    fired = [s.name for s in _signals(row)]
    assert not fired, f"{row['id']} ({row['shape']}) fired {fired} on {row['url']}"


@pytest.mark.parametrize("row", [r for r in PHISHING if r["expect"] == "caught"], ids=lambda r: r["id"])
def test_a_phishing_url_expected_to_be_caught_stays_caught(row):
    assert _signals(row), f"{row['id']} ({row['shape']}) now evades: {row['url']}"


# --- the numbers -----------------------------------------------------------


def test_recall_does_not_regress():
    caught = sum(1 for r in PHISHING if _signals(r))
    assert caught / len(PHISHING) >= MIN_RECALL


def test_precision_does_not_regress():
    caught = sum(1 for r in PHISHING if _signals(r))
    flagged_benign = sum(1 for r in BENIGN if _signals(r))
    assert caught / (caught + flagged_benign) >= MIN_PRECISION


def test_no_benign_site_ever_reaches_the_verdict_floor():
    """The tightest constraint in this file, and the number that matters more
    than precision.

    Precision counts every signal. The floor is what actually changes what a
    user is shown. A benign row carrying one true weak signal costs nothing; a
    benign row reaching two independent bases turns a `safe` verdict into
    `suspicious` on a real bank.
    """
    floored = [r["id"] for r in BENIGN if _would_floor(r)]
    assert not floored, f"benign rows would be floored to non-safe: {floored}"


def test_the_number_of_accepted_gaps_does_not_drift():
    gaps = [r for r in PHISHING if r["expect"] == "known_gap"]
    assert len(gaps) == EXPECTED_KNOWN_GAPS, (
        f"{len(gaps)} known gaps, expected {EXPECTED_KNOWN_GAPS}. If deliberate, "
        f"raise EXPECTED_KNOWN_GAPS and say why in the row's note."
    )
