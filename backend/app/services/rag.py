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


def retrieve_similar_patterns(
    query_text: str, language: str, top_k: int = 5
) -> list[RetrievedPattern]:
    query_embedding = embed(query_text, task_type="retrieval_query")
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
