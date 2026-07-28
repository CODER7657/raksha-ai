"""Local, free, multilingual embeddings for the RAG retrieval step.

paraphrase-multilingual-MiniLM-L12-v2 is open-source, runs on CPU, covers
50+ languages including Hindi/Gujarati/Marathi/Bengali/Tamil/etc., and
produces 384-dim vectors — matching the `vector(384)` column in
supabase/migrations/0001_init.sql. No API cost, no network call.
"""

from functools import lru_cache

from sentence_transformers import SentenceTransformer

MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"


@lru_cache
def _model() -> SentenceTransformer:
    return SentenceTransformer(MODEL_NAME)


def embed(text: str) -> list[float]:
    vector = _model().encode(text, normalize_embeddings=True)
    return vector.tolist()
