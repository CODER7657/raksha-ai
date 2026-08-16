-- Make `pattern_provenance_summary` honour RLS (#79 follow-up).
--
-- The view landed in 0007 without `security_invoker`. Postgres defaults that
-- option to OFF, which means a view executes with the privileges of its OWNER
-- rather than the caller. The owner here is `postgres`, which also owns
-- `scam_patterns` — and a table's owner is exempt from its own row level
-- security. So selecting this view reads straight past whatever policy is on
-- the table underneath it.
--
-- 0006 got this right for `agent_overview` and said why. 0007 did not, and the
-- two views were written days apart, which is exactly how a convention that
-- lives only in one file's comments goes missing.
--
-- WHAT THIS CHANGES TODAY: nothing observable. `scam_patterns` carries
-- "Anyone can read scam patterns" from 0001, and this view exposes only
-- per-language counts. Nobody can see anything through it they could not see
-- by querying the table directly.
--
-- WHY IT IS WORTH A MIGRATION ANYWAY: the exposure is not the point, the
-- silence is. The day someone narrows that 0001 policy — a reviewer role, a
-- tenant split, anything — they will narrow the table and reasonably assume
-- the view followed. It will not have. A control that looks like it constrains
-- and does not is worse than an absent one, because it is trusted.
--
-- ROLLBACK
--   alter view public.pattern_provenance_summary reset (security_invoker);
--
--   Restores the previous (owner-privileged) behaviour. Safe, and reversible
--   precisely because nothing depends on the current setting.

alter view public.pattern_provenance_summary set (security_invoker = on);

comment on view public.pattern_provenance_summary is
  'Per-language counts of hand-written vs agent-drafted patterns. security_invoker=on, so it honours the caller''s RLS rather than the owner''s exemption.';

-- Verification, for whoever runs this by hand. Both views must report
-- {security_invoker=on}; a NULL in either column means the option did not take
-- and the view is still reading past RLS.
--
--   select relname, reloptions
--     from pg_class
--    where relname in ('agent_overview', 'pattern_provenance_summary');
