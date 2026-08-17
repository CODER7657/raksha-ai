"""A verdict that arrives after the user has already acted. #115 §3.

> **Latency: off-path always.** A verdict can arrive after the user has read
> their result. It must **announce itself** rather than silently replacing what
> they already acted on.

A2 stages 2-3 take seconds to minutes. By the time a page verdict exists the
person has read `safe`, decided, and possibly clicked. That makes this a
different problem from getting the verdict right, and the interesting
constraints are all about the person rather than the detection.

## Append, never overwrite

`scans.verdict` is what the user was shown, and it is the only record of that.
Replacing it destroys the answer to *"what was I told?"* — which is the question
that matters after somebody has been defrauded, and precisely what the
hash-chained audit log exists to answer. So a revision is a new row, and the
original is left exactly as it was rendered.

## The unacknowledged state is the announcement

A quietly-updated row is indistinguishable from one that never changed, so the
user goes on acting on stale information forever. A revision arrives
unacknowledged; that is what makes it an announcement rather than an edit.

## Silence when nothing changed

The channel exists for *"you clicked a phishing link ten minutes ago"*. A
notification on every scan trains people to ignore exactly the message that
matters, so a revision that does not move the verdict is not recorded at all.

## Both directions, both explained

Raising caution late is the case this was built for. Lowering it — *"we warned
you and we were wrong"* — is information a user is equally entitled to, and it
is the direction that damages trust when it arrives without a reason. Both carry
the same reason and evidence, and `direction` is recorded rather than left for a
client to derive from a verdict ordering it should not have to encode.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from app.core.supabase_client import get_supabase

logger = logging.getLogger(__name__)

TABLE = "scan_revisions"

#: How loud a change is, in the only ordering that matters to a user.
_SEVERITY = {"safe": 0, "suspicious": 1, "high_risk": 2}


@dataclass(frozen=True)
class Revision:
    """A later conclusion about a scan already answered."""

    scan_id: str
    verdict: str
    risk_score: int
    #: Why, in a form a reviewer can act on. "We changed our mind" is not one.
    reason: str
    #: The evidence bundle, same shape as the signals in the trace (#87).
    signals: list[dict] = field(default_factory=list)


def _read_scan(scan_id: str) -> dict[str, Any] | None:
    """The scan as the user saw it. Separated so tests need no database."""
    response = (
        get_supabase()
        .table("scans")
        .select("id,verdict,risk_score,explanation")
        .eq("id", scan_id)
        .limit(1)
        .execute()
    )
    rows = response.data or []
    return rows[0] if rows else None


def _insert_revision(row: dict) -> dict | None:
    inserted = get_supabase().table(TABLE).insert(row).execute()
    rows = inserted.data or []
    return rows[0] if rows else None


def _append_audit(scan_id: str, payload: dict) -> None:
    get_supabase().rpc(
        "append_verdict_audit",
        {"p_scan_id": scan_id, "p_user_id": None, "p_payload": payload},
    ).execute()


def direction_of(previous: str, current: str) -> str | None:
    """`raised`, `lowered`, or None when the verdict did not move.

    Recorded on the row rather than derived by the client: deriving it means
    encoding the verdict ordering in a UI, and a UI that gets that ordering
    wrong announces a downgrade as an alarm.
    """
    before, after = _SEVERITY.get(previous, 0), _SEVERITY.get(current, 0)
    if after == before:
        return None
    return "raised" if after > before else "lowered"


def revise(revision: Revision) -> dict | None:
    """Record a later verdict, or None if there is nothing to announce.

    None means one of three things, and all three are correct outcomes: the
    verdict did not move, the original scan could not be read, or the write
    failed. None of them mutate what the user was shown.
    """
    scan = _read_scan(revision.scan_id)
    if not scan:
        # Without the original we cannot say what changed, and a revision that
        # cannot name its previous verdict is not reviewable.
        logger.warning("No scan %s to revise", revision.scan_id)
        return None

    previous = scan.get("verdict", "")
    direction = direction_of(previous, revision.verdict)
    if direction is None:
        # Not news. A risk score moving 5 to 3 under an unchanged `safe` is not
        # something to interrupt anyone for, and interrupting them anyway is how
        # the channel stops being read.
        return None

    row = {
        "scan_id": revision.scan_id,
        "previous_verdict": previous,
        "previous_risk_score": scan.get("risk_score"),
        "verdict": revision.verdict,
        "risk_score": revision.risk_score,
        "direction": direction,
        "reason": revision.reason,
        "signals": revision.signals,
        # Unacknowledged is the announcement. A row that arrived already seen
        # would be an edit wearing a revision's clothes.
        "acknowledged_at": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    try:
        stored = _insert_revision(row) or row
    except Exception:
        logger.exception("Could not record a verdict revision for %s", revision.scan_id)
        return None

    try:
        # Both verdicts in the compliance record. One holding only the first
        # cannot show what we later concluded; one holding only the second
        # cannot show what the user acted on.
        _append_audit(
            revision.scan_id,
            {
                "kind": "verdict_revision",
                "previous_verdict": previous,
                "verdict": revision.verdict,
                "direction": direction,
                "reason": revision.reason,
            },
        )
    except Exception:
        # Best-effort, same posture as the audit append in scan.py: a user gets
        # their warning even when the compliance write fails. Inverting that
        # would withhold a fraud warning because a record could not be written.
        logger.exception("Audit append failed for revision of %s", revision.scan_id)

    return stored


def pending(rows: list[dict]) -> list[dict]:
    """The revisions a user has not seen yet — what a client announces."""
    return [row for row in rows if row.get("acknowledged_at") is None]
