-- Traceability: persist the evidence behind a verdict, and make the record of
-- it tamper-evident. ARCHITECTURE.md §03.
--
-- Two things happen here:
--   1. `scans` gains a `trace` column, so the evidence the pipeline already
--      computed (retrieved patterns, itemised rules, model identity) stops
--      being discarded between the classifier and the response.
--   2. A new `verdict_audit` table holds an append-only, hash-chained record.
--
-- ROLLBACK
--   drop function if exists public.verify_verdict_chain();
--   drop function if exists public.append_verdict_audit(uuid, uuid, jsonb);
--   drop trigger if exists verdict_audit_no_delete on public.verdict_audit;
--   drop trigger if exists verdict_audit_no_update on public.verdict_audit;
--   drop function if exists public.reject_audit_mutation();
--   drop table if exists public.verdict_audit;
--   alter table public.scans drop column if exists trace;
--
--   Both steps are safe to reverse. Dropping `scans.trace` discards captured
--   evidence but touches no pre-existing column, and `verdict_audit` is a new
--   table, so nothing that exists today depends on either. Forward migration
--   is additive only: no column is altered or dropped, so a running instance
--   on the previous code keeps working against the migrated schema.

create extension if not exists pgcrypto;

-- ── Evidence on the scan row ─────────────────────────────────────────────

-- Nullable-by-default rather than NOT NULL: every row written before this
-- migration legitimately has no trace, and backfilling a fake one would make
-- unrecorded evidence indistinguishable from recorded-and-empty.
alter table public.scans add column if not exists trace jsonb;

comment on column public.scans.trace is
  'Reasoning trace for this verdict: offline_rules_fired, retrieved_patterns, model. NULL for scans recorded before traceability shipped.';

-- ── Append-only, hash-chained audit log ──────────────────────────────────

create table if not exists public.verdict_audit (
  -- bigserial, not uuid: the chain needs a total order, and a random uuid
  -- gives none.
  id bigserial primary key,
  -- Plain uuids, deliberately NOT foreign keys.
  --
  -- An append-only table cannot participate in referential actions, because
  -- every referential action is a mutation. `on delete set null` here issues an
  -- UPDATE against this table, which the append-only trigger below refuses —
  -- so deleting a scan would fail outright, and since auth.users cascades to
  -- scans, deleting a user account would fail with it. `on delete cascade`
  -- would be worse: removing the evidence would become as easy as removing the
  -- scan it evidences.
  --
  -- So the references are by value. A deleted scan leaves a scan_id pointing at
  -- nothing, which is the correct shape for an audit record — it says "this
  -- verdict concerned scan X" whether or not X still exists.
  scan_id uuid,
  user_id uuid,
  payload jsonb not null,
  prev_hash text,
  hash text not null unique,
  created_at timestamptz not null default now()
);

create index if not exists verdict_audit_scan_id_idx on public.verdict_audit (scan_id);
create index if not exists verdict_audit_user_id_idx on public.verdict_audit (user_id);

alter table public.verdict_audit enable row level security;

-- Read your own records. There is deliberately no insert/update/delete policy
-- for end users: rows arrive only through append_verdict_audit(), called by
-- the backend.
create policy "Users can view own audit records"
  on public.verdict_audit for select
  using (auth.uid() = user_id);

-- RLS alone does not make this append-only — the backend holds the service
-- role key, which bypasses RLS entirely. A trigger does not care which role
-- you are, so the guarantee holds even against our own backend.
create or replace function public.reject_audit_mutation()
returns trigger
language plpgsql
as $$
begin
  raise exception 'verdict_audit is append-only (attempted %)', tg_op;
end;
$$;

drop trigger if exists verdict_audit_no_update on public.verdict_audit;
create trigger verdict_audit_no_update
  before update on public.verdict_audit
  for each row execute function public.reject_audit_mutation();

drop trigger if exists verdict_audit_no_delete on public.verdict_audit;
create trigger verdict_audit_no_delete
  before delete on public.verdict_audit
  for each row execute function public.reject_audit_mutation();

-- ── Appending a link ─────────────────────────────────────────────────────

-- Hashing lives here rather than in Python on purpose. Postgres renders jsonb
-- with keys ordered by length then bytewise; Python's json.dumps(sort_keys)
-- orders lexicographically. Two implementations would silently disagree the
-- moment a payload carries keys of differing length, so there is exactly one,
-- and it sits next to the data it protects.
create or replace function public.append_verdict_audit(
  p_scan_id uuid,
  p_user_id uuid,
  p_payload jsonb
)
returns table (id bigint, hash text, prev_hash text)
language plpgsql
as $$
declare
  v_prev_hash text;
  v_hash text;
begin
  -- Serialise appenders. Without this, two concurrent scans read the same tip
  -- and write two links claiming the same predecessor — a forked chain, which
  -- verifies as tampered. Transaction-scoped, so it releases on commit or
  -- rollback either way.
  perform pg_advisory_xact_lock(hashtext('verdict_audit_chain'));

  select va.hash into v_prev_hash
  from public.verdict_audit va
  order by va.id desc
  limit 1;

  v_hash := encode(
    digest(coalesce(v_prev_hash, '') || p_payload::text, 'sha256'),
    'hex'
  );

  return query
  insert into public.verdict_audit (scan_id, user_id, payload, prev_hash, hash)
  values (p_scan_id, p_user_id, p_payload, v_prev_hash, v_hash)
  returning verdict_audit.id, verdict_audit.hash, verdict_audit.prev_hash;
end;
$$;

-- ── Verifying the chain ──────────────────────────────────────────────────

-- Recomputes every link with the same expression that wrote it and reports
-- the first row that does not reconcile. An empty result means intact.
create or replace function public.verify_verdict_chain()
returns table (id bigint, problem text)
language plpgsql
as $$
declare
  v_expected_prev text := null;
  rec record;
begin
  for rec in
    select va.id, va.payload, va.prev_hash, va.hash
    from public.verdict_audit va
    order by va.id
  loop
    if rec.prev_hash is distinct from v_expected_prev then
      id := rec.id;
      problem := 'prev_hash does not match the preceding link';
      return next;
    end if;

    if rec.hash <> encode(
         digest(coalesce(rec.prev_hash, '') || rec.payload::text, 'sha256'),
         'hex'
       ) then
      id := rec.id;
      problem := 'hash does not match payload — record was altered';
      return next;
    end if;

    v_expected_prev := rec.hash;
  end loop;
end;
$$;

comment on function public.verify_verdict_chain() is
  'Returns one row per broken link; an empty result means the chain is intact.';

-- ── Who may call these ───────────────────────────────────────────────────

-- Postgres grants EXECUTE on new functions to PUBLIC by default, and Supabase
-- exposes every public-schema function over PostgREST. Without these revokes a
-- logged-in user could invoke append_verdict_audit() directly and try to write
-- their own links into the chain.
--
-- RLS already blocks that insert today (verdict_audit has no INSERT policy),
-- so this is a second lock on the same door — but the first one is the absence
-- of a policy, and absences are easy to undo by accident. The chain is the
-- artifact an institutional buyer is being asked to trust; it should not
-- depend on nobody adding a well-meaning INSERT policy later.
revoke execute on function public.append_verdict_audit(uuid, uuid, jsonb) from public, anon, authenticated;
revoke execute on function public.verify_verdict_chain() from public, anon, authenticated;

-- The backend (service role) is the only caller of the append path.
grant execute on function public.append_verdict_audit(uuid, uuid, jsonb) to service_role;
grant execute on function public.verify_verdict_chain() to service_role;
