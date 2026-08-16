-- Register A2's page analyser as an agent under the control plane.
--
-- #115: every agent, without exception, is registered in `agent_state`, under a
-- kill switch that has been pulled and observed, inside a budget cap (#75), and
-- on the batch key pool.
--
-- A2 stages 2-3 is the first agent that reads attacker-controlled content, which
-- makes the kill switch matter more here than anywhere it has been used so far.
-- The other two agents spend money when they misbehave; this one fetches a URL
-- an attacker chose. "Stop doing that right now" needs to be one UPDATE.
--
-- Cap of 100, lower than A6's 200 and the benchmark's 300, for two reasons. It
-- is off the hot path so nobody is waiting, and it is the only agent whose
-- per-call cost includes a sandbox boot rather than just tokens. The plan also
-- asks for a per-URL-per-day sandbox cap on top of this; that belongs with the
-- sandbox runner, which is infrastructure and does not exist yet.
--
-- ROLLBACK
--   delete from public.agent_state where agent_id = 'a2_page_analysis';
--
--   Safe. Nothing joins to it, and `may_run` refuses an unregistered agent —
--   so removing the row disables the agent rather than freeing it.

insert into public.agent_state (agent_id, display_name, spend_cap_calls)
values
  ('a2_page_analysis', 'A2 Phishing Page Analyser', 100)
on conflict (agent_id) do nothing;
