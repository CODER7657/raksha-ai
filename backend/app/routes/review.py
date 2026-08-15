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
from app.services import evasion_review, pattern_review

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
