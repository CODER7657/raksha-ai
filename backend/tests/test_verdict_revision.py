"""A verdict that arrives after the user has already acted. #115 §3.

> **Latency: off-path always.** A verdict can arrive after the user has read
> their result. It must **announce itself** rather than silently replacing what
> they already acted on.

Stage 2-3 take seconds to minutes. By the time a page verdict exists, the person
has read `safe`, decided, and possibly clicked. That makes this a different
problem from getting the verdict right.

## Two things a late verdict must not do

**It must not overwrite.** `scans.verdict` is what the user was shown, and it is
the only record of that. Replacing it destroys the answer to "what was I told?"
— which is the question that matters after someone has been defrauded, and the
one the audit chain exists to answer. A revision is an append.

**It must not arrive silently.** A quietly-updated row is indistinguishable from
one that never changed, so the user acts on stale information forever. A
revision is unacknowledged until seen; that unacknowledged state *is* the
announcement.

## And one thing it must not become

A notification for every scan. A revision that does not change the verdict is
not news, and shipping one teaches people to ignore the channel that exists for
the case where they clicked a phishing link ten minutes ago.
"""

import pytest

from app.services import verdict_revision

SAFE_SCAN = {
    "id": "scan-1",
    "verdict": "safe",
    "risk_score": 5,
    "explanation": "Nothing unusual in the wording.",
}


@pytest.fixture
def store(monkeypatch):
    """In-memory stand-in for the scans row and the revisions table."""
    state = {"scan": dict(SAFE_SCAN), "revisions": [], "audit": []}

    monkeypatch.setattr(verdict_revision, "_read_scan", lambda scan_id: dict(state["scan"]))
    monkeypatch.setattr(
        verdict_revision, "_insert_revision",
        lambda row: state["revisions"].append(row) or {**row, "id": f"rev-{len(state['revisions'])}"},
    )
    monkeypatch.setattr(
        verdict_revision, "_append_audit", lambda scan_id, payload: state["audit"].append(payload)
    )
    return state


def _worse(reason="known_bad_feed"):
    return verdict_revision.Revision(
        scan_id="scan-1", verdict="high_risk", risk_score=90,
        reason=reason, signals=[{"name": "known_bad_feed", "basis": "feed"}],
    )


# --- the original is never touched ----------------------------------------


def test_the_original_verdict_is_left_exactly_as_the_user_saw_it(store):
    """`scans.verdict` is the only record of what the person was told. After
    someone has been defrauded, "what was I shown?" is the question, and an
    overwritten row cannot answer it."""
    verdict_revision.revise(_worse())

    assert store["scan"]["verdict"] == "safe"
    assert store["scan"]["risk_score"] == 5
    assert store["scan"]["explanation"] == SAFE_SCAN["explanation"]


def test_a_revision_is_an_append_not_an_edit(store):
    verdict_revision.revise(_worse())
    assert len(store["revisions"]) == 1

    verdict_revision.revise(_worse(reason="page_analysis"))
    assert len(store["revisions"]) == 2, "a second revision replaced the first"


def test_the_revision_records_what_it_changed_from(store):
    """A revision saying only "high_risk" cannot be reviewed. The pair is the
    finding."""
    verdict_revision.revise(_worse())
    row = store["revisions"][0]

    assert row["previous_verdict"] == "safe"
    assert row["verdict"] == "high_risk"


def test_the_revision_records_why(store):
    """Appealable. "We changed our mind" is not, and #87's evidence-bundle shape
    is the standard here."""
    verdict_revision.revise(_worse())
    row = store["revisions"][0]

    assert row["reason"]
    assert row["signals"]


# --- it announces itself --------------------------------------------------


def test_a_new_revision_is_unacknowledged(store):
    """The unacknowledged state IS the announcement. A silently-updated row is
    indistinguishable from one that never changed."""
    verdict_revision.revise(_worse())
    assert store["revisions"][0]["acknowledged_at"] is None


def test_pending_announcements_surface_only_unacknowledged_ones(store):
    monkeypatch_rows = [
        {"id": "r1", "scan_id": "scan-1", "acknowledged_at": None},
        {"id": "r2", "scan_id": "scan-2", "acknowledged_at": "2026-08-16T10:00:00Z"},
    ]
    pending = verdict_revision.pending(monkeypatch_rows)
    assert [r["id"] for r in pending] == ["r1"]


# --- and does not become noise --------------------------------------------


def test_a_revision_that_changes_nothing_is_not_recorded(store):
    """The channel exists for "you clicked a phishing link ten minutes ago". A
    notification on every scan teaches people to ignore it."""
    same = verdict_revision.Revision(
        scan_id="scan-1", verdict="safe", risk_score=5,
        reason="page_analysis", signals=[],
    )
    assert verdict_revision.revise(same) is None
    assert store["revisions"] == []


def test_a_lower_risk_score_with_the_same_verdict_is_not_news(store):
    """Verdict is what the user acts on. A score moving 5 to 3 under an
    unchanged `safe` is not something to interrupt anyone for."""
    nudge = verdict_revision.Revision(
        scan_id="scan-1", verdict="safe", risk_score=3,
        reason="page_analysis", signals=[],
    )
    assert verdict_revision.revise(nudge) is None


# --- direction ------------------------------------------------------------


def test_a_late_verdict_may_raise_caution(store):
    assert verdict_revision.revise(_worse()) is not None


def test_a_late_verdict_may_also_lower_it_and_says_so(store):
    """Worth allowing, and worth marking. "We warned you and we were wrong" is
    information a user is entitled to — and it is the direction that damages
    trust if it arrives with no explanation, so it carries the same reason and
    evidence as a raise."""
    store["scan"] = {**SAFE_SCAN, "verdict": "suspicious", "risk_score": 70}
    cleared = verdict_revision.Revision(
        scan_id="scan-1", verdict="safe", risk_score=5,
        reason="page_analysis_cleared", signals=[{"name": "no_findings", "basis": "page_content"}],
    )
    row = verdict_revision.revise(cleared)

    assert row is not None
    assert row["direction"] == "lowered"
    assert row["reason"]


def test_the_direction_is_recorded_rather_than_inferred(store):
    """A client deciding how loudly to announce needs this, and deriving it
    means knowing the verdict ordering — which is not a thing a UI should have
    to encode."""
    assert verdict_revision.revise(_worse())["direction"] == "raised"


# --- the audit chain ------------------------------------------------------


def test_a_revision_appends_to_the_audit_chain(store):
    """The compliance record has to contain both verdicts. One that holds only
    the first cannot show what we later concluded; one that holds only the
    second cannot show what the user acted on."""
    verdict_revision.revise(_worse())
    assert len(store["audit"]) == 1
    assert store["audit"][0]["previous_verdict"] == "safe"
    assert store["audit"][0]["verdict"] == "high_risk"


def test_a_failed_audit_append_does_not_lose_the_revision(store, monkeypatch):
    """Same posture as `_append_audit_record` in scan.py: a user gets their
    warning even when the compliance write fails. Inverting that would withhold
    a fraud warning because a record could not be written."""
    def boom(scan_id, payload):
        raise RuntimeError("audit table unreachable")

    monkeypatch.setattr(verdict_revision, "_append_audit", boom)
    assert verdict_revision.revise(_worse()) is not None
    assert len(store["revisions"]) == 1


def test_an_unreadable_scan_is_not_revised(store, monkeypatch):
    """Without the original we cannot say what changed, and a revision that
    cannot name its previous verdict is not reviewable."""
    monkeypatch.setattr(verdict_revision, "_read_scan", lambda scan_id: None)
    assert verdict_revision.revise(_worse()) is None
    assert store["revisions"] == []
