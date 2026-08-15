"""The evasion queue's lifecycle.

The behaviour worth pinning is not "can it read JSON". It is the three rules
that make the queue trustworthy: closure is measured rather than asserted, an
evasion is only resolved by the detector it was found against, and a fix with
nothing pinning it is reported rather than assumed safe.
"""

import json

import pytest

from app.services import evasion_queue as queue


def evasion(id_="ev-1", status="open", detector="rules", text="Share the OTP", **extra):
    return {
        "seed_id": "en-kyc-001",
        "strategy": "paraphrase",
        "language": "en",
        "text": text,
        "verdict": "safe",
        "risk_score": 0,
        "rules_fired": [],
        "judge_reason": "same fraud",
        "fingerprint": "abc123def456",
        "detector": detector,
        "id": id_,
        "status": status,
        "first_seen": "2026-08-15",
        "resolution": None,
        **extra,
    }


def catches_everything(text, language):
    return {"verdict": "high_risk"}


def catches_nothing(text, language):
    return {"verdict": "safe"}


# --- reading -------------------------------------------------------------


def test_rows_written_before_the_lifecycle_still_load(tmp_path):
    """The first three entries predate this module. Refusing to load them would
    make the fix for a missing lifecycle a queue nobody can open."""
    path = tmp_path / "evasions.jsonl"
    legacy = {
        "seed_id": "s",
        "strategy": "paraphrase",
        "language": "en",
        "text": "t",
        "verdict": "safe",
        "risk_score": 0,
        "rules_fired": [],
        "judge_reason": "r",
        "fingerprint": "0123456789abcdef",
    }
    path.write_text(json.dumps(legacy) + "\n", encoding="utf-8")

    loaded = queue.load(path)[0]
    assert loaded["status"] == queue.OPEN
    assert loaded["id"] == "ev-0123456789ab"
    assert loaded["resolution"] is None


def test_a_missing_queue_is_empty_not_an_error(tmp_path):
    assert queue.load(tmp_path / "nothing.jsonl") == []


def test_round_trip_preserves_records(tmp_path):
    path = tmp_path / "evasions.jsonl"
    queue.save([evasion(), evasion(id_="ev-2")], path)
    assert [r["id"] for r in queue.load(path)] == ["ev-1", "ev-2"]


# --- closure is measured, not asserted -----------------------------------


def test_verify_closes_an_evasion_the_detector_now_catches():
    records, changed = queue.verify([evasion()], catches_everything)

    assert records[0]["status"] == queue.FIXED
    assert changed == [records[0]]
    assert records[0]["resolution"]["how"] == "verify", (
        "a closure has to say whether it was measured or asserted"
    )
    assert "high_risk" in records[0]["resolution"]["note"]


def test_verify_leaves_a_still_evading_record_open():
    records, changed = queue.verify([evasion()], catches_nothing)
    assert records[0]["status"] == queue.OPEN
    assert changed == []


def test_verify_does_not_touch_already_closed_records():
    """Re-closing a fixed record would overwrite the note and date on the
    original closure, losing when and how it was actually resolved."""
    original = queue.resolve(
        evasion(), queue.FIXED, how="human", note="closed by hand", on="2026-01-01"
    )
    records, changed = queue.verify([original], catches_everything)

    assert changed == []
    assert records[0]["resolution"]["at"] == "2026-01-01"
    assert records[0]["resolution"]["how"] == "human"


def test_an_evasion_is_only_resolved_by_the_detector_it_was_found_against():
    """The rules layer is what runs on the phone with no network. The full
    pipeline catching something the rules miss does not close the rules gap —
    that is exactly the confusion `--detector rules` exists to prevent."""
    rules_evasion = evasion(detector="rules")
    records, changed = queue.verify([rules_evasion], catches_everything, detector="full")

    assert changed == [], "a full-pipeline run must not close a rules evasion"
    assert records[0]["status"] == queue.OPEN


def test_wontfix_is_never_reachable_by_verify():
    """A machine can observe that something is caught. It cannot decide that a
    gap is not worth chasing — that is a judgement about our users."""
    records, _ = queue.verify([evasion()], catches_everything)
    assert records[0]["status"] != queue.WONTFIX


def test_resolve_rejects_an_unknown_status():
    with pytest.raises(ValueError, match="unknown status"):
        queue.resolve(evasion(), "probably-fine", how="human")


def test_resolve_does_not_mutate_the_original():
    original = evasion()
    queue.resolve(original, queue.FIXED, how="verify")
    assert original["status"] == queue.OPEN


# --- a fix with nothing holding it in place ------------------------------


def test_a_fixed_evasion_with_no_corpus_row_is_reported():
    """Closing an evasion without adding a case means the bug can return and
    nothing notices — the queue would keep saying `fixed` about a live defect."""
    fixed = queue.resolve(evasion(text="Share the numeric code"), queue.FIXED, how="verify")
    assert queue.unpinned([fixed], corpus=[]) == [fixed]


def test_a_fixed_evasion_whose_text_is_in_the_corpus_is_pinned():
    fixed = queue.resolve(evasion(text="Share the numeric code"), queue.FIXED, how="verify")
    corpus = [{"text": "share the   NUMERIC code"}]  # whitespace and case differ
    assert queue.unpinned([fixed], corpus) == []


def test_an_explicit_corpus_id_counts_as_pinned():
    fixed = queue.resolve(
        evasion(), queue.FIXED, how="verify", corpus_id="en-code-word-numeric-001"
    )
    assert queue.unpinned([fixed], corpus=[]) == []


def test_open_records_are_not_reported_as_unpinned():
    assert queue.unpinned([evasion()], corpus=[]) == []


# --- what a reviewer sees before opening it ------------------------------


def test_summary_counts_every_status_including_the_empty_ones():
    """A queue reporting only what it has is a queue that looks alarming the
    day it is empty of one category and silent the day it fills."""
    records = [
        evasion(id_="a"),
        queue.resolve(evasion(id_="b"), queue.FIXED, how="verify"),
        queue.resolve(evasion(id_="c"), queue.WONTFIX, how="human", note="too rare"),
    ]
    assert queue.summary(records) == {"open": 1, "fixed": 1, "wontfix": 1}
    assert queue.summary([]) == {"open": 0, "fixed": 0, "wontfix": 0}
