"""Known-bad feed lookups, stacked rather than chosen.

`PHASE-2-PLAN.md` §01 puts four feeds behind one check because independent
research puts single-feed detection well under 60%. The design consequence that
matters is not "query four APIs" — it is that a feed hit is **a** signal and
never the answer, and that no feed lookup is allowed to make a network call on
the scan path.

The lists ship empty. Populating them needs the refresh job, which runs
off-path and needs a Google Safe Browsing API key; the code, the format, the
canonicalisation and the tests are what stage 1 delivers. Tests here use
fixtures rather than real feed data, so they measure the mechanism rather than
somebody's 12-hour-old snapshot.
"""

import pytest

from app.services import threat_feeds


@pytest.fixture
def stub_feeds(monkeypatch):
    """Two feeds listing one URL each, plus one both list."""
    both = threat_feeds.digest_for("http://shared-bad.example/login")
    monkeypatch.setattr(
        threat_feeds,
        "_load_all",
        lambda: {
            "urlhaus": {threat_feeds.digest_for("http://only-urlhaus.example/a"), both},
            "openphish": {threat_feeds.digest_for("http://only-openphish.example/b"), both},
        },
    )
    threat_feeds.reset_cache()
    yield
    threat_feeds.reset_cache()


# --- canonicalisation -----------------------------------------------------


@pytest.mark.parametrize(
    "variant",
    [
        "http://Example.com/Login",
        "http://example.com:80/Login",
        "http://example.com/Login#fragment",
        "  http://example.com/Login  ",
    ],
)
def test_trivial_variants_hash_the_same(variant):
    """A feed lists one spelling and a scammer sends another. Case, default
    port, fragment and whitespace are not different URLs."""
    assert threat_feeds.digest_for(variant) == threat_feeds.digest_for("http://example.com/Login")


def test_the_path_is_case_sensitive_because_servers_treat_it_that_way():
    """Host is case-insensitive, path is not. Folding the path would collide
    distinct URLs and turn one listing into a false positive on another."""
    assert threat_feeds.digest_for("http://example.com/A") != threat_feeds.digest_for(
        "http://example.com/a"
    )


def test_digests_are_hashes_not_urls():
    """The lists are hash lists — the point is that we can ship and diff them
    without shipping a directory of live phishing URLs."""
    digest = threat_feeds.digest_for("http://example.com/login")
    assert len(digest) == 64 and all(c in "0123456789abcdef" for c in digest)
    assert "example" not in digest


# --- lookup ---------------------------------------------------------------


def test_a_listed_url_names_the_feed_that_listed_it(stub_feeds):
    assert threat_feeds.lookup("http://only-urlhaus.example/a") == ["urlhaus"]


def test_a_url_on_two_feeds_names_both(stub_feeds):
    assert threat_feeds.lookup("http://shared-bad.example/login") == ["openphish", "urlhaus"]


def test_an_unlisted_url_returns_nothing(stub_feeds):
    assert threat_feeds.lookup("https://www.hdfcbank.com/") == []


def test_lookup_survives_a_missing_feed_directory():
    """A fresh clone has no feed data and must still scan. An exception here
    would take down every scan rather than degrade one check."""
    threat_feeds.reset_cache()
    assert threat_feeds.lookup("http://anything.example/") == []


# --- the signal -----------------------------------------------------------


def test_two_feeds_are_still_one_witness(stub_feeds):
    """The tightest constraint in this file. Feeds ingest each other, so two
    listings are not two independent confirmations — and the Confirmed tier in
    §01 spends exactly one slot on 'known-bad feed' however many agree.

    Counted as two, a single widely-syndicated listing would auto-block for
    every user with no other evidence at all."""
    from app.services import link_signals

    signals = threat_feeds.signals_for("http://shared-bad.example/login")
    assert len(signals) == 2
    assert link_signals.independent_witnesses(signals) == 1


def test_a_feed_signal_is_deterministic(stub_feeds):
    """A local hash list cannot be influenced by page content, which is what
    lets a feed hit satisfy the Confirmed tier's deterministic requirement."""
    for signal in threat_feeds.signals_for("http://shared-bad.example/login"):
        assert signal.deterministic is True


def test_feed_signals_name_the_feed(stub_feeds):
    """'On a blocklist' is not appealable. 'On URLhaus' is."""
    evidence = [s.evidence["feed"] for s in threat_feeds.signals_for("http://shared-bad.example/login")]
    assert sorted(evidence) == ["openphish", "urlhaus"]


# --- no network on the scan path ------------------------------------------


def test_lookup_makes_no_network_call(stub_feeds, monkeypatch):
    """§00b: no blocking network call in the scan path, ever. A feed client that
    quietly starts querying an API would blow the 100ms budget and add an
    availability dependency to detection."""
    import socket

    def explode(*args, **kwargs):
        raise AssertionError("threat feed lookup attempted a network connection")

    monkeypatch.setattr(socket.socket, "connect", explode)
    monkeypatch.setattr(socket, "create_connection", explode)
    monkeypatch.setattr(socket, "getaddrinfo", explode)

    threat_feeds.lookup("http://shared-bad.example/login")
