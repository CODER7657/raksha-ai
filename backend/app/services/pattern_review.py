"""The A1 pattern draft queue (#32 A).

Every agent that can affect users produces drafts, and a human approves them.
That makes this queue part of the security design rather than admin UI: the
pattern database is what the detection engine reasons against, so a wrong
pattern silently degrades every verdict in a way no test catches. If triage is
slow the queue backs up, and the pressure to auto-approve becomes real —
reviewer throughput is a security property here.

**What is stored and what is computed.** A draft record holds only what a human
or an agent asserted: the text, its language and category, where it came from,
and the decision once one is made. The near-duplicate check is computed at
review time and never written down, because a similarity score frozen at
draft-time goes stale the moment the pattern database moves, and a stale score
that looks authoritative is worse than no score.

**Cost.** Finding neighbours needs one embedding call for the draft being
looked at. That is why `neighbours_for` takes a single draft rather than the
queue: a reviewer works through one card at a time, so the cost is one call per
draft actually reviewed, not fifty up front for a queue nobody finishes.
"""

from __future__ import annotations

import json
import logging
import pathlib
from dataclasses import asdict, dataclass

from app.services import rag
from app.services.rule_engine import offline_rule_hits

logger = logging.getLogger(__name__)

DRAFTS_PATH = (
    pathlib.Path(__file__).resolve().parents[3] / "testdata" / "pattern_drafts.jsonl"
)

#: At or above this cosine similarity, a draft is telling the reviewer nothing
#: new. Mirrors the leakage threshold in benchmark_llm for the same reason —
#: above it, two texts are the same text for retrieval purposes.
NEAR_DUPLICATE_SIMILARITY = 0.95

STATUSES = ("pending", "accepted", "rejected")

#: What a reviewer may record when turning a draft down (#32).
#:
#: Closed, because §A asks for one keystroke and because rejections are training
#: data for whoever tunes A1 — reasons that cannot be counted teach nobody
#: anything. The optional free-text note beside it is the escape hatch: a closed
#: list is a claim that we already know every way a draft can be wrong, and we
#: do not. The list grows by reading the notes, not by guessing.
#:
#: Mirrored by a check constraint in migration 0009. `test_rejection_reasons_
#: match_the_migration` keeps the two honest, the same way KNOWN_AGENTS is held
#: to the agent table.
#: The first five are the codes `frontend/src/lib/review.ts` already ships, in
#: the order it binds them to number keys. They are not re-spelled here: a
#: reviewer who has learned that 3 is "too broad" would be silently retrained by
#: a reordering, and #64 is the whole argument against two lists of the same
#: thing drifting apart. `low_value` is added as 6 because it is genuinely a
#: different judgement from `low_quality` — one is about the draft being
#: garbled, the other about it being real but too rare to be worth a retrieval
#: slot.
REJECTION_REASONS = (
    "duplicate",       # already covered by an existing pattern
    "not_a_scam",      # the source material was misread
    "too_broad",       # would match legitimate messages
    "wrong_language",  # script or language mismatch
    "low_quality",     # garbled, or not usable as written
    "low_value",       # real, but too rare to be worth a retrieval slot
)

#: What a decision may be. `revoked` is not a status a draft can be drafted in —
#: it only ever follows an accept, and it exists because a wrong pattern
#: degrades every verdict silently (AGENT-LAYER §03). Being unable to take one
#: back would make that unrecoverable.
DECISIONS = ("accepted", "rejected", "revoked")


@dataclass(frozen=True)
class Neighbour:
    pattern_text: str
    category: str
    similarity: float
    #: Stated rather than left to the reader to infer from a decimal — the whole
    #: point of showing neighbours is so a near-duplicate is obvious at a glance.
    near_duplicate: bool


def load_drafts(path: pathlib.Path | None = None) -> list[dict]:
    source = path or DRAFTS_PATH
    if not source.exists():
        return []
    return [
        json.loads(line)
        for line in source.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def pending(drafts: list[dict]) -> list[dict]:
    return [d for d in drafts if d.get("status") == "pending"]


def rule_response(draft: dict) -> list[str]:
    """What the offline engine already does with this text.

    Free, deterministic, and honest — unlike a benchmark-impact figure, which
    would need the LLM benchmark re-run per draft. A draft the rules already
    fire on is a different decision from one they ignore, and the reviewer can
    see which without anyone spending API quota.
    """
    return sorted({hit.rule_id for hit in offline_rule_hits(draft["pattern_text"], draft["language"])})


def neighbours_for(draft: dict, top_k: int = 3) -> list[Neighbour]:
    """Nearest existing patterns, so a near-duplicate is obvious.

    One embedding call. Raises nothing on failure — a queue that cannot be
    triaged because retrieval is down is worse than one triaged without the
    near-duplicate hint, so the caller degrades instead.
    """
    retrieved = rag.retrieve_similar_patterns(draft["pattern_text"], draft["language"], top_k=top_k)
    return [
        Neighbour(
            pattern_text=p.pattern_text,
            category=p.category,
            similarity=round(p.similarity, 4),
            near_duplicate=p.similarity >= NEAR_DUPLICATE_SIMILARITY,
        )
        for p in retrieved
    ]


def latest_decisions() -> dict[str, dict] | None:
    """Current state per decided draft, or None if the store cannot be read.

    None rather than an empty dict, and the distinction is the same one
    `review_card` already makes about neighbours: "nothing has been decided" and
    "we cannot see what has been decided" call for opposite responses from a
    reviewer. Collapsing them would show a full queue of apparently-pending
    drafts during an outage, and a reviewer working that queue would be
    re-deciding things that are already decided.
    """
    from app.core.supabase_client import get_supabase

    try:
        rows = get_supabase().table("pattern_decision_latest").select("*").execute().data or []
    except Exception:
        logger.warning("Could not read the pattern decision store", exc_info=True)
        return None
    return {row["draft_id"]: row for row in rows}


def with_decisions(drafts: list[dict], decisions: dict[str, dict] | None) -> list[dict]:
    """Overlay the store onto the file.

    The file is what A1 drafted; the database is what a human decided. The
    file's own `status` and `decision` fields are the initial state only — every
    draft is written `pending` — and the store wins wherever it has an opinion.

    Two sources of truth would drift, so this states plainly which one is
    authoritative rather than leaving it to whichever code path reads first.

    The output shape is unchanged, deliberately: `status` and `decision` are
    already the contract `frontend/src/lib/review.ts` consumes, so persistence
    changes where the values come from and nothing about what the client sees.

    A `revoked` draft reads as `pending` again. It is genuinely undecided —
    the pattern it produced has been retired, and somebody has to look at it
    afresh — and inventing a fourth status would mean teaching the UI a state
    that only ever means "pending, and there is history".
    """
    if decisions is None:
        return drafts

    overlaid = []
    for draft in drafts:
        decision = decisions.get(draft["id"])
        if decision is None:
            overlaid.append(draft)
            continue
        status = "pending" if decision["decision"] == "revoked" else decision["decision"]
        overlaid.append(
            {
                **draft,
                "status": status,
                "decision": {
                    "by": decision["actor"],
                    "at": decision["created_at"],
                    "reason": decision["reason"],
                    "note": decision["note"],
                    "outcome": decision["decision"],
                    "pattern_id": decision["pattern_id"],
                },
            }
        )
    return overlaid


def record_decision(
    draft: dict,
    decision: str,
    actor: str,
    reason: str | None = None,
    note: str | None = None,
) -> dict:
    """Persist one decision, promoting the draft when it is an accept.

    Raises rather than returning a failure. Unlike every read path here, a
    decision that did not land must not look like one that did — a reviewer who
    believes they approved a pattern into the detection set, and did not, is the
    failure this whole issue exists to remove.

    The embedding is computed here because it is an API call and cannot happen
    inside the transaction that stores it. It is computed *before* the RPC so a
    failure to embed fails the accept outright: a pattern with no embedding is
    invisible to retrieval, which would be an accept that silently did nothing.
    """
    from app.core.supabase_client import get_supabase
    from app.services.embeddings import embed

    if decision not in DECISIONS:
        raise ValueError(f"decision must be one of {DECISIONS}, got {decision!r}")
    if decision == "rejected" and reason not in REJECTION_REASONS:
        raise ValueError(
            f"a rejection needs a reason from {REJECTION_REASONS}, got {reason!r}"
        )
    if decision != "rejected" and reason is not None:
        raise ValueError("only a rejection carries a reason")

    embedding = None
    if decision == "accepted":
        # 'retrieval_document', matching how seed_scam_patterns stores patterns.
        # Gemini's embeddings are asymmetric and the query side already uses
        # 'retrieval_query', so mismatching here would quietly degrade
        # retrieval for exactly the patterns a human took the trouble to approve.
        embedding = embed(draft["pattern_text"])

    response = get_supabase().rpc(
        "record_pattern_decision",
        {
            "p_draft_id": draft["id"],
            "p_decision": decision,
            "p_reason": reason,
            "p_note": note,
            "p_actor": actor,
            "p_pattern_text": draft["pattern_text"],
            "p_language": draft["language"],
            "p_category": draft["category"],
            "p_drafted_by": draft.get("drafted_by") or "unknown",
            "p_embedding": embedding,
        },
    ).execute()

    rows = response.data
    return rows[0] if isinstance(rows, list) and rows else rows


def review_card(draft: dict) -> dict:
    """One draft plus everything the reviewer needs to decide on it.

    Retrieval failure degrades to `neighbours: null` rather than an error. The
    distinction matters in the UI: an empty list means "nothing similar
    exists", null means "we could not check" — and a reviewer must not read the
    second as the first.
    """
    try:
        neighbours: list[dict] | None = [asdict(n) for n in neighbours_for(draft)]
    except Exception:
        neighbours = None

    return {
        **draft,
        "neighbours": neighbours,
        "rule_response": rule_response(draft),
    }
