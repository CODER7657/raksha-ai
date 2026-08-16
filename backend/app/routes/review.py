"""Reviewer-facing draft queue (#32 A).

Decisions are persisted now. They were not, for a reason worth keeping in view:
writing them needed a store and a lifecycle, and shipping a half-written
persistence layer would have meant a reviewer believing their accept landed
when it did not — the one failure this screen cannot have. So the queue shipped
read-only and said so, rather than guessing.

What settled it is that an accept and its promotion into `scam_patterns` happen
in **one transaction** (migration 0009). The decision cannot exist without the
pattern it created, and the pattern cannot appear without the decision that
approved it — which is also how the 0007 constraint is satisfied by
construction rather than by remembering to fill three columns in.

Decisions are append-only. Reversing an accept appends a `revoked` row and
retires the pattern; nothing is ever edited, because the record of who approved
a pattern has to outlive the pattern itself. An attacker who gets one approved
is the poisoning path AGENT-LAYER §03 exists to prevent.
"""

import logging
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.auth import get_current_user
from app.services import agent_control, evasion_review, pattern_review

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["review"])


@router.get("/review/drafts")
def list_drafts(_user_id: str = Depends(get_current_user)) -> dict:
    """Pending drafts, without neighbours.

    Neighbours are deliberately not computed here. Each one costs an embedding
    call, and a reviewer opening a queue of fifty would spend fifty calls on
    cards they may never reach. The client fetches them per card instead.

    The file supplies the drafts; the decision store supplies their state. When
    the store cannot be read the drafts are returned as the file has them and
    `decisions_available` says so — an operator seeing a full queue must be able
    to tell "nothing decided yet" from "cannot see what was decided", because
    working the second as though it were the first means re-deciding drafts that
    are already done.
    """
    decisions = pattern_review.latest_decisions()
    drafts = pattern_review.with_decisions(pattern_review.load_drafts(), decisions)
    queue = pattern_review.pending(drafts)

    return {
        "drafts": queue,
        "counts": {
            "pending": len(queue),
            "accepted": sum(1 for d in drafts if d.get("status") == "accepted"),
            "rejected": sum(1 for d in drafts if d.get("status") == "rejected"),
            "total": len(drafts),
        },
        # Both stated in the payload rather than assumed by the client. The
        # first is now true (#32); the second is about this request, not the
        # capability, and they are different questions.
        "decisions_persisted": True,
        "decisions_available": decisions is not None,
        "rejection_reasons": list(pattern_review.REJECTION_REASONS),
    }


class DraftDecision(BaseModel):
    decision: Literal["accepted", "rejected", "revoked"]
    #: Required for a rejection, forbidden otherwise — enforced in the service
    #: and again by a check constraint in 0009.
    reason: str | None = None
    #: The escape hatch beside the closed list. Bounded because it is free text
    #: written by a human in a hurry, not because anything downstream needs it
    #: short.
    note: str | None = Field(default=None, max_length=1000)


@router.post("/review/drafts/{draft_id}/decision")
def decide_draft(
    draft_id: str,
    payload: DraftDecision,
    user_id: str = Depends(get_current_user),
) -> dict:
    """Accept, reject or revoke one draft.

    An accept promotes the draft into `scam_patterns` in the same transaction
    that records the decision, so the two cannot disagree. That matters more
    than it sounds: a reviewer told their accept landed while the pattern
    database is unchanged is the single failure this endpoint exists to remove,
    and it is why the queue shipped read-only rather than guessing at a store.

    Errors surface. Nothing here is best-effort.
    """
    draft = next((d for d in pattern_review.load_drafts() if d["id"] == draft_id), None)
    if draft is None:
        raise HTTPException(status_code=404, detail="No such draft")

    try:
        record = pattern_review.record_decision(
            draft,
            payload.decision,
            actor=user_id,
            reason=payload.reason,
            note=payload.note,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Failed to record a %s decision for %s", payload.decision, draft_id)
        raise HTTPException(
            status_code=502,
            detail=(
                f"Could not record the decision for '{draft_id}'. It has NOT been "
                f"{payload.decision} — nothing was written."
            ),
        ) from exc

    return {"decision": record}


@router.get("/review/drafts/{draft_id}/context")
def draft_context(draft_id: str, _user_id: str = Depends(get_current_user)) -> dict:
    """The near-duplicate check and rule response for one draft.

    One embedding call, paid only for a card actually opened.
    """
    match = next((d for d in pattern_review.load_drafts() if d["id"] == draft_id), None)
    if match is None:
        raise HTTPException(status_code=404, detail="No such draft")

    return pattern_review.review_card(match)


@router.get("/review/evasions")
def list_evasions(_user_id: str = Depends(get_current_user)) -> dict:
    """Variants that got past the detector and still need a human decision.

    Only `open` entries. `fixed` closed itself when the detector caught up
    (#53) and `wontfix` was already judged — a queue that never empties gets
    ignored, and then a real evasion sits in it unnoticed.

    Each entry carries the seed case it was mutated from and a token-level
    diff, because the reviewer's question is "is this still the same fraud?"
    and the variant alone cannot answer it.

    The `text` on these records is adversarial by construction. It is returned
    as data and never used to build a prompt; nothing on this path calls a
    model.
    """
    return evasion_review.build_queue()


# ── Operator console (#32 D) ────────────────────────────────────────────────


class AgentSwitch(BaseModel):
    enabled: bool
    # Required when disabling, enforced in the service. A switch with no reason
    # attached gets flipped back on by the next person who finds it off and
    # cannot tell whether that was deliberate.
    reason: str | None = Field(default=None, max_length=500)


@router.get("/agents")
def list_agents(_user_id: str = Depends(get_current_user)) -> dict:
    """Per-agent switch state, 24h spend against cap, and the last run.

    `available: false` rather than an empty list when the control plane cannot
    be read: an operator seeing no agents must be able to tell "none
    registered" from "cannot see", because those call for opposite responses.
    """
    return agent_control.overview()


@router.get("/agents/runs")
def list_agent_runs(
    agent_id: str | None = None,
    _user_id: str = Depends(get_current_user),
) -> dict:
    """The run log. A `blocked` entry is the kill switch working, not an error —
    an operator asking "did it fire?" needs the evidence that it did."""
    return {"runs": agent_control.recent_runs(agent_id)}


@router.post("/agents/{agent_id}/switch")
def switch_agent(
    agent_id: str,
    payload: AgentSwitch,
    user_id: str = Depends(get_current_user),
) -> dict:
    """Stop or start one agent.

    Deliberately per-agent with no bulk variant. §09 requires that any one can
    be disabled without touching the others, and a "stop everything" button is
    the shape that gets pressed in a panic and takes down more than intended.

    Errors are surfaced rather than swallowed: an operator who believes they
    stopped an agent and did not is the worst outcome this endpoint can have.

    Unlike the read endpoints beside it, this one is allowlisted. They only
    disclose; this one writes — and with open signup, "authenticated" is not a
    meaningful boundary for a write that a stranger could use to stop the
    red-team loop or leave a string in `disabled_reason` for the next operator.
    """
    if not agent_control.is_operator(user_id):
        raise HTTPException(
            status_code=403,
            detail=(
                "Only listed operators can stop or start an agent. Add the user's "
                "Supabase UUID to AGENT_OPERATOR_IDS. Unset means nobody, on purpose."
            ),
        )

    try:
        return {"agent": agent_control.set_enabled(agent_id, payload.enabled, payload.reason, user_id)}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Failed to switch agent %s", agent_id)
        raise HTTPException(
            status_code=502,
            detail=f"Could not change '{agent_id}'. It has NOT been stopped — check the control plane.",
        ) from exc
