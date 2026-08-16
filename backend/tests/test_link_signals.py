"""A2 stage 1 — static link checks that never fetch the page.

The checks themselves are the easy half. The shape of what they return is the
half that decides whether stages 2-3 can be built on top, so most of this file
is about the shape.

`PHASE-2-PLAN.md` §01 blocks on **two independent signals, at least one
deterministic**. That policy is only implementable if the stage hands it named
signals it can count. A blended score — "this URL scored 0.82" — is not
reducible back into "which two things agreed, and was either of them immune to
page content", so a total destroys exactly the property the policy needs.

The `basis` field is the part that is an interpretation rather than a
transcription of the spec, and it is here because counting is where this gets
dangerous. Brand-token edit distance and homograph detection both fire on
`paytm.xyz` spelled with a Cyrillic 'a'. Counted as two, that is a confirmed
auto-block for every user on what is really one observation about one string.
Blocking a genuine bank domain during a fraud alert is the harm this product
exists to prevent, so independence is counted by distinct basis, not by
signal count.
"""

import pytest

from app.services import link_signals


# --- the contract ---------------------------------------------------------


def test_every_signal_is_named():
    """An anonymous signal cannot be reasoned about by the blocking policy, and
    cannot be told apart from a second firing of the same check."""
    signals = link_signals.evaluate("http://paytm-refund.info/verify")
    assert signals, "a lookalike domain on a suspicious TLD should fire something"
    for signal in signals:
        assert signal.name, "signal has no name"
        assert signal.name.replace("_", "").isalnum(), (
            f"{signal.name!r} is not a stable identifier"
        )


def test_every_signal_declares_whether_it_is_deterministic():
    """`deterministic` is not decoration. The Confirmed tier requires at least
    one signal that page content cannot influence, and a signal that declines to
    say which kind it is cannot satisfy that."""
    for signal in link_signals.evaluate("http://paytm-refund.info/verify"):
        assert isinstance(signal.deterministic, bool)


def test_stage_one_signals_are_all_deterministic():
    """Stage 1 does not fetch, does not sandbox, and runs no model. If anything
    here reports `deterministic: False` it has acquired a dependency it is not
    allowed to have."""
    for signal in link_signals.evaluate("http://paytm-refund.info/verify"):
        assert signal.deterministic is True, (
            f"{signal.name} claims non-determinism, but nothing in stage 1 reads "
            f"attacker-controlled content"
        )


def test_there_is_no_blended_score_on_the_result():
    """Guards the shape against the most likely future 'improvement'."""
    result = link_signals.evaluate("http://paytm-refund.info/verify")
    assert isinstance(result, list)
    for banned in ("score", "risk", "total", "confidence"):
        assert not hasattr(result, banned)


def test_a_clean_url_returns_no_signals_rather_than_a_zero():
    """Absence of evidence is reported as absence. A zero-scored signal in the
    list would be counted by anything that counts."""
    assert link_signals.evaluate("https://www.hdfcbank.com/") == []


# --- independence ---------------------------------------------------------


def test_signals_derived_from_one_observation_share_a_basis():
    """The auto-block guard. Two checks reading the same string are one witness,
    however many names they report under."""
    signals = link_signals.evaluate("http://pаytm.xyz/login")  # Cyrillic 'а'
    names = {s.name for s in signals}
    assert "homograph_domain" in names
    assert len({s.basis for s in signals if s.name in names}) < len(names), (
        "every signal claimed its own basis, so one lookalike domain would count "
        "as enough independent evidence to auto-block"
    )


def test_independent_witness_count_is_not_the_signal_count():
    signals = link_signals.evaluate("http://pаytm.xyz/login")
    assert link_signals.independent_witnesses(signals) < len(signals)


def test_display_text_mismatch_is_a_separate_witness_from_the_url_itself():
    """The mismatch is an observation about the *pair*, not about either string,
    so it is genuinely independent evidence and must count as such."""
    signals = link_signals.evaluate(
        "http://paytm-refund.info/verify", display_text="www.hdfcbank.com"
    )
    bases = {s.basis for s in signals}
    assert len(bases) >= 2
    assert link_signals.independent_witnesses(signals) >= 2


# --- the checks -----------------------------------------------------------


def test_punycode_domain_is_flagged():
    signals = link_signals.evaluate("http://xn--pytm-4qa.com/login")
    assert "homograph_domain" in {s.name for s in signals}


def test_mixed_script_domain_is_flagged_before_it_is_encoded():
    """A raw Cyrillic character reaches us as-is from an SMS; waiting for
    punycode would miss it."""
    signals = link_signals.evaluate("http://pаytm.com/login")
    assert "homograph_domain" in {s.name for s in signals}


def test_a_genuine_indic_domain_is_not_called_a_homograph():
    """The false-positive half. A Devanagari domain is a normal thing in this
    product's market, and mixed-script detection that fires on it would block
    legitimate Indian sites."""
    signals = link_signals.evaluate("https://सरकार.भारत/")
    assert "homograph_domain" not in {s.name for s in signals}


def test_brand_lookalike_is_flagged():
    signals = link_signals.evaluate("http://paytnn.com/refund")
    assert "brand_lookalike" in {s.name for s in signals}


def test_the_real_brand_domain_is_not_a_lookalike():
    assert link_signals.evaluate("https://www.paytm.com/offers") == []


def test_suspicious_tld_is_flagged():
    signals = link_signals.evaluate("http://verify-account.xyz/")
    assert "suspicious_tld" in {s.name for s in signals}


def test_high_entropy_host_is_flagged():
    signals = link_signals.evaluate("http://x7f2q9k3mz8vb1n4.com/")
    assert "high_entropy_host" in {s.name for s in signals}


def test_display_text_target_mismatch_is_flagged():
    """The most common phishing tell in HTML."""
    signals = link_signals.evaluate(
        "http://evil.example/login", display_text="https://www.icicibank.com/login"
    )
    assert "display_target_mismatch" in {s.name for s in signals}


def test_display_text_that_is_not_a_url_is_not_a_mismatch():
    """"Click here" is not a lie about where the link goes."""
    signals = link_signals.evaluate("https://www.hdfcbank.com/", display_text="Click here")
    assert "display_target_mismatch" not in {s.name for s in signals}


# --- it must not fetch ----------------------------------------------------


def test_evaluate_makes_no_network_call(monkeypatch):
    """The whole premise of stage 1 is zero new attack surface. A fetch added
    here would move it to stage 2 without anyone noticing."""
    import socket

    def explode(*args, **kwargs):
        raise AssertionError("stage 1 attempted a network connection")

    monkeypatch.setattr(socket.socket, "connect", explode)
    monkeypatch.setattr(socket, "create_connection", explode)
    monkeypatch.setattr(socket, "getaddrinfo", explode)

    link_signals.evaluate("http://paytm-refund.info/verify")


# --- malformed input ------------------------------------------------------


@pytest.mark.parametrize(
    "value", ["", "   ", "not a url", "http://", "://missing-scheme", "javascript:alert(1)"]
)
def test_unparseable_input_returns_no_signals_rather_than_raising(value):
    """This runs on the hot path against text a scammer wrote. An exception here
    is a 500 on a scan, which fails unsafe."""
    assert link_signals.evaluate(value) == []
