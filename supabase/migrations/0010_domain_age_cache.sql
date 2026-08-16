-- Domain age cache: WHOIS is seconds, and the scan path has 100ms.
--
-- A domain registered yesterday and claiming to be HDFC is not HDFC. It is one
-- of the strongest static signals A2 stage 1 has, and the only one that cannot
-- be computed from the URL string — it needs a WHOIS lookup, which takes
-- seconds against a budget of 100ms (PHASE-2-PLAN.md §00b).
--
-- So the lookup and the read are split. The refresh job writes here; the scan
-- path does one indexed read and nothing else. A miss yields no signal rather
-- than a guess: "we have not checked" is not "it is new", and inventing the
-- difference would put a fabricated witness in front of the blocking policy.
--
-- Keyed on the REGISTRABLE domain, not the hostname. `login.paytm-refund.info`
-- and `paytm-refund.info` are one registration, and subdomains are free for an
-- attacker to generate — keying on the host would miss the cache on every new
-- one, at exactly the moment the answer matters.
--
-- ROLLBACK
--   drop table if exists public.domain_age_cache;
--
--   Safe: `domain_age.signals_for` returns [] on any read failure by design, so
--   dropping this removes one signal and breaks no scan. Nothing joins to it.

create table if not exists public.domain_age_cache (
  domain text primary key,

  -- pending    — seen in a scan, not yet looked up
  -- resolved   — WHOIS answered; registered_on is set
  -- unresolved — WHOIS refused or failed; registered_on stays null
  --
  -- `unresolved` is a stored state rather than an absent row on purpose.
  -- Plenty of TLDs refuse WHOIS, and without recording the refusal the job
  -- retries those domains on every pass forever.
  status text not null default 'pending'
    check (status in ('pending', 'resolved', 'unresolved')),

  registered_on date,

  -- Null until a lookup has been attempted. Lets the refresh job find stale
  -- entries without conflating "never checked" with "checked long ago".
  checked_at timestamptz,
  first_seen_at timestamptz not null default now(),

  -- A resolved row must carry a date and an unresolved one must not, or the
  -- read path has to defend against a state the table said was impossible.
  constraint resolved_rows_have_a_date check (
    (status = 'resolved' and registered_on is not null)
    or (status <> 'resolved' and registered_on is null)
  )
);

-- The refresh job's only query: which domains still need looking up.
create index if not exists domain_age_cache_pending_idx
  on public.domain_age_cache (status)
  where status = 'pending';

alter table public.domain_age_cache enable row level security;

-- No policy for end users. Written and read only by the backend under the
-- service role, which bypasses RLS. A SELECT policy would let a user enumerate
-- which domains have been seen in other people's scans — the same reasoning
-- that keeps `verdict_cache` closed (0005).
