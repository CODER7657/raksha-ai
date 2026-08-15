"""RAG retrieval: pull the most similar known scam patterns before we ever
call the LLM, so classification is grounded in a real reference set instead
of the model's own guess. This is what makes the "Technical Accuracy" and
"Explainability" story real rather than just an LLM wrapper.
"""

from dataclasses import dataclass

from app.core.supabase_client import get_supabase
from app.services.embeddings import embed


@dataclass
class RetrievedPattern:
    pattern_text: str
    category: str
    similarity: float
    #: 'human' or 'agent'. Defaulted so a caller constructing one by hand — and
    #: every existing test — keeps working, and because a pattern whose origin
    #: we cannot establish is a hand-written one until proven otherwise.
    #: Claiming 'agent' on a missing value would overstate agent involvement,
    #: which is the exact number #32 C exists to report honestly.
    provenance: str = "human"
    drafted_by: str | None = None


def retrieve_similar_patterns(
    query_text: str, language: str, top_k: int = 5, pool: str | None = None
) -> list[RetrievedPattern]:
    query_embedding = embed(query_text, task_type="retrieval_query", pool=pool)
    supabase = get_supabase()

    response = supabase.rpc(
        "match_scam_patterns",
        {
            "query_embedding": query_embedding,
            "match_language": language,
            "match_count": top_k,
        },
    ).execute()

    rows = response.data or []
    return [
        RetrievedPattern(
            pattern_text=row["pattern_text"],
            category=row["category"],
            similarity=row["similarity"],
            provenance=row.get("provenance") or "human",
            drafted_by=row.get("drafted_by"),
        )
        for row in rows
    ]


def format_context_block(patterns: list[RetrievedPattern]) -> str:
    """Turn retrieved patterns into the context block injected into the LLM prompt."""
    if not patterns:
        return "No closely matching known scam patterns were found in the database."

    lines = [
        f'- [{p.category}] "{p.pattern_text}" (similarity: {p.similarity:.2f})'
        for p in patterns
        if p.similarity > 0.35  # filter out weak/irrelevant matches
    ]
    if not lines:
        return "No closely matching known scam patterns were found in the database."

    return "Known scam patterns similar to this message:\n" + "\n".join(lines)
