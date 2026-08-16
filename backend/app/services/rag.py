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


#: Below this cosine similarity a retrieved pattern is noise and is left out of
#: the prompt. It is applied *here* and deliberately not in SQL — see
#: `language_is_covered`, whose whole contract depends on the query returning
#: top-k unfiltered.
WEAK_MATCH_SIMILARITY = 0.35


def language_is_covered(patterns: list[RetrievedPattern]) -> bool:
    """Does this language have any patterns at all to retrieve from?

    `match_scam_patterns` applies **no similarity floor**. It orders by distance
    and takes top-k, however poor the distance is. So an empty result does not
    mean "nothing was similar enough" — it means the `where language = ...`
    filter matched no live rows, i.e. this language has nothing in the corpus.

    That distinction is the difference between a verdict grounded in retrieved
    evidence and one the model made up unaided, and today it is invisible: nine
    of the twelve supported languages have zero patterns (#88), and their scans
    return the same shape as a grounded English one.

    The inference is only sound while the SQL stays unfiltered, so
    `test_retrieval_has_no_similarity_floor` asserts that against the migration.
    If someone adds a `where similarity > x`, that test fails and tells them
    this function needs rewriting rather than letting it quietly start lying.
    """
    return bool(patterns)


def format_context_block(patterns: list[RetrievedPattern]) -> str:
    """Turn retrieved patterns into the context block injected into the LLM prompt.

    Three outcomes, not two, and the third used to be told as the second.

    A language with **no patterns at all** was described to the model as "no
    closely matching known scam patterns were found in the database" — which
    says a corpus was consulted and came back empty. For Tamil or Odia that is
    false, and it is false in the direction that costs us: absence of evidence
    is offered to the model as evidence of absence, on exactly the languages
    where we have the least right to any confidence.
    """
    if not language_is_covered(patterns):
        return (
            "There are NO reference scam patterns in the database for this "
            "language. This is a gap in our data, not a signal about the "
            "message. Judge the message entirely on its own merits, and do not "
            "treat the absence of matches as evidence that it is safe."
        )

    lines = [
        f'- [{p.category}] "{p.pattern_text}" (similarity: {p.similarity:.2f})'
        for p in patterns
        if p.similarity > WEAK_MATCH_SIMILARITY
    ]
    if not lines:
        return (
            "Known scam patterns exist for this language, but none were "
            "similar to this message. That is a real signal: the message does "
            "not resemble anything in the reference set."
        )

    return "Known scam patterns similar to this message:\n" + "\n".join(lines)
