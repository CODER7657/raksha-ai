"""Embeddings via Gemini's free embedding API — no local model, no torch.

Originally used sentence-transformers (local, free, no network call), but
that pulls in torch, which OOM-crashed the backend on Render's free
512MB-RAM tier. This trades a network call per embed for a much lighter
process — still $0, still free tier, just an API call instead of local
compute.
"""


MODEL_NAME = "models/gemini-embedding-001"
# gemini-embedding-001 outputs 3072-dim by default; truncated (Matryoshka)
# to 768 here — smaller vectors, faster ANN search, still well within the
# model's supported output_dimensionality options.
EMBEDDING_DIM = 768


def embed(
    text: str, task_type: str = "retrieval_document", pool: str | None = None
) -> list[float]:
    """task_type should be 'retrieval_document' when embedding stored scam
    patterns (seeding) and 'retrieval_query' when embedding an incoming
    message to search against them — Gemini's embeddings are asymmetric,
    matching task_type on both sides improves retrieval quality.

    `pool` selects which API key pays for the call. Every scan embeds, and so
    does every benchmark case and every red-team variant — so an agent run that
    shares the interactive key can rate-limit live retrieval just as easily as
    it can rate-limit classification. Defaults to interactive, because a scan is
    the caller that cannot wait."""
    import google.generativeai as genai

    from app.services import llm

    genai.configure(api_key=llm.keys_for(pool or llm.INTERACTIVE)[1])
    result = genai.embed_content(
        model=MODEL_NAME,
        content=text,
        task_type=task_type,
        output_dimensionality=EMBEDDING_DIM,
    )
    return result["embedding"]
