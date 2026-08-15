-- Verdict cache: stop paying for the same scam a thousand times.
--
-- A scam campaign sends one message to thousands of people. Every one of those
-- currently costs an embedding call and a classification call for a message we
-- have already judged, on free-tier keys shared with everything else. The
-- infrastructure for "have we seen this exact text" is already in production —
-- `community_reports` is keyed on `trace.hash_text()` — so this reuses the same
-- digest rather than inventing a second identity for a message.
--
-- ROLLBACK
--   drop table if exists public.verdict_cache;
--
--   Safe: nothing reads it that cannot fall through to a live classification,
--   which is exactly what happens today. Dropping it costs money, not
--   correctness.

create table if not exists public.verdict_cache (
  -- The three things that together decide whether a stored verdict still
  -- applies. Language matters because the explanation is written in it, and
  -- prompt_version because a prompt change is a verdict change (ARCHITECTURE
  -- §03) — the same key the benchmark cache uses, for the same reason.
  digest text not null,
  language text not null,
  prompt_version text not null,

  verdict text not null check (verdict in ('safe', 'suspicious', 'high_risk')),
  risk_score int not null check (risk_score between 0 and 100),
  flagged_phrases jsonb not null default '[]'::jsonb,
  explanation text not null,
  recommended_action text not null,

  -- Which model produced it. A cached verdict has to be able to say this, or
  -- the trace would credit a model call that never happened.
  provider text not null,
  model text not null,

  created_at timestamptz not null default now(),
  hit_count int not null default 0,
  last_hit_at timestamptz,

  primary key (digest, language, prompt_version)
);

comment on table public.verdict_cache is
  'Classifier verdicts keyed by message digest. Never holds raw message text — the digest is the same unkeyed hash community_reports uses.';

-- Reads are by primary key, so the only index worth adding is for eviction.
create index if not exists verdict_cache_created_at_idx
  on public.verdict_cache (created_at);

alter table public.verdict_cache enable row level security;

-- No policy for end users at all. This table is written and read only by the
-- backend under the service role, which bypasses RLS. A user has no reason to
-- query it directly, and a SELECT policy would let one enumerate which messages
-- have been scanned by guessing digests.

-- Counting hits without a read-modify-write from Python, which would race
-- between two concurrent scans of the same viral message — the exact situation
-- this table exists for.
create or replace function public.touch_verdict_cache(
  p_digest text,
  p_language text,
  p_prompt_version text
)
returns void
language sql
as $$
  update public.verdict_cache
     set hit_count = hit_count + 1,
         last_hit_at = now()
   where digest = p_digest
     and language = p_language
     and prompt_version = p_prompt_version;
$$;

revoke execute on function public.touch_verdict_cache(text, text, text)
  from public, anon, authenticated;
grant execute on function public.touch_verdict_cache(text, text, text) to service_role;
