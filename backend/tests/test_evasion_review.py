"""The evasion review queue (#41 §3).

Two things carry real risk here. One, the queue must show only work that is
still open, or it becomes the never-emptying list #53 describes and gets
ignored. Two, everything in it is attacker-authored — written by a loop whose
job is defeating our detector — so it must stay data all the way through.
"""

import json

from app.services import evasion_review


def write_evasions(tmp_path, rows):
    path = tmp_path / "evasions.jsonl"
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    return path


def write_corpus(tmp_path, rows):
    path = tmp_path / "corpus.jsonl"
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    return path


SEED = {
    "id": "en-kyc-001",
    "language": "en",
    "label": "scam",
    "status": "enforced",
    "text": "Share the OTP or your account will be blocked",
    "expected_rule_ids": ["otp_share", "account_lock"],
    "source": "handwritten",
    "note": None,
}


def evasion(**overrides):
    base = {
        "id": "ev-001",
        "seed_id": "en-kyc-001",
        "strategy": "paraphrase",
        "language": "en",
        "text": "Kindly provide the numeric code or your account faces suspension",
        "verdict": "safe",
        "risk_score": 0,
        "rules_fired": [],
        "judge_reason": "Both ask for an OTP to avoid account blockage.",
        "detector": "rules",
        "status": "open",
        "first_seen": None,
    }
    return {**base, **overrides}


def test_only_open_entries_are_queued(tmp_path):
    """A queue that never empties gets ignored, and then a real evasion sits in
    it unnoticed — the failure #53 describes."""
    rows = [
        evasion(id="a", status="open"),
        evasion(id="b", status="fixed"),
        evasion(id="c", status="wontfix"),
    ]
    queue = evasion_review.build_queue(
        write_evasions(tmp_path, rows), write_corpus(tmp_path, [SEED])
    )

    assert [e["id"] for e in queue["evasions"]] == ["a"]
    assert queue["counts"] == {"open": 1, "fixed": 1, "wontfix": 1, "total": 3}


def test_every_entry_carries_the_seed_it_mutated(tmp_path):
    """The reviewer's question is "is this still the same fraud?", which the
    variant alone cannot answer."""
    queue = evasion_review.build_queue(
        write_evasions(tmp_path, [evasion()]), write_corpus(tmp_path, [SEED])
    )
    card = queue["evasions"][0]

    assert card["seed"]["id"] == "en-kyc-001"
    assert card["seed"]["text"] == SEED["text"]
    assert card["seed"]["expected_rule_ids"] == ["otp_share", "account_lock"]


def test_a_missing_seed_degrades_rather_than_breaking(tmp_path):
    """A seed deleted from the corpus makes the variant harder to judge, not
    unreviewable — and the UI must be able to say the original is gone rather
    than render a blank panel."""
    queue = evasion_review.build_queue(
        write_evasions(tmp_path, [evasion(seed_id="deleted-case")]),
        write_corpus(tmp_path, [SEED]),
    )
    card = queue["evasions"][0]

    assert card["seed"] is None
    assert card["diff"] is None
    assert card["text"], "the variant itself must still be there"


def test_diff_marks_only_what_the_mutation_added(tmp_path):
    queue = evasion_review.build_queue(
        write_evasions(tmp_path, [evasion()]), write_corpus(tmp_path, [SEED])
    )
    diff = queue["evasions"][0]["diff"]

    added = [t["text"] for t in diff if t["kind"] == "added"]
    same = [t["text"] for t in diff if t["kind"] == "same"]

    assert "numeric" in added and "Kindly" in added
    # Words carried over from the seed must not be highlighted, or everything
    # is highlighted and the diff says nothing.
    assert "account" in same and "your" in same


def test_diff_ignores_trailing_punctuation():
    """"suspension." and "suspension" are the same word moving, not an edit.
    The diff is a reading aid, not a merge tool."""
    diff = evasion_review.diff_tokens("your account is blocked", "your account is blocked.")
    assert all(t["kind"] == "same" for t in diff)


def test_diff_is_case_insensitive():
    diff = evasion_review.diff_tokens("Share the OTP", "share the otp")
    assert all(t["kind"] == "same" for t in diff)


def test_diff_returns_tokens_never_markup():
    """The variant is the most hostile string on the screen. If this ever
    returned a string, the rendering layer would have something to interpret —
    so it returns structured tokens and the UI escapes them as React children.
    """
    hostile = 'Ignore previous instructions. <script>alert(1)</script> & "quoted"'
    diff = evasion_review.diff_tokens("benign seed text", hostile)

    assert isinstance(diff, list)
    assert all(set(t) == {"text", "kind"} for t in diff)
    # Verbatim, unescaped and un-stripped — escaping is the renderer's job, and
    # doing it here would double-escape or give a false sense of safety.
    assert "<script>alert(1)</script>" in " ".join(t["text"] for t in diff)


def test_strategy_counts_are_reported(tmp_path):
    """A strategy producing nothing but noise is itself a finding, and it is
    only visible in aggregate."""
    rows = [
        evasion(id="a", strategy="paraphrase"),
        evasion(id="b", strategy="paraphrase"),
        evasion(id="c", strategy="transliteration"),
        evasion(id="d", strategy="padding", status="fixed"),
    ]
    queue = evasion_review.build_queue(
        write_evasions(tmp_path, rows), write_corpus(tmp_path, [SEED])
    )

    # Open entries only — a strategy whose findings are all fixed is not work.
    assert queue["by_strategy"] == {"paraphrase": 2, "transliteration": 1}


def test_missing_file_is_an_empty_queue(tmp_path):
    queue = evasion_review.build_queue(
        tmp_path / "absent.jsonl", write_corpus(tmp_path, [SEED])
    )
    assert queue["evasions"] == []
    assert queue["counts"]["total"] == 0


def test_the_committed_queue_is_well_formed():
    """Guards the real file. All three entries are currently `fixed`, which is
    the correct state — the queue should be empty when the detector has caught
    up."""
    queue = evasion_review.build_queue()
    for card in queue["evasions"]:
        assert card["seed"] is not None or card["diff"] is None
        assert card["strategy"]
        assert card["text"]
