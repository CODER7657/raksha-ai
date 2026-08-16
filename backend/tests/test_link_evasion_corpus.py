"""A6 against A2 stage 1, as a corpus rather than a claim.

#115: *"Point A6 at every detector you build. If it can mutate past your checks,
that is a benchmark case before it is a production gap."*

`testdata/link_evasions.jsonl` is that benchmark. Each row is one known
URL-evasion technique applied to the same underlying fraud — a phishing link
aimed at an Indian bank or wallet customer. The seed is the first row; every
other row is a mutation of it that a real scammer could plausibly send.

## Why this run was deterministic

A6's LLM loop (`redteam.py`) needs `llm.BATCH`, and `GROQ_API_KEY_BATCH` was
unset. `llm._keys_for` does not fail on that — it **warns and falls back to the
interactive pool**, which is the pool live scans use and exactly the failure
#51 and #59 exist for. So the model half of this pass was not run.

For a detector whose every check is deterministic, that is a smaller loss than
it sounds. A systematic sweep of known techniques is reproducible, free, and
exhaustive over what it covers, where a model samples. The model half is still
worth running for the mutations nobody thought to enumerate — `detect_links` in
`redteam.py` registers this detector so the existing loop can be pointed at it
the moment a batch key exists. That run has not happened and this file does not
claim it has.

## The number

First run: **20 of 31 caught, 11 evaded.** After fixing what the evasions
exposed: **29 of 31**. The 11 were not 11 bugs — several were one bug wearing
different hats, and one of them disproved a claim written in `link_signals.py`'s
own docstring about which direction its public-suffix approximation erred in.

## The two that still evade

They are marked `known_gap` in the corpus with a reason, and they are marked
that way because fixing them costs more than the gap does — not because they are
hard. A brand name in a URL *path* would flag every news article and review site
that names a bank. A2's benign half is larger than its phishing half, and that
one belongs to the stages that read the page, where "a Paytm login form on a
domain that is not Paytm" is evidence instead of a guess.

**The count of known gaps may not grow without an edit here.** That is the point
of pinning it: a gap acquired by accident and a gap accepted on purpose look
identical in a pass rate.
"""

import json
import pathlib

import pytest

from app.services import link_signals

CORPUS = pathlib.Path(__file__).resolve().parents[2] / "testdata" / "link_evasions.jsonl"

#: Raised only by a deliberate edit, alongside a documented reason in the row.
EXPECTED_KNOWN_GAPS = 2


def _rows() -> list[dict]:
    with CORPUS.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


ROWS = _rows()


def test_the_corpus_is_not_empty_and_is_well_formed():
    assert ROWS
    for row in ROWS:
        assert set(row) >= {"id", "technique", "url", "expect", "note"}
        assert row["expect"] in {"caught", "known_gap"}


@pytest.mark.parametrize("row", [r for r in ROWS if r["expect"] == "caught"], ids=lambda r: r["id"])
def test_each_caught_technique_stays_caught(row):
    """A regression here means a mutation that used to be detected now walks
    through — which is a production gap, not a test failure."""
    signals = link_signals.evaluate(row["url"])
    assert signals, f"{row['id']} ({row['technique']}) evaded: {row['url']}"


@pytest.mark.parametrize(
    "row", [r for r in ROWS if r["expect"] == "known_gap"], ids=lambda r: r["id"]
)
def test_each_known_gap_states_why_it_is_accepted(row):
    """An unexplained known gap is indistinguishable from an unnoticed one."""
    assert row["note"].strip(), f"{row['id']} is a known gap with no reason recorded"


def test_the_number_of_accepted_gaps_does_not_drift():
    """False positives named, not counted (#76) — and the same for gaps. A pass
    rate that quietly reclassifies a failure as expected is how a benchmark
    stops measuring anything."""
    gaps = [r for r in ROWS if r["expect"] == "known_gap"]
    assert len(gaps) == EXPECTED_KNOWN_GAPS, (
        f"{len(gaps)} known gaps, expected {EXPECTED_KNOWN_GAPS}. If this is "
        f"deliberate, raise EXPECTED_KNOWN_GAPS and say why in the row's note."
    )


def test_the_reported_rate_matches_what_actually_happens():
    """The docstring above claims 29 of 31. This checks the claim rather than
    trusting it — a number in a comment rots the first time somebody edits the
    corpus."""
    caught = sum(1 for row in ROWS if link_signals.evaluate(row["url"]))
    assert caught == len(ROWS) - EXPECTED_KNOWN_GAPS
