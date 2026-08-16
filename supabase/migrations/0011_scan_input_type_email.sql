-- Email as a scan channel of its own.
--
-- `scans.input_type` has been `check (input_type in ('text', 'audio'))` since
-- 0001. Share-to-app email (#115 §2) is a third channel and needs its own value
-- rather than being recorded as `text`.
--
-- Not cosmetic. Every accuracy claim on this project is reported per-slice and
-- never aggregated, and channel is one of the slices that matters most: an
-- email carries a sender we usually cannot verify and a link we usually can
-- check, which is close to the opposite of an SMS. Filed under `text`, email's
-- precision would be averaged into SMS's and neither number would mean
-- anything.
--
-- ROLLBACK
--   Only safe while no row uses the new value:
--
--   delete from public.scans where input_type = 'email';
--   alter table public.scans drop constraint scans_input_type_check;
--   alter table public.scans add constraint scans_input_type_check
--     check (input_type in ('text', 'audio'));
--
--   The delete is destructive and is why this is written down rather than
--   assumed — reverting the constraint without it fails, and reverting it with
--   it discards user scan history.

alter table public.scans drop constraint if exists scans_input_type_check;

alter table public.scans add constraint scans_input_type_check
  check (input_type in ('text', 'audio', 'email'));
