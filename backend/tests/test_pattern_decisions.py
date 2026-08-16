"""The review queue's decision store (#32 A).

The queue shipped read-only and said so — `decisions_persisted: false` — because
a half-written store would mean a reviewer believes their accept landed when it
did not. These are the assertions that let it say `true`.

What they mostly pin is the *shape* of a decision rather than the plumbing: that
a rejection cannot be recorded without a countable reason, that an accept is
never silently a no-op, and that the file on disk stops being the authority the
moment the store has an opinion. The transactional half — accept and promote
together, or neither — lives in SQL and is asserted against a real Postgres in
the migration's own checks; nothing mockable here can prove it.
"""

import json

import pytest

from app.services import pattern_review


def draft(**overrides):
    base = {
        "id": "draft-en-0001",
        "language": "en",
        "pattern_text": "Your account will be suspended unless you verify",
        "category": "account_lock",
        "source": "a1:run-2026-08-15T09:00Z",
        "drafted_by": "machine",
        "created_at": "2026-08-15T09:00:00Z",
        "status": "pending",
        "decision": None,
        "note": None,
    }
    return {**base, **overrides}


def decision_row(**overrides):
    base = {
        "draft_id": "draft-en-0001",
        "decision": "accepted",
        "reason": None,
        "note": None,
        "actor": "11111111-1111-1111-1111-111111111111",
        "pattern_id": "22222222-2222-2222-2222-222222222222",
        "created_at": "2026-08-16T10:00:00Z",
    }
    return {**base, **overrides}


# --- the closed vocabulary, and its escape hatch --------------------------


def test_rejection_reasons_match_the_migration():
    """The tuple is duplicated into a check constraint in 0009 so a bad reason
    is refused by the database and not only by Python. This is what keeps the
    duplicate honest — the same job `test_agent_ids_match_the_migration` does."""
    import pathlib

    migration = (
        pathlib.Path(__file__).resolve().parents[2]
        / "supabase/migrations/0009_pattern_decisions.sql"
    ).read_text(encoding="utf-8")

    for reason in pattern_review.REJECTION_REASONS:
        assert f"'{reason}'" in migration, f"{reason} is not in the constraint"


def test_a_rejection_needs_a_reason_from_the_closed_list():
    with pytest.raises(ValueError, match="rejection needs a reason"):
        pattern_review.record_decision(draft(), "rejected", actor="u", reason=None)

    with pytest.raises(ValueError, match="rejection needs a reason"):
        pattern_review.record_decision(
            draft(), "rejected", actor="u", reason="i just did not like it"
        )


def test_an_accept_may_not_carry_a_rejection_reason():
    """`too_broad` on an accept would be recorded and then never read, and a
    field that means nothing is worse than an absent one."""
    with pytest.raises(ValueError, match="only a rejection carries a reason"):
        pattern_review.record_decision(
            draft(), "accepted", actor="u", reason="too_broad"
        )


def test_the_decision_vocabulary_is_closed():
    with pytest.raises(ValueError, match="decision must be one of"):
        pattern_review.record_decision(draft(), "maybe", actor="u")


def test_a_note_is_allowed_without_a_reason(monkeypatch):
    """The escape hatch has to work on an accept too — 'approved, but watch
    this one' is a thing a reviewer needs to be able to write down."""
    captured = {}
    _stub_rpc(monkeypatch, captured)
    monkeypatch.setattr(pattern_review, "_embed_for_test", None, raising=False)

    pattern_review.record_decision(
        draft(), "revoked", actor="u", note="pattern was matching bank alerts"
    )
    assert captured["args"]["p_note"] == "pattern was matching bank alerts"
    assert captured["args"]["p_reason"] is None


# --- an accept must never be a silent no-op -------------------------------


def test_an_accept_embeds_before_it_writes(monkeypatch):
    """A pattern with no embedding is invisible to retrieval, so an accept that
    failed to embed would be an approval that did nothing. The embed happens
    first and its failure fails the whole decision."""
    order = []
    captured = {}

    monkeypatch.setattr(
        "app.services.embeddings.embed",
        lambda text, *a, **k: order.append("embed") or [0.1] * 768,
    )
    _stub_rpc(monkeypatch, captured, on_call=lambda: order.append("rpc"))

    pattern_review.record_decision(draft(), "accepted", actor="u")

    assert order == ["embed", "rpc"], f"expected embed before write, got {order}"
    assert len(captured["args"]["p_embedding"]) == 768


def test_a_failed_embedding_fails_the_accept(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("embedding provider down")

    monkeypatch.setattr("app.services.embeddings.embed", boom)
    called = {"rpc": False}
    _stub_rpc(monkeypatch, {}, on_call=lambda: called.__setitem__("rpc", True))

    with pytest.raises(RuntimeError, match="embedding provider down"):
        pattern_review.record_decision(draft(), "accepted", actor="u")

    assert not called["rpc"], "wrote a decision for a pattern it could not embed"


def test_a_rejection_does_not_embed(monkeypatch):
    """Rejecting costs nothing. Embedding a draft nobody accepted would spend
    quota on a pattern that will never be retrieved."""
    monkeypatch.setattr(
        "app.services.embeddings.embed",
        lambda *a, **k: pytest.fail("rejection must not embed"),
    )
    captured = {}
    _stub_rpc(monkeypatch, captured)

    pattern_review.record_decision(draft(), "rejected", actor="u", reason="duplicate")
    assert captured["args"]["p_embedding"] is None


# --- the store outranks the file ------------------------------------------


def test_the_store_overrides_the_file(monkeypatch):
    drafts = [draft(id="a", status="pending"), draft(id="b", status="pending")]
    decisions = {"a": decision_row(draft_id="a", decision="accepted")}

    result = pattern_review.with_decisions(drafts, decisions)

    assert result[0]["status"] == "accepted"
    assert result[0]["decision"]["outcome"] == "accepted"
    assert result[0]["decision"]["pattern_id"] == "22222222-2222-2222-2222-222222222222"
    assert result[1]["status"] == "pending", "an undecided draft must be left alone"


def test_a_revoked_draft_reads_as_pending_again():
    """It is genuinely undecided — the pattern it produced has been retired and
    somebody has to look at it afresh. A fourth status would teach the UI a
    state that only ever means 'pending, with history'."""
    drafts = [draft(id="a", status="pending")]
    decisions = {"a": decision_row(draft_id="a", decision="revoked", pattern_id=None)}

    result = pattern_review.with_decisions(drafts, decisions)

    assert result[0]["status"] == "pending"
    assert result[0]["decision"]["outcome"] == "revoked", (
        "the history must survive even though the status resets"
    )
    assert pattern_review.pending(result) == result


def test_an_unreadable_store_leaves_the_file_untouched():
    """None means 'cannot see', and the caller reports that separately. Silently
    treating it as 'nothing decided' would show a reviewer a full queue during
    an outage and have them re-decide work already done."""
    drafts = [draft(id="a", status="pending")]
    assert pattern_review.with_decisions(drafts, None) == drafts


def test_latest_decisions_returns_none_when_the_store_is_unreachable(monkeypatch):
    class Broken:
        def table(self, *a, **k):
            raise RuntimeError("no database")

    monkeypatch.setattr("app.core.supabase_client.get_supabase", lambda: Broken())
    assert pattern_review.latest_decisions() is None


def test_latest_decisions_is_keyed_by_draft(monkeypatch):
    rows = [decision_row(draft_id="a"), decision_row(draft_id="b", decision="rejected", reason="duplicate")]
    monkeypatch.setattr(
        "app.core.supabase_client.get_supabase", lambda: _FakeSupabase(rows)
    )

    result = pattern_review.latest_decisions()
    assert set(result) == {"a", "b"}
    assert result["b"]["reason"] == "duplicate"


# --- the drafts file is still a valid queue -------------------------------


def test_every_draft_in_the_file_is_decidable():
    """A draft the store cannot key on is unreachable from the UI. Cheap to
    assert and it fails loudly if someone hand-edits the file."""
    drafts = pattern_review.load_drafts()
    assert drafts, "the drafts file is empty"
    ids = [d["id"] for d in drafts]
    assert len(ids) == len(set(ids)), "draft ids must be unique to be decidable"
    for d in drafts:
        assert d["id"] and isinstance(d["id"], str)
        assert d["pattern_text"] and d["language"] and d["category"]


# --- helpers ---------------------------------------------------------------


class _FakeSupabase:
    def __init__(self, rows):
        self._rows = rows

    def table(self, name):
        return self

    def select(self, *a, **k):
        return self

    def execute(self):
        return type("R", (), {"data": self._rows})()


def _stub_rpc(monkeypatch, captured, on_call=None):
    class Stub:
        def rpc(self, name, args):
            if on_call:
                on_call()
            captured["name"] = name
            captured["args"] = args
            return self

        def execute(self):
            return type("R", (), {"data": [{"id": 1, **_json_safe(captured["args"])}]})()

    monkeypatch.setattr("app.core.supabase_client.get_supabase", lambda: Stub())


def _json_safe(args):
    return {k: v for k, v in args.items() if k != "p_embedding" and _serialisable(v)}


def _serialisable(value):
    try:
        json.dumps(value)
        return True
    except TypeError:
        return False
