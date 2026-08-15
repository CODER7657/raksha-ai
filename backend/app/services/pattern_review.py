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
import pathlib
from dataclasses import asdict, dataclass

from app.services import rag
from app.services.rule_engine import offline_rule_hits

DRAFTS_PATH = (
    pathlib.Path(__file__).resolve().parents[3] / "testdata" / "pattern_drafts.jsonl"
)

#: At or above this cosine similarity, a draft is telling the reviewer nothing
#: new. Mirrors the leakage threshold in benchmark_llm for the same reason —
#: above it, two texts are the same text for retrieval purposes.
NEAR_DUPLICATE_SIMILARITY = 0.95

STATUSES = ("pending", "accepted", "rejected")


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
