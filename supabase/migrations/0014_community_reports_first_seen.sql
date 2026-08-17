-- When a reported message was first seen, so A3 can compute velocity.
--
-- `community_reports` has carried `last_reported_at` and `report_count` since
-- 0001. That pair cannot distinguish the two things A3 exists to tell apart:
--
--   40 reports, last seen an hour ago, first seen 6 hours ago     -> a campaign
--   40 reports, last seen an hour ago, first seen 3 months ago    -> a message
--                                                                    that circulates
--
-- Velocity is the whole difference, and without a first sighting there is no
-- window to divide by. `AGENT-LAYER.md` §04 asks A3 to cluster on timing among
-- other things; this is the timing half being made possible.
--
-- BACKFILL IS DELIBERATELY ABSENT. Existing rows get NULL rather than a guess,
-- and `campaign_correlator` skips a row with no first sighting rather than
-- assuming one. Defaulting them to `last_reported_at` would compute a zero
-- window, and defaulting to `now()` would make every old message look like it
-- started today — inventing exactly the signal this column exists to measure.
-- Old rows are silent until they are reported again, which is correct.
--
-- Nothing else about the table changes. No region, no content, no user id:
-- A3 is read-only over aggregates and the aggregate stays as thin as it is.
--
-- ROLLBACK
--   alter table public.community_reports drop column if exists first_reported_at;
--
--   Safe. Losing it makes A3 report nothing, which is its correct behaviour
--   without the data rather than a broken state.

alter table public.community_reports
  add column if not exists first_reported_at timestamptz;

comment on column public.community_reports.first_reported_at is
  'First sighting of this digest. NULL for rows written before 0014 — A3 skips '
  'those rather than guessing a window. Set on insert, never updated.';

-- Set on first insert and left alone afterwards. `report_count` and
-- `last_reported_at` keep moving; this one is the fixed end of the window, and
-- an update here would shrink every campaign's window towards zero on each new
-- report — quietly inflating the velocity it exists to measure.
create or replace function increment_community_report(p_pattern_hash text, p_language text)
returns int
language plpgsql
as $$
declare
  new_count int;
begin
  insert into public.community_reports (
    pattern_hash, language, report_count, first_reported_at, last_reported_at
  )
  values (p_pattern_hash, p_language, 1, now(), now())
  on conflict (pattern_hash)
  do update set
    report_count = community_reports.report_count + 1,
    last_reported_at = now(),
    -- coalesce, not assignment: a pre-0014 row acquires a first sighting the
    -- next time it is reported, and a row that already has one keeps it.
    first_reported_at = coalesce(community_reports.first_reported_at, now())
  returning report_count into new_count;

  return new_count;
end;
$$;
