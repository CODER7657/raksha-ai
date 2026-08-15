-- Operator control plane for the agent layer (#32 D).
--
-- AGENT-LAYER.md §09 promises per-agent budget caps, a per-agent kill switch,
-- and a run log with cost and outcome. None of it existed, so those controls
-- lived only in a document — and a control that exists only in a document is
-- indistinguishable, on the day you need it, from one that was never built.
--
-- Two tables, and one property that matters more than either:
--
--   **The detection path must never read these.** §09 says any agent can be
--   disabled "without touching the others or the detection path". If `scan.py`
--   ever consulted agent_state, a stuck switch or an unreachable table would
--   stop fraud warnings reaching users — turning a cost control into an
--   outage. `test_kill_switch_cannot_touch_detection` pins that.
--
-- ROLLBACK
--   drop function if exists public.set_agent_enabled(text, boolean, text, uuid);
--   drop function if exists public.record_agent_run(text, text, int, jsonb);
--   drop view if exists public.agent_overview;
--   drop table if exists public.agent_runs;
--   drop table if exists public.agent_state;
--
--   Purely additive: two new tables, one view, two functions. Nothing existing
--   is altered, so the previous code runs unchanged against the migrated
--   schema and reversing costs only the recorded history.

-- ── Which agents exist, and whether they may run ─────────────────────────

create table if not exists public.agent_state (
  -- Stable string, not a uuid: it appears in CLI flags, logs and this table,
  -- and a human has to be able to type it.
  agent_id text primary key,
  display_name text not null,
  -- Default true. A new agent is not born disabled, and a row appearing from a
  -- migration should not silently stop work someone is relying on.
  enabled boolean not null default true,
  -- Why, and who. A kill switch with no reason attached gets flipped back on by
  -- the next person who finds it off and cannot tell whether that was
  -- deliberate.
  disabled_reason text,
  disabled_by uuid,
  disabled_at timestamptz,
  -- Model calls allowed per rolling 24h. NULL means uncapped, which is a
  -- deliberate state rather than an absent one.
  spend_cap_calls int check (spend_cap_calls is null or spend_cap_calls > 0),
  updated_at timestamptz not null default now()
);

comment on table public.agent_state is
  'Per-agent kill switch and budget cap. Never read by the detection path.';

-- ── What each run cost, and how it ended ─────────────────────────────────

create table if not exists public.agent_runs (
  id bigserial primary key,
  agent_id text not null,
  outcome text not null check (outcome in ('ok', 'failed', 'blocked')),
  -- 'blocked' is a real outcome, not an absence of one: a run refused by the
  -- kill switch or the cap is the control working, and it belongs in the log
  -- next to the runs that happened.
  model_calls int not null default 0 check (model_calls >= 0),
  detail jsonb,
  started_at timestamptz not null default now(),
  finished_at timestamptz
);

create index if not exists agent_runs_agent_started_idx
  on public.agent_runs (agent_id, started_at desc);

alter table public.agent_state enable row level security;
alter table public.agent_runs enable row level security;

-- Any signed-in user can read. There is still no role system, so this is the
-- same posture as the benchmark endpoint: authenticated, not restricted
-- further, and wanting a reviewer role before a pilot. Writes go through the
-- functions below, which the backend calls with the service key.
create policy "Signed-in users can read agent state"
  on public.agent_state for select using (auth.uid() is not null);

create policy "Signed-in users can read agent runs"
  on public.agent_runs for select using (auth.uid() is not null);

-- ── Flipping the switch ──────────────────────────────────────────────────

create or replace function public.set_agent_enabled(
  p_agent_id text,
  p_enabled boolean,
  p_reason text,
  p_actor uuid
)
returns public.agent_state
language plpgsql
as $$
declare
  result public.agent_state;
begin
  update public.agent_state
     set enabled = p_enabled,
         -- Cleared on re-enable. A stale "disabled because it was looping"
         -- sitting on a running agent is worse than no reason at all.
         disabled_reason = case when p_enabled then null else p_reason end,
         disabled_by     = case when p_enabled then null else p_actor end,
         disabled_at     = case when p_enabled then null else now() end,
         updated_at      = now()
   where agent_id = p_agent_id
  returning * into result;

  if not found then
    raise exception 'No such agent: %', p_agent_id
      using hint = 'Agents are registered by migration, not created on demand.';
  end if;

  return result;
end;
$$;

-- ── Recording a run ──────────────────────────────────────────────────────

create or replace function public.record_agent_run(
  p_agent_id text,
  p_outcome text,
  p_model_calls int,
  p_detail jsonb
)
returns bigint
language plpgsql
as $$
declare
  new_id bigint;
begin
  insert into public.agent_runs (agent_id, outcome, model_calls, detail, finished_at)
  values (p_agent_id, p_outcome, coalesce(p_model_calls, 0), p_detail, now())
  returning id into new_id;
  return new_id;
end;
$$;

-- ── What the console renders ─────────────────────────────────────────────

-- A view rather than three round trips. Spend is over a rolling 24h because a
-- calendar-day cap resets at midnight in a timezone nobody agreed on, and an
-- agent that exhausts its budget at 23:00 should not be free again in an hour.
-- `security_invoker = on` is load-bearing, even though it changes nothing
-- today. A Postgres view defaults to executing as its *owner* — `postgres`,
-- which owns the two tables below and is exempt from their RLS — so without
-- this the view quietly skips the policies written directly above it.
--
-- The policies currently grant every signed-in user read, so the effective
-- exposure is identical right now. It matters the moment someone adds the
-- reviewer role this codebase keeps saying it needs: they will tighten the
-- policy on `agent_state`, and an owner-executing view would carry on
-- returning everything. A control that looks like it constrains and does not
-- is worse than no control, because nobody checks it again.
create or replace view public.agent_overview
  with (security_invoker = on)
as
select
  s.agent_id,
  s.display_name,
  s.enabled,
  s.disabled_reason,
  s.disabled_at,
  s.spend_cap_calls,
  coalesce(recent.calls_24h, 0) as calls_24h,
  last_run.outcome     as last_outcome,
  last_run.started_at  as last_run_at,
  last_run.model_calls as last_run_calls
from public.agent_state s
left join lateral (
  select sum(r.model_calls)::int as calls_24h
  from public.agent_runs r
  where r.agent_id = s.agent_id
    and r.started_at > now() - interval '24 hours'
) recent on true
left join lateral (
  select r.outcome, r.started_at, r.model_calls
  from public.agent_runs r
  where r.agent_id = s.agent_id
  -- `id desc` is the tiebreak, and it is load-bearing: `now()` is
  -- transaction-scoped in Postgres, so two runs recorded in one transaction
  -- share a `started_at` to the microsecond and ordering by time alone picks
  -- between them arbitrarily. The console would then show a stale outcome as
  -- the latest — which for an operator deciding whether an agent is misbehaving
  -- is exactly the wrong thing to get wrong.
  order by r.started_at desc, r.id desc
  limit 1
) last_run on true;

comment on view public.agent_overview is
  'One row per agent: switch state, 24h spend against cap, and the last run.';

-- ── The agents that exist today ──────────────────────────────────────────

-- Registered here rather than created on demand, so a typo in a CLI flag is an
-- error instead of a new agent nobody is watching.
insert into public.agent_state (agent_id, display_name, spend_cap_calls)
values
  ('a6_redteam', 'A6 Red-Team Adversary', 200),
  ('llm_benchmark', 'RAG + LLM benchmark', 300)
on conflict (agent_id) do nothing;

-- ── Who may call these ───────────────────────────────────────────────────

-- Both functions are `security invoker`, so RLS default-deny already stops a
-- non-service caller: the update touches zero rows and the insert is rejected.
-- These revokes state the intent rather than leaving it to that backstop —
-- Postgres grants EXECUTE to PUBLIC by default and Supabase exposes every
-- public-schema function over PostgREST, so without them the API surface says
-- "anyone may call this" and only the policy disagrees.
--
-- Same reasoning as the revokes on the audit chain in 0004.
revoke execute on function public.set_agent_enabled(text, boolean, text, uuid) from public, anon, authenticated;
revoke execute on function public.record_agent_run(text, text, int, jsonb) from public, anon, authenticated;

grant execute on function public.set_agent_enabled(text, boolean, text, uuid) to service_role;
grant execute on function public.record_agent_run(text, text, int, jsonb) to service_role;
