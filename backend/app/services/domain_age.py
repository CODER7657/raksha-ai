"""Domain age — a warm-path check the hot path only ever reads.

A domain registered yesterday and claiming to be HDFC is not HDFC. It is one of
the strongest static signals available, and it is the only stage 1 check that
cannot be computed from the URL string.

## Why this is two halves

WHOIS takes **seconds**. `PHASE-2-PLAN.md` §00b: look up once, cache for days,
serve the cached answer to the hot path. So:

- `signals_for()` — hot path. One indexed read. **Never** performs a lookup,
  never touches the network, never raises.
- `record()` / `pending_domains()` — warm path, driven by
  `scripts/refresh_domain_ages.py`. This is where the network lives.

A single function that looked up on a cache miss would be simpler, correct, and
would blow the 100ms budget on the first unseen domain while making every scan
depend on a WHOIS server being up.

## Silence is not innocence

A miss, a pending lookup and a failed lookup all yield **no signal**. Plenty of
TLDs refuse WHOIS, and "we could not check" is not "it is new". Reporting an
unchecked domain as young would invent evidence, which is worse here than
missing one — the absent signal simply leaves the blocking policy one witness
short, which is the conservative direction.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import Any

from app.core.supabase_client import get_supabase
from app.services.link_signals import (
    BASIS_DOMAIN_AGE,
    Signal,
    _host_of,
    _labels_of,
    _registrable_label,
)

logger = logging.getLogger(__name__)

TABLE = "domain_age_cache"

#: Below this, a domain is "newly registered". Thirty days is the window in
#: which a throwaway phishing domain does its work; a real bank's domain is
#: measured in years, so the gap between the two populations is wide and the
#: exact number is not load-bearing. Pinned by a test so tuning it is a
#: deliberate edit.
NEW_DOMAIN_DAYS = 30


def _registrable_domain(url: str) -> str | None:
    """The registration, not the hostname.

    `login.paytm-refund.info` and `paytm-refund.info` are one registration, and
    subdomains are free for an attacker to generate — keying the cache on the
    full host would miss on every new one and turn a cached answer into an
    uncached miss at exactly the moment it matters.
    """
    host = _host_of(url)
    if not host:
        return None
    labels = _labels_of(host)
    registrable = _registrable_label(labels)
    if not registrable:
        return None
    suffix = labels[labels.index(registrable) + 1 :] if registrable in labels else []
    return ".".join([registrable, *suffix]) if suffix else registrable


def _read(domain: str) -> dict[str, Any] | None:
    """One indexed read. Separated so tests can substitute the store without
    standing up a database."""
    response = (
        get_supabase()
        .table(TABLE)
        .select("status,registered_on")
        .eq("domain", domain)
        .limit(1)
        .execute()
    )
    rows = response.data or []
    return rows[0] if rows else None


def signals_for(url: str) -> list[Signal]:
    """Hot path. Cache read only — no lookup, no network, never raises."""
    domain = _registrable_domain(url)
    if not domain:
        return []

    try:
        row = _read(domain)
    except Exception:
        # A scan must not fail because a cache table is unreachable. The check
        # goes quiet; the static checks and the offline rules still run.
        logger.warning("Domain age cache read failed for %s", domain, exc_info=True)
        return []

    if not row or row.get("status") != "resolved" or not row.get("registered_on"):
        return []

    try:
        registered = date.fromisoformat(str(row["registered_on"])[:10])
    except ValueError:
        return []

    # UTC, not local. WHOIS dates are UTC and the server's timezone is not the
    # user's; a naive `date.today()` puts the boundary a day out for anyone east
    # of the deploy region, which is everyone this product serves.
    age_days = (datetime.now(timezone.utc).date() - registered).days
    if age_days >= NEW_DOMAIN_DAYS or age_days < 0:
        return []

    return [
        Signal(
            name="newly_registered_domain",
            basis=BASIS_DOMAIN_AGE,
            deterministic=True,
            detail=f"The domain '{domain}' was registered {age_days} day(s) ago.",
            evidence={
                "domain": domain,
                "registered_on": registered.isoformat(),
                "age_days": age_days,
            },
        )
    ]


# --- warm path ------------------------------------------------------------
# Called by scripts/refresh_domain_ages.py, never by a request handler.


def record(domain: str, registered_on: date | None, *, status: str) -> bool:
    """Store a completed lookup. `status` is `resolved` or `unresolved`.

    `unresolved` is stored rather than left absent on purpose: without it, a TLD
    that refuses WHOIS is retried on every pass forever.
    """
    try:
        get_supabase().table(TABLE).upsert(
            {
                "domain": domain,
                "status": status,
                "registered_on": registered_on.isoformat() if registered_on else None,
                "checked_at": datetime.now().astimezone().isoformat(),
            },
            on_conflict="domain",
        ).execute()
    except Exception:
        logger.warning("Could not record a domain age for %s", domain, exc_info=True)
        return False
    return True


def pending_domains(limit: int = 100) -> list[str]:
    """Domains seen in a scan but not yet looked up."""
    try:
        response = (
            get_supabase()
            .table(TABLE)
            .select("domain")
            .eq("status", "pending")
            .limit(limit)
            .execute()
        )
    except Exception:
        logger.warning("Could not list pending domains", exc_info=True)
        return []
    return [row["domain"] for row in (response.data or [])]
