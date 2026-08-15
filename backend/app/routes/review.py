"""Reviewer-facing draft queue (#32 A).

Read-only for now. Decisions are not persisted here yet: writing them needs a
store and a lifecycle agreed with the A1 work (see the shape discussion on
#32), and shipping a half-written persistence layer would mean a reviewer
believes their accept landed when it did not — which is the one failure this
screen cannot have.

So the queue renders and triages, and the client holds decisions until there is
somewhere honest to put them. The UI says so rather than implying otherwise.
"""

from fastapi import APIRouter, Depends, HTTPException

from app.core.auth import get_current_user
from app.services import pattern_review

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
