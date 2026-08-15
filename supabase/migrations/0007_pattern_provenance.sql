-- Where a scam pattern came from (#32 C/E, AGENT-LAYER.md §03).
--
-- Once A1 drafts patterns, some of the evidence behind a verdict is
-- machine-generated and human-approved, and some is hand-written. A reviewer
-- and eventually an auditor has to be able to tell which — and today they
-- cannot, because `scam_patterns` records only the text.
--
-- This matters more than provenance usually does. §03 is explicit that a
-- generated scam approved as a pattern is the poisoning path the review gate
-- exists to prevent. If that gate is ever bypassed, the only way to find out
-- which verdicts were affected is a column saying which patterns arrived that
-- way. Adding it after the fact is impossible: the information is gone.
--
-- ROLLBACK
--   drop view if exists public.pattern_provenance_summary;
--   drop function if exists public.match_scam_patterns(vector(768), text, int);
--   -- then re-create the 3-column version from 0003_switch_to_gemini_embeddings.sql
--   alter table public.scam_patterns
--     drop column if exists provenance,
--     drop column if exists drafted_by,
--     drop column if exists approved_by,
--     drop column if exists approved_at,
--     drop column if exists draft_id;
--
--   Additive except for the function signature, which is replaced in place.
--   Rolling back needs the old function restored or retrieval breaks, so do
--   both statements or neither.

-- ── Provenance on the pattern itself ─────────────────────────────────────

-- `human` is the default and the honest one for every row that exists today:
-- everything in the table was seeded by hand. Backfilling `agent` would be
-- inventing a history, and backfilling NULL would make "we never recorded it"
-- indistinguishable from "nobody has checked".
alter table public.scam_patterns
  add column if not exists provenance text not null default 'human'
    check (provenance in ('human', 'agent')),
  -- Which agent drafted it. NULL for hand-written rows, and required for
  -- agent ones — see the constraint below.
  add column if not exists drafted_by text,
  -- Who approved it into the table. §03: nothing an agent produces reaches the
  -- pattern database without a human saying yes, so an agent-drafted row with
  -- no approver is a bypass and the constraint rejects it.
  add column if not exists approved_by uuid,
  add column if not exists approved_at timestamptz,
  -- Back-reference to the draft it came from, so a reviewer can find the
  -- decision that let it in.
  add column if not exists draft_id text;

comment on column public.scam_patterns.provenance is
  'human = hand-written; agent = drafted by an agent and approved by a person. An agent row without approved_by is rejected.';

-- The constraint is the actual guarantee. Without it `provenance` is a label
-- anyone can set, and the review gate is a convention rather than a rule.
alter table public.scam_patterns
  drop constraint if exists scam_patterns_agent_rows_need_approval;

alter table public.scam_patterns
  add constraint scam_patterns_agent_rows_need_approval
  check (
    provenance = 'human'
    or (drafted_by is not null and approved_by is not null and approved_at is not null)
  );

create index if not exists scam_patterns_provenance_idx
  on public.scam_patterns (provenance)
  where provenance = 'agent';

-- ── Retrieval carries it through ─────────────────────────────────────────

-- Replaced rather than extended: the trace has to be able to say which of the
-- patterns behind a verdict were machine-drafted, and it can only do that if
-- retrieval returns it. Same *argument* signature, so no caller changes.
--
-- Dropped first, and that is not optional. `create or replace function` cannot
-- change a return type — Postgres rejects it with "cannot change return type of
-- existing function", and because the column additions above already succeeded
-- the migration would leave the table half-updated with retrieval still on the
-- old shape. 0003 drops the previous signature for the same reason.
--
-- The drop is momentarily destructive: any scan between it and the create
-- fails. That is a few milliseconds inside one migration run, and #57 already
-- says the migration goes in by hand before the deploy, so nothing is serving
-- the new code yet.
drop function if exists public.match_scam_patterns(vector(768), text, int);

create function public.match_scam_patterns(
  query_embedding vector(768),
  match_language text,
  match_count int default 5
)
returns table (
  id uuid,
  pattern_text text,
  category text,
  similarity float,
  provenance text,
  drafted_by text
)
language sql stable
as $$
  select id, pattern_text, category,
         1 - (embedding <=> query_embedding) as similarity,
         provenance, drafted_by
  from public.scam_patterns
  where language = match_language
  order by embedding <=> query_embedding
  limit match_count;
$$;

-- ── What the operator console can show ───────────────────────────────────

-- How much of the knowledge base is machine-drafted, per language. The number
-- that answers "how much of what we tell users traces back to an agent?" — and
-- the one that should be watched if it starts climbing without the review
-- queue's acceptance rate climbing with it.
create or replace view public.pattern_provenance_summary as
select
  language,
  count(*) as total,
  count(*) filter (where provenance = 'agent') as agent_drafted,
  count(*) filter (where provenance = 'human') as hand_written
from public.scam_patterns
group by language;
