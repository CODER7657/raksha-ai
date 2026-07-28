-- Switching RAG embeddings from local sentence-transformers (384-dim, but
-- OOM-crashed the backend on Render's free 512MB RAM tier) to Gemini's free
-- embedding API (text-embedding-004, 768-dim). Existing 384-dim rows are
-- incompatible with the new dimension and must be cleared before re-seeding.

truncate table public.scam_patterns;

alter table public.scam_patterns alter column embedding type vector(768);

drop index if exists scam_patterns_embedding_idx;
create index scam_patterns_embedding_idx
  on public.scam_patterns using ivfflat (embedding vector_cosine_ops) with (lists = 100);

drop function if exists match_scam_patterns(vector(384), text, int);

create or replace function match_scam_patterns(
  query_embedding vector(768),
  match_language text,
  match_count int default 5
)
returns table (
  id uuid,
  pattern_text text,
  category text,
  similarity float
)
language sql stable
as $$
  select id, pattern_text, category,
         1 - (embedding <=> query_embedding) as similarity
  from public.scam_patterns
  where language = match_language or match_language = 'en'
  order by embedding <=> query_embedding
  limit match_count;
$$;
