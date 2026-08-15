"""The A1 draft queue (#32 A).

This queue is part of the security design, not admin UI: the pattern database
is what detection reasons against, so what a reviewer is shown determines what
gets in. These cover the parts where being wrong is quiet — a stale hint, or an
inability to tell "nothing similar exists" from "we could not check".
"""

import json

import pytest

from app.services import pattern_review


def write_drafts(tmp_path, rows):
    path = tmp_path / "drafts.jsonl"
    path.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8"
    )
    return path


def draft(**overrides):
    base = {
        "id": "draft-en-0001",
        "language": "en",
        "pattern_text": "Share the OTP or your account will be blocked",
        "category": "account_lock",
        "source": "a1:run-1",
        "drafted_by": "machine",
        "created_at": "2026-08-15T09:00:00Z",
        "status": "pending",
        "decision": None,
        "note": None,
    }
    return {**base, **overrides}


def test_missing_queue_is_empty_not_an_error(tmp_path):
    assert pattern_review.load_drafts(tmp_path / "absent.jsonl") == []


def test_only_pending_drafts_are_queued(tmp_path):
    rows = [
        draft(id="a", status="pending"),
        draft(id="b", status="accepted"),
        draft(id="c", status="rejected"),
        draft(id="d", status="pending"),
    ]
    drafts = pattern_review.load_drafts(write_drafts(tmp_path, rows))

    assert [d["id"] for d in pattern_review.pending(drafts)] == ["a", "d"]


def test_decided_drafts_are_kept_not_deleted(tmp_path):
    """Rejections are training data for whoever tunes A1 — a deleted row
    teaches nothing."""
    rows = [draft(id="a", status="rejected", decision={"by": "hem", "at": "x", "reason": "duplicate"})]
    drafts = pattern_review.load_drafts(write_drafts(tmp_path, rows))

    assert len(drafts) == 1
    assert drafts[0]["decision"]["reason"] == "duplicate"


def test_rule_response_is_computed_from_the_live_engine():
    """Free and deterministic, unlike a benchmark-impact figure. A draft the
    rules already catch is a different decision from one they miss."""
    fired = pattern_review.rule_response(draft())
    assert "otp_share" in fired
    assert "account_lock" in fired


def test_rule_response_is_empty_when_nothing_fires():
    quiet = draft(pattern_text="Your parcel will arrive on Tuesday")
    assert pattern_review.rule_response(quiet) == []


def test_review_card_survives_retrieval_being_down(monkeypatch):
    """A queue that cannot be triaged because retrieval is unavailable is worse
    than one triaged without the near-duplicate hint."""
    monkeypatch.setattr(
        pattern_review, "neighbours_for", _raise(RuntimeError("embeddings unavailable"))
    )
    card = pattern_review.review_card(draft())

    assert card["neighbours"] is None
    # The rest of the card must still be usable.
    assert card["pattern_text"]
    assert card["rule_response"]


def test_null_neighbours_is_distinct_from_empty(monkeypatch):
    """`[]` means nothing similar exists; `null` means we could not check. A
    reviewer reading the second as the first would accept a duplicate believing
    it had been checked."""
    monkeypatch.setattr(pattern_review, "neighbours_for", lambda *_a, **_k: [])
    assert pattern_review.review_card(draft())["neighbours"] == []

    monkeypatch.setattr(pattern_review, "neighbours_for", _raise(RuntimeError("down")))
    assert pattern_review.review_card(draft())["neighbours"] is None


def test_near_duplicate_flag_is_stated_not_inferred(monkeypatch):
    """The reviewer should not have to eyeball a decimal to spot a duplicate."""
    from app.services.rag import RetrievedPattern

    monkeypatch.setattr(
        pattern_review.rag,
        "retrieve_similar_patterns",
        lambda *_a, **_k: [
            RetrievedPattern("almost exactly this", "account_lock", 0.97),
            RetrievedPattern("something else", "kyc_scam", 0.61),
        ],
    )
    neighbours = pattern_review.neighbours_for(draft())

    assert neighbours[0].near_duplicate is True
    assert neighbours[1].near_duplicate is False


def test_the_seeded_queue_is_well_formed():
    """Guards the committed seed file, not a fixture — a malformed row would
    show up as a blank card rather than an error."""
    drafts = pattern_review.load_drafts()
    assert drafts, "the seeded queue should not be empty"

    required = {"id", "language", "pattern_text", "category", "source", "drafted_by", "status"}
    ids = set()
    for row in drafts:
        assert required <= row.keys(), f"{row.get('id')} is missing fields"
        assert row["status"] in pattern_review.STATUSES
        assert row["id"] not in ids, f"duplicate draft id {row['id']}"
        ids.add(row["id"])


def test_the_seed_covers_both_provenances_and_an_rtl_script():
    """C wants machine-drafted distinguishable from hand-written, and the queue
    must render Urdu without it arriving left-to-right."""
    drafts = pattern_review.load_drafts()
    assert {d["drafted_by"] for d in drafts} == {"machine", "human"}
    assert any(d["language"] == "ur" for d in drafts)


def _raise(exc):
    def _fn(*_args, **_kwargs):
        raise exc

    return _fn


@pytest.mark.parametrize("status", pattern_review.STATUSES)
def test_status_vocabulary_is_closed(status):
    assert status in ("pending", "accepted", "rejected")
