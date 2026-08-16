"""Domain age — the one stage 1 check that cannot run on the hot path.

WHOIS takes seconds. `PHASE-2-PLAN.md` §00b puts it on the warm path for that
reason: look up once, cache for days, and let the hot path read the cache and
nothing else.

The tests that matter here are the negative ones. A domain-age check that
quietly does its own lookup would be correct, useful, and would blow the 100ms
budget on the first uncached domain — while adding an availability dependency on
a WHOIS server to every scan. So most of this file pins what `signals_for` is
forbidden from doing.
"""

from datetime import datetime, timedelta, timezone

import pytest

from app.services import domain_age, link_signals


@pytest.fixture
def cache(monkeypatch):
    """An in-memory stand-in for the cache table."""
    rows: dict[str, dict] = {}
    monkeypatch.setattr(domain_age, "_read", lambda domain: rows.get(domain))
    return rows


def _resolved(days_old: int) -> dict:
    """UTC, matching `domain_age.signals_for`. A local-time helper against a
    UTC implementation would make the boundary tests flap by a day depending on
    where the machine running them is."""
    today = datetime.now(timezone.utc).date()
    return {
        "status": "resolved",
        "registered_on": (today - timedelta(days=days_old)).isoformat(),
    }


# --- the hot path reads the cache and only the cache ----------------------


def test_a_cache_miss_yields_no_signal(cache):
    """Silence, not a guess. An unknown domain is unknown — reporting it as
    young because we have not looked would invent evidence."""
    assert domain_age.signals_for("http://never-seen.example/") == []


def test_a_pending_lookup_yields_no_signal(cache):
    cache["pending.example"] = {"status": "pending", "registered_on": None}
    assert domain_age.signals_for("http://pending.example/") == []


def test_a_failed_lookup_yields_no_signal(cache):
    """Plenty of TLDs refuse WHOIS. 'We could not check' is not 'it is new'."""
    cache["noreply.example"] = {"status": "unresolved", "registered_on": None}
    assert domain_age.signals_for("http://noreply.example/") == []


def test_signals_for_makes_no_network_call(cache, monkeypatch):
    """The whole reason this check is split in two."""
    import socket

    def explode(*args, **kwargs):
        raise AssertionError("domain age lookup attempted a network connection")

    monkeypatch.setattr(socket.socket, "connect", explode)
    monkeypatch.setattr(socket, "create_connection", explode)
    monkeypatch.setattr(socket, "getaddrinfo", explode)

    domain_age.signals_for("http://never-seen.example/")


def test_a_cache_read_failure_degrades_to_no_signal(monkeypatch):
    """A scan must not fail because a cache table is unreachable."""

    def boom(domain):
        raise RuntimeError("database is down")

    monkeypatch.setattr(domain_age, "_read", boom)
    assert domain_age.signals_for("http://anything.example/") == []


# --- the signal itself ----------------------------------------------------


def test_a_domain_registered_yesterday_is_flagged(cache):
    cache["brand-new.example"] = _resolved(1)
    signals = domain_age.signals_for("http://brand-new.example/")
    assert [s.name for s in signals] == ["newly_registered_domain"]


def test_an_established_domain_is_not_flagged(cache):
    cache["hdfcbank.com"] = _resolved(9000)
    assert domain_age.signals_for("https://www.hdfcbank.com/") == []


def test_the_threshold_is_at_the_documented_boundary(cache):
    """Pinned so a tuning change is a deliberate edit rather than a drift."""
    cache["edge.example"] = _resolved(domain_age.NEW_DOMAIN_DAYS - 1)
    assert domain_age.signals_for("http://edge.example/")

    cache["edge.example"] = _resolved(domain_age.NEW_DOMAIN_DAYS + 1)
    assert domain_age.signals_for("http://edge.example/") == []


def test_the_signal_is_deterministic(cache):
    """A WHOIS registration date is not something the page can talk us out of,
    which is what lets this satisfy the Confirmed tier's deterministic slot."""
    cache["brand-new.example"] = _resolved(1)
    for signal in domain_age.signals_for("http://brand-new.example/"):
        assert signal.deterministic is True


def test_domain_age_is_its_own_witness(cache):
    """Registration date is a fact about the world, not a reading of the URL
    string, so it is genuinely independent of every host-label check."""
    cache["paytnn.example"] = _resolved(1)
    combined = link_signals.evaluate("http://paytnn.example/") + domain_age.signals_for(
        "http://paytnn.example/"
    )
    assert link_signals.independent_witnesses(combined) == 2


def test_the_signal_says_how_old_rather_than_just_new(cache):
    """'Registered 3 days ago' is appealable and checkable. 'Suspicious' is
    neither."""
    cache["brand-new.example"] = _resolved(3)
    signal = domain_age.signals_for("http://brand-new.example/")[0]
    assert signal.evidence["age_days"] == 3
    assert signal.evidence["registered_on"]


# --- subdomains -----------------------------------------------------------


def test_age_is_looked_up_on_the_registrable_domain_not_the_full_host(cache):
    """`login.paytm-refund.info` and `paytm-refund.info` are one registration.
    Keying on the full host would miss the cache on every new subdomain, which
    is free for an attacker to generate."""
    cache["paytm-refund.info"] = _resolved(2)
    assert domain_age.signals_for("http://login.paytm-refund.info/verify")
