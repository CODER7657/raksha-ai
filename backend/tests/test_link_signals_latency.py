"""The 100ms budget, as a test rather than an intention.

`PHASE-2-PLAN.md` §00b puts A2 stage 1 on the **hot path** with a budget of
under 100ms added per scan. That number is only meaningful if something checks
it, because the way it gets lost is not a careless commit — it is a reasonable
one. A Public Suffix List load, a real Unicode confusables table, a regex sweep
over the message body: each is a good idea and each is how 0.5ms becomes 50ms.

Measured on the developer machine at the time of writing, 2000 iterations per
case, feeds loaded with 2,000,000 digests:

    clean bank domain        p50 0.0161ms   p99 0.0355ms
    brand lookalike          p50 0.0987ms   p99 0.2278ms
    brand impersonation      p50 0.2463ms   p99 0.6391ms
    homograph (cyrillic)     p50 0.0909ms   p99 0.2373ms
    homograph (punycode)     p50 0.0918ms   p99 0.2733ms
    machine-generated host   p50 0.2341ms   p99 0.4969ms
    indic domain (benign)    p50 0.1590ms   p99 0.2839ms
    malformed input          p50 0.0020ms   p99 0.0037ms

Roughly 150x of headroom against the budget. The threshold below is set at
**10ms**, not 100ms, deliberately: at two orders of magnitude of margin, a
regression that merely stays under 100ms has still changed the shape of this
code into something it was not, and the useful alarm goes off long before the
budget does.

CI machines are noisier than a laptop, so the assertion is on the median rather
than the max — a single scheduling hiccup is not a regression.

**Not measured here:** `domain_age.signals_for`, which does one indexed database
read. It is excluded because timing it needs a live Supabase and would measure
the network rather than this code. It is on the hot path and it is one indexed
read on a primary key; that is the claim, and it is not one this file has
verified.
"""

import statistics
import time

import pytest

from app.services import link_signals, threat_feeds

#: Two orders of magnitude below the §00b budget — see the module docstring.
BUDGET_MS = 10.0

ITERATIONS = 300

CASES = [
    ("clean bank domain", "https://www.hdfcbank.com/"),
    ("brand lookalike", "http://paytnn.com/refund"),
    ("brand impersonation", "http://paytm-refund.info/verify"),
    ("homograph cyrillic", "http://pаytm.xyz/login"),
    ("homograph punycode", "http://xn--pytm-4qa.com/login"),
    ("machine generated host", "http://x7f2q9k3mz8vb1n4.com/"),
    ("indic domain benign", "https://सरकार.भारत/"),
    ("malformed input", "not a url at all"),
]


@pytest.mark.parametrize("name,url", CASES, ids=[c[0] for c in CASES])
def test_each_url_shape_stays_inside_the_budget(name, url):
    """Per-slice, never aggregated. A mean across these would let the slow shape
    hide behind the fast ones, and the slow shape is the one that matters."""
    link_signals.evaluate(url)  # warm the regex/codec caches

    timings = []
    for _ in range(ITERATIONS):
        started = time.perf_counter()
        link_signals.evaluate(url)
        threat_feeds.signals_for(url)
        timings.append((time.perf_counter() - started) * 1000)

    median = statistics.median(timings)
    assert median < BUDGET_MS, f"{name}: {median:.4f}ms exceeds the {BUDGET_MS}ms guard"


def test_feed_size_does_not_move_the_budget():
    """Guards the data structure, not the timing.

    A feed list is a frozenset and lookup is set membership, so growing it is
    free. This is worth pinning because the obvious 'improvement' — scanning a
    list, or globbing files per lookup — turns an O(1) check into an O(n) one
    that only shows up in production, where n is two million and the developer's
    fixture had three entries.
    """
    import hashlib

    original = threat_feeds._cache
    try:
        threat_feeds._cache = {
            feed: frozenset(
                hashlib.sha256(f"{feed}{i}".encode()).hexdigest() for i in range(50_000)
            )
            for feed in threat_feeds.FEEDS
        }
        url = "http://paytm-refund.info/verify"
        threat_feeds.signals_for(url)

        timings = []
        for _ in range(ITERATIONS):
            started = time.perf_counter()
            threat_feeds.signals_for(url)
            timings.append((time.perf_counter() - started) * 1000)

        assert statistics.median(timings) < BUDGET_MS
    finally:
        threat_feeds._cache = original
