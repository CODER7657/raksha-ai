"""Reviewer-facing draft queue (#32 A).

Read-only for now. Decisions are not persisted here yet: writing them needs a
store and a lifecycle agreed with the A1 work (see the shape discussion on
#32), and shipping a half-written persistence layer would mean a reviewer
believes their accept landed when it did not — which is the one failure this
screen cannot have.

So the queue renders and triages, and the client holds decisions until there is
somewhere honest to put them. The UI says so rather than implying otherwise.
"""

import logging

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
    """
    drafts = pattern_review.load_drafts()
    queue = pattern_review.pending(drafts)

    return {
        "drafts": queue,
        "counts": {
            "pending": len(queue),
            "accepted": sum(1 for d in drafts if d.get("status") == "accepted"),
            "rejected": sum(1 for d in drafts if d.get("status") == "rejected"),
            "total": len(drafts),
        },
        # Stated in the payload rather than assumed by the client, so the UI
        # cannot quietly imply decisions are being saved.
        "decisions_persisted": False,
    }


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
