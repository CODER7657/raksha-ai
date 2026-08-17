-- Verdicts that arrive after the user has already acted. #115 §3.
--
-- A2 stages 2-3 take seconds to minutes. By then the person has read `safe`,
-- decided, and possibly clicked. §3 requires that a late verdict "announce
-- itself rather than silently replacing what they already acted on".
--
-- WHY THIS IS A TABLE AND NOT AN UPDATE TO `scans`
--
-- `scans.verdict` is the only record of what the user was shown. Overwriting it
-- destroys the answer to "what was I told?" — the question that matters after
-- somebody has been defrauded, and the one the hash-chained audit log exists to
-- answer. So revisions append, and the original row is never touched.
--
-- `acknowledged_at is null` IS the announcement. A silently-updated row is
-- indistinguishable from one that never changed, so the user goes on acting on
-- stale information forever.
--
-- ROLLBACK
--   drop table if exists public.scan_revisions;
--
--   Destructive: it discards the record of every late correction, including any
--   the user has not seen. `scans` is unaffected, which is the point of the
--   design — no verdict a user was shown is lost by dropping this.

create table if not exists public.scan_revisions (
  id                  uuid primary key default gen_random_uuid(),
  scan_id             uuid not null references public.scans(id) on delete cascade,

  -- Both sides of the change. A revision recording only the new verdict cannot
  -- be reviewed: the pair is the finding.
  previous_verdict    text not null check (previous_verdict in ('safe', 'suspicious', 'high_risk')),
  previous_risk_score int,
  verdict             text not null check (verdict in ('safe', 'suspicious', 'high_risk')),
  risk_score          int,

  -- Recorded rather than derived. A client deciding how loudly to announce
  -- would otherwise have to encode the verdict ordering, and one that gets it
  -- wrong announces a downgrade as an alarm.
  direction           text not null check (direction in ('raised', 'lowered')),

  -- Appealable. "We changed our mind" is not, and #87 set the evidence-bundle
  -- shape this follows.
  reason              text not null,
  signals             jsonb not null default '[]'::jsonb,

  acknowledged_at     timestamptz,
  created_at          timestamptz not null default now()
);

-- The announcement query: unseen revisions for one user's scans.
create index if not exists scan_revisions_unacknowledged_idx
  on public.scan_revisions (scan_id)
  where acknowledged_at is null;

alter table public.scan_revisions enable row level security;

-- A user reads revisions of their own scans and nothing else. Joined through
-- `scans` rather than duplicating `user_id` here, so there is one place a scan's
-- owner is recorded and no way for the two to disagree.
create policy scan_revisions_owner_select on public.scan_revisions
  for select
  using (
    exists (
      select 1 from public.scans s
      where s.id = scan_revisions.scan_id and s.user_id = auth.uid()
    )
  );

-- Acknowledging is the only thing a user may write, and only on their own rows.
-- Deliberately no update policy for any other column: a user must not be able to
-- edit what we concluded, only to record that they have seen it.
create policy scan_revisions_owner_acknowledge on public.scan_revisions
  for update
  using (
    exists (
      select 1 from public.scans s
      where s.id = scan_revisions.scan_id and s.user_id = auth.uid()
    )
  );

-- Writes come from the service role only. A revision is our conclusion, not
-- something a client may assert about itself.
revoke insert, delete on public.scan_revisions from anon, authenticated;
