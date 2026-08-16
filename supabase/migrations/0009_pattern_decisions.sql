-- The review queue's decision store (#32 A).
--
-- The queue has rendered and triaged since #60, and `review.py` has been
-- honest about the gap ever since: `decisions_persisted: false`, because
-- shipping a half-written store would mean a reviewer believes their accept
-- landed when it did not. This is the store.
--
-- Three properties, in the order they matter.
--
--   1. A DECISION IS A RECORD, NOT A STATUS. Append-only, like verdict_audit
--      and for the same reason: patterns get edited and deleted, and the
--      decision that let one in has to remain answerable afterwards. An
--      attacker who gets a pattern approved is the poisoning path AGENT-LAYER
--      §03 exists to prevent, so "who approved this, when, and why" must
--      outlive the pattern itself.
--
--   2. ACCEPT AND PROMOTE ARE ONE TRANSACTION. `record_pattern_decision`
--      appends the decision and inserts into scam_patterns together, or does
--      neither. A staging table promoted later would reintroduce exactly the
--      ambiguity this migration exists to remove.
--
--   3. NOTHING IS EVER EDITED. Revoking an accept appends a `revoked` row and
--      retires the pattern. The row survives for audit; retrieval stops seeing
--      it. Deleting would destroy the thing the accept record points at.
--
-- ROLLBACK
--   drop function if exists public.record_pattern_decision(text, text, text, text, uuid, text, text, text, vector(768));
--   drop function if exists public.reject_pattern_decision_mutation() cascade;
--   drop table if exists public.pattern_decisions;
--   alter table public.scam_patterns drop column if exists retired_at;
--   -- and restore the 0007 definition of match_scam_patterns, which differs
--   -- only by the `retired_at is null` predicate added below.
--
--   Additive apart from the retrieval filter. Existing rows have retired_at
--   null, so the filter is a no-op against today's data.

-- ── Retirement, so a revoke does not delete evidence ─────────────────────

alter table public.scam_patterns
  add column if not exists retired_at timestamptz;

comment on column public.scam_patterns.retired_at is
  'Set when a pattern is revoked. The row stays for audit; retrieval skips it.';

-- ── The decisions themselves ─────────────────────────────────────────────

create table if not exists public.pattern_decisions (
  id bigserial primary key,

  -- The draft this decides, by the id in testdata/pattern_drafts.jsonl. Text
  -- rather than a foreign key because drafts are a file, not a table - A1
  -- writes them and git reviews them, which is the point.
  draft_id text not null,

  decision text not null check (decision in ('accepted', 'rejected', 'revoked')),

  -- Closed vocabulary, so rejections are countable. Rejections are training
  -- data for whoever tunes A1, and reasons that cannot be counted teach
  -- nobody anything. Null for an accept, which needs no excuse.
  -- The first five are the codes frontend/src/lib/review.ts already binds to
  -- number keys; they are not re-spelled or reordered here, because a reviewer
  -- who has learned that 3 is "too broad" would be silently retrained. Held to
  -- the Python tuple by test_rejection_reasons_match_the_migration.
  reason text check (
    reason is null
    or reason in (
      'duplicate', 'not_a_scam', 'too_broad', 'wrong_language',
      'low_quality', 'low_value'
    )
  ),

  -- The escape hatch, recorded rather than hidden. A closed list is a claim
  -- that we already know every way a draft can be wrong, and we do not. The
  -- list is expected to grow by reading these, not by guessing.
  note text,

  actor uuid not null,

  -- The pattern this created, when the decision was an accept. Null otherwise.
  pattern_id uuid,

  created_at timestamptz not null default now(),

  -- A rejection must say why; an acceptance must not need to.
  constraint pattern_decisions_rejection_needs_a_reason check (
    decision <> 'rejected' or reason is not null
  ),
  -- An accept must point at what it created, or it is not evidence of anything.
  constraint pattern_decisions_accept_has_a_pattern check (
    decision <> 'accepted' or pattern_id is not null
  )
);

create index if not exists pattern_decisions_draft_idx
  on public.pattern_decisions (draft_id, id desc);

comment on table public.pattern_decisions is
  'Append-only review decisions. The latest row per draft_id is its current state.';

-- Append-only, by trigger rather than by policy. The backend holds the service
-- role key, which bypasses RLS, so a policy would not constrain us - the same
-- reasoning as verdict_audit in 0004.
create or replace function public.reject_pattern_decision_mutation()
returns trigger
language plpgsql
as $$
begin
  raise exception 'pattern_decisions is append-only (attempted %)', tg_op
    using hint = 'Reversing a decision means appending a revoke, not editing the record of it.';
end;
$$;

drop trigger if exists pattern_decisions_no_update on public.pattern_decisions;
create trigger pattern_decisions_no_update
  before update on public.pattern_decisions
  for each row execute function public.reject_pattern_decision_mutation();

drop trigger if exists pattern_decisions_no_delete on public.pattern_decisions;
create trigger pattern_decisions_no_delete
  before delete on public.pattern_decisions
  for each row execute function public.reject_pattern_decision_mutation();

alter table public.pattern_decisions enable row level security;

-- Read for signed-in users, same posture as the other reviewer surfaces: there
-- is still no role system, and this wants one before a pilot. No write policy
-- at all - writes go through the function below under the service key.
create policy "Signed-in users can read pattern decisions"
  on public.pattern_decisions for select using (auth.uid() is not null);

-- ── Deciding, and promoting, together ────────────────────────────────────

create or replace function public.record_pattern_decision(
  p_draft_id text,
  p_decision text,
  p_reason text,
  p_note text,
  p_actor uuid,
  p_pattern_text text,
  p_language text,
  p_category text,
  p_drafted_by text,
  p_embedding vector(768)
)
returns public.pattern_decisions
language plpgsql
as $$
declare
  new_pattern_id uuid;
  result public.pattern_decisions;
  latest text;
begin
  -- Current state is the newest decision, not a status column. `id desc` is the
  -- tiebreak for the same reason agent_overview needs it: now() is
  -- transaction-scoped, so two rows written in one transaction share a
  -- created_at and time alone orders them arbitrarily.
  select d.decision into latest
    from public.pattern_decisions d
   where d.draft_id = p_draft_id
   order by d.created_at desc, d.id desc
   limit 1;

  if p_decision = 'accepted' and latest = 'accepted' then
    raise exception 'Draft % is already accepted', p_draft_id
      using hint = 'Revoke it first if the pattern needs replacing.';
  end if;

  if p_decision = 'revoked' and latest is distinct from 'accepted' then
    raise exception 'Draft % is not accepted, so there is nothing to revoke', p_draft_id
      using hint = 'A revoke supersedes an accept; it is not a way to undo a rejection.';
  end if;

  if p_decision = 'accepted' then
    -- The promotion. In this transaction, so a reviewer is never told their
    -- accept landed while scam_patterns is unchanged.
    --
    -- provenance/approved_by/approved_at satisfy the 0007 constraint by
    -- construction: an agent-drafted row cannot exist without an approver, and
    -- the approver is this decision's actor.
    insert into public.scam_patterns
      (pattern_text, language, category, embedding,
       provenance, drafted_by, approved_by, approved_at, draft_id)
    values
      (p_pattern_text, p_language, p_category, p_embedding,
       'agent', p_drafted_by, p_actor, now(), p_draft_id)
    returning id into new_pattern_id;
  end if;

  if p_decision = 'revoked' then
    -- Retire, never delete. The accept record points at this row.
    update public.scam_patterns
       set retired_at = now()
     where draft_id = p_draft_id
       and retired_at is null;
  end if;

  insert into public.pattern_decisions
    (draft_id, decision, reason, note, actor, pattern_id)
  values
    (p_draft_id, p_decision, p_reason, p_note, p_actor, new_pattern_id)
  returning * into result;

  return result;
end;
$$;

-- ── Retrieval skips retired patterns ─────────────────────────────────────

-- Dropped first: `create or replace function` cannot change a return type, and
-- 0007 learned that the hard way - the column additions succeeded and left the
-- table updated with retrieval on the old shape. The signature is unchanged
-- here, but the drop costs nothing and removes the class of problem.
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
    -- A revoked pattern must stop influencing verdicts immediately. This is the
    -- whole reason revoke exists, so the filter is the load-bearing half of it.
    and retired_at is null
  order by embedding <=> query_embedding
  limit match_count;
$$;

-- ── What the queue reads ─────────────────────────────────────────────────

-- Latest decision per draft. A view rather than a window function repeated in
-- the backend, so "current state" has exactly one definition.
create or replace view public.pattern_decision_latest
  with (security_invoker = on)
as
select distinct on (draft_id)
  draft_id, decision, reason, note, actor, pattern_id, created_at
from public.pattern_decisions
order by draft_id, created_at desc, id desc;

comment on view public.pattern_decision_latest is
  'One row per decided draft: its current state. security_invoker=on so it honours the caller''s RLS.';
