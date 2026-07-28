-- Raksha AI — initial schema
-- Run via Supabase SQL editor or `supabase db push`

create extension if not exists vector;

-- ── Scan history ─────────────────────────────────────────────────────────
create table if not exists public.scans (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references auth.users(id) on delete cascade not null,
  input_type text not null check (input_type in ('text', 'audio')),
  input_text text not null,
  language text not null default 'en',
  risk_score int not null check (risk_score between 0 and 100),
  verdict text not null check (verdict in ('safe', 'suspicious', 'high_risk')),
  flagged_phrases jsonb not null default '[]'::jsonb,
  explanation text not null default '',
  recommended_action text not null default '',
  created_at timestamptz not null default now()
);

alter table public.scans enable row level security;

-- Users can only ever see / write their own scans. This is the load-bearing
-- security boundary — the backend must never bypass it with the service key
-- except for the RAG seed script.
create policy "Users can view own scans"
  on public.scans for select
  using (auth.uid() = user_id);

create policy "Users can insert own scans"
  on public.scans for insert
  with check (auth.uid() = user_id);

create index if not exists scans_user_id_idx on public.scans (user_id, created_at desc);

-- ── RAG knowledge base: known scam patterns (retrieval source) ─────────────
-- Embeddings from sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
-- (384-dim, free, runs locally, covers Hindi/Gujarati/etc.)
create table if not exists public.scam_patterns (
  id uuid primary key default gen_random_uuid(),
  pattern_text text not null,
  language text not null default 'en',
  category text not null,
  embedding vector(384),
  created_at timestamptz not null default now()
);

create index if not exists scam_patterns_embedding_idx
  on public.scam_patterns using ivfflat (embedding vector_cosine_ops) with (lists = 100);

alter table public.scam_patterns enable row level security;

-- Reference data seeded by us via the service key — public read, no public write.
create policy "Anyone can read scam patterns"
  on public.scam_patterns for select
  using (true);

-- Vector similarity search function used by the RAG retrieval step
create or replace function match_scam_patterns(
  query_embedding vector(384),
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

-- ── Community Scam Radar: aggregate counts only, no PII, no raw text stored ─
create table if not exists public.community_reports (
  id uuid primary key default gen_random_uuid(),
  pattern_hash text not null unique,
  language text not null default 'en',
  report_count int not null default 1,
  last_reported_at timestamptz not null default now()
);

alter table public.community_reports enable row level security;

create policy "Anyone can read community reports"
  on public.community_reports for select
  using (true);

create or replace function increment_community_report(p_pattern_hash text, p_language text)
returns int
language plpgsql
as $$
declare
  new_count int;
begin
  insert into public.community_reports (pattern_hash, language, report_count, last_reported_at)
  values (p_pattern_hash, p_language, 1, now())
  on conflict (pattern_hash)
  do update set report_count = community_reports.report_count + 1,
                last_reported_at = now()
  returning report_count into new_count;
  return new_count;
end;
$$;
