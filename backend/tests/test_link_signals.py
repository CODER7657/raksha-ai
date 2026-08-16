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


def test_a_host_beginning_with_w_is_not_confused_with_a_www_prefix():
    """`lstrip("www.")` strips *characters*, not a prefix — `wine.com` becomes
    `ine.com` and `web.example` becomes `eb.example`. Two unrelated hosts could
    therefore normalise to the same string and a real mismatch be suppressed.

    Found by ruff (PLE1310), not by the tests above, which is the useful part:
    every case they exercised happened to start with a literal `www.`."""
    signals = link_signals.evaluate(
        "http://ine.com/login", display_text="https://wine.com/login"
    )
    assert "display_target_mismatch" in {s.name for s in signals}


def test_a_www_prefix_alone_is_still_not_a_mismatch():
    """The behaviour the buggy line was reaching for, kept."""
    signals = link_signals.evaluate(
        "https://www.hdfcbank.com/", display_text="hdfcbank.com"
    )
    assert "display_target_mismatch" not in {s.name for s in signals}


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


# --- A6 findings ----------------------------------------------------------
# #115: "Point A6 at every detector you build. If it can mutate past your
# checks, that is a benchmark case before it is a production gap."
#
# A deterministic sweep of 31 known URL-evasion techniques against the first
# version of this module caught 20 and was evaded by 11. Each test below is one
# of those evasions. They are grouped by what the evasion revealed, because
# several of them are one bug wearing different hats.


def test_a_bare_host_with_a_path_is_parsed():
    """SMS does not contain `http://`. People send `paytm-refund.info/verify`,
    and the first version parsed a bare host only when it had no path — so the
    single most common real-world shape went unchecked."""
    signals = link_signals.evaluate("paytm-refund.info/verify")
    assert "brand_impersonation" in {s.name for s in signals}


def test_a_bare_ip_host_is_flagged():
    """No bank serves from a bare IP. Cheap to check and it defeats every
    host-name check at once — there is no name to compare."""
    signals = link_signals.evaluate("http://203.0.113.44/paytm/verify")
    assert "ip_address_host" in {s.name for s in signals}


def test_an_integer_encoded_ip_host_is_flagged():
    """`3405803820` is `203.0.113.44` written as a single integer, which most
    browsers still resolve and most naive parsers do not recognise as an IP."""
    signals = link_signals.evaluate("http://3405803820/paytm")
    assert "ip_address_host" in {s.name for s in signals}


def test_a_url_shortener_is_flagged():
    """A shortener hides the destination completely — every static check has
    nothing left to read.

    Stage 1 cannot resolve it without fetching, which is stage 2 by definition.
    So the honest signal is not "this is malicious" but "the destination is
    hidden", which is a fact, is deterministic, and is what makes the case worth
    escalating to a stage that may fetch."""
    signals = link_signals.evaluate("http://bit.ly/3xK9pQ")
    assert "hidden_destination" in {s.name for s in signals}


def test_a_url_embedded_in_a_query_parameter_is_evaluated_too():
    """The open-redirect shape. The host is `google.com` and entirely genuine;
    the payload is in `?q=`. Reading only the outer host means a legitimate
    domain launders the whole check."""
    signals = link_signals.evaluate(
        "https://www.google.com/url?q=http://paytm-refund.info/verify"
    )
    assert "brand_impersonation" in {s.name for s in signals}


def test_an_embedded_url_does_not_recurse_without_bound():
    """A nested chain is a cheap way to make one scan do arbitrary work."""
    nested = "http://a.example/?q=http://b.example/?q=http://c.example/?q=http://paytm-refund.info/"
    link_signals.evaluate(nested)  # must return, not hang


def test_a_brand_under_a_multi_part_suffix_is_an_impersonation():
    """The finding that disproved a claim in this module's own docstring.

    `hdfcbank.com.co` and `hdfcbank.com` produce an *identical* registrable
    label, so comparing the label to the brand cannot tell them apart — and the
    first version therefore treated `hdfcbank.com.co` as HDFC's own domain and
    skipped the check entirely.

    `_registrable_label` claimed that where it was wrong it erred towards
    treating a subdomain as registrable, "which produces a warning rather than a
    missed detection". This is the case where it errs the other way and the
    result is a missed detection. The fix compares the full registrable domain
    against the brand's known domains rather than comparing labels."""
    signals = link_signals.evaluate("http://vvww.hdfcbank.com.co/")
    assert "brand_impersonation" in {s.name for s in signals}


def test_the_real_bank_domain_still_is_not_an_impersonation():
    """The other half of the previous test, and the one that costs users if it
    breaks."""
    assert link_signals.evaluate("https://www.hdfcbank.com/") == []
    assert link_signals.evaluate("https://netbanking.hdfcbank.com/login") == []


@pytest.mark.parametrize("tld", [".icu", ".cc", ".buzz", ".win", ".rest", ".quest"])
def test_known_abuse_tlds_are_flagged(tld):
    """Whack-a-mole by nature, which is exactly why `suspicious_tld` is a weak
    named signal rather than a verdict — the blocking policy needs two
    independent witnesses and this can only ever be one of them."""
    signals = link_signals.evaluate(f"http://verify-account{tld}/")
    assert "suspicious_tld" in {s.name for s in signals}


# --- finding links in a message -------------------------------------------
# The entry point A6 exposed by not existing: stage 1 could evaluate a URL and
# nothing could get a URL out of an SMS.


def test_a_bare_link_is_found_in_ordinary_sms_text():
    """The shape people actually receive — no scheme, mid-sentence."""
    found = link_signals.extract_urls(
        "Your KYC expires today. Verify at paytm-refund.info/verify or account blocked."
    )
    assert found == ["paytm-refund.info/verify"]


def test_trailing_sentence_punctuation_is_not_part_of_the_link():
    assert link_signals.extract_urls("Visit www.hdfcbank.com.") == ["www.hdfcbank.com"]


@pytest.mark.parametrize(
    "text",
    [
        "Call 1800.123.4567 before 12.30pm.",
        "Amount Rs.5000 pending.",
        "no links here at all, version 1.2.3 released",
        "mail me at ravi@paytm.com please",
    ],
)
def test_prose_that_merely_contains_dots_is_not_a_link(text):
    """The false-positive half. Matching prose would run brand comparisons
    against arbitrary words on the hot path, and an email address is not a link
    — treating one as a host would flag every message naming a real bank."""
    assert link_signals.extract_urls(text) == []


def test_the_number_of_links_taken_from_one_message_is_bounded():
    """A message stuffed with links is itself adversarial input, and this runs
    on the hot path."""
    text = " ".join(f"site{i}.example/p" for i in range(50))
    assert len(link_signals.extract_urls(text)) == 10


def test_the_same_link_twice_is_evaluated_once():
    found = link_signals.extract_urls("go to a.example/x and again A.EXAMPLE/x now")
    assert len(found) == 1


# --- A6 findings deliberately NOT fixed -----------------------------------


def test_a_brand_name_in_the_path_is_not_flagged():
    """Recorded as a benchmark case rather than fixed, and the reasoning
    matters more than the case.

    `secure-portal.net/paytm/login` does evade every check here. Flagging a
    brand name in a *path* would also flag every news article, every review
    site and every legitimate aggregator that mentions a bank — an enormous
    false-positive surface for a weak signal.

    A2's benign half is larger than its phishing half. This one belongs to the
    stages that read the page, where "the page is a Paytm login form on a
    domain that is not Paytm" is a strong signal instead of a guess."""
    assert link_signals.evaluate("http://secure-portal.net/paytm/login") == []
