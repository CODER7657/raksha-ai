"""Email phishing via share-to-app. `PHASE-2-PLAN.md` §01b, #115 §2.

Most of the work is already A2: the dangerous part of a phishing email is the
link, and stage 1 handles links. What email adds is a **sender**, and that is
what this module is about.

## The constraint that shapes everything here

Share-to-app delivers `text/plain` through `EXTRA_TEXT` and nothing else —
`AndroidManifest.xml` declares only that mime type and `MainActivity.handleShare`
reads only that extra. So what arrives is a body, sometimes with a mail client's
quoted "Forwarded message" block above it.

**SPF and DKIM cannot be computed from that, and not as an edge case.** SPF
needs the IP that connected to the receiving server. DKIM needs the exact raw
bytes of the message plus its signature header. Sharing destroys both. Even
reading the *result* needs `Authentication-Results`, a header the receiving
server adds and which a shared body does not carry.

So §01b's "model-independent second witness" is real and is unreachable through
the route §115 §2 mandates. The honest split, and what these tests pin:

- headers present  -> read what the receiving server concluded
- headers absent   -> **say so**, and never imply the sender checked out

## Why "cannot verify" is not a Signal

The subtle one, and the reason `EmailAssessment` exists instead of a bare list.

`independent_witnesses` counts signals toward blocking. If inability to verify a
sender were a `Signal`, **every forwarded email would carry a free witness
toward being blocked** — an absence of evidence promoted into evidence, on the
most common input this feature has. So it is a `caveat`: user-facing, honest,
and never counted.
"""

import pytest

from app.services import email_signals, link_signals

FORWARDED = """\
---------- Forwarded message ---------
From: HDFC Bank <alerts@hdfcbank.com>
Date: Sat, 16 Aug 2026 at 10:22
Subject: Your account will be blocked
To: <user@example.com>

Dear Customer, your KYC is pending. Verify at http://hdfc-verify.info/kyc
"""

RAW_FAILING = """\
Delivered-To: user@example.com
Authentication-Results: mx.google.com;
       dkim=fail header.i=@hdfcbank.com;
       spf=fail (google.com: domain of bounce@evil.xyz does not designate permitted sender) smtp.mailfrom=bounce@evil.xyz;
       dmarc=fail (p=REJECT sp=REJECT dis=NONE) header.from=hdfcbank.com
From: HDFC Bank <alerts@hdfcbank.com>
Subject: Your account will be blocked

Dear Customer, verify at http://hdfc-verify.info/kyc
"""

RAW_PASSING = """\
Delivered-To: user@example.com
Authentication-Results: mx.google.com;
       dkim=pass header.i=@hdfcbank.com;
       spf=pass (google.com: domain of alerts@hdfcbank.com designates 1.2.3.4 as permitted sender) smtp.mailfrom=alerts@hdfcbank.com;
       dmarc=pass (p=REJECT sp=REJECT dis=NONE) header.from=hdfcbank.com
From: HDFC Bank <alerts@hdfcbank.com>
Subject: Your September statement

Your statement is ready at https://www.hdfcbank.com/statements
"""


# --- parsing --------------------------------------------------------------


def test_a_forwarded_block_yields_the_claimed_sender():
    parsed = email_signals.parse(FORWARDED)
    assert parsed.headers["from"] == "HDFC Bank <alerts@hdfcbank.com>"
    assert parsed.header_source == "forwarded_block"


def test_a_raw_message_yields_real_headers():
    parsed = email_signals.parse(RAW_FAILING)
    assert parsed.header_source == "raw"
    assert "authentication-results" in parsed.headers


def test_a_body_with_no_headers_at_all_still_parses():
    parsed = email_signals.parse("Your KYC is pending, verify at http://x.example/")
    assert parsed.header_source == "none"
    assert parsed.headers == {}
    assert parsed.body


def test_the_body_excludes_the_forwarded_header_block():
    """The header block is metadata. Leaving it in the body would run the scam
    rules over `Date:` and `To:` lines and report them as content."""
    parsed = email_signals.parse(FORWARDED)
    assert "Dear Customer" in parsed.body
    assert "Forwarded message" not in parsed.body
    assert "Subject:" not in parsed.body


@pytest.mark.parametrize("value", ["", "   ", "\n\n\n", "From:", "::::"])
def test_malformed_input_does_not_raise(value):
    """Hot-path text a scammer wrote. An exception here is a 500 on a scan."""
    email_signals.evaluate(value)


# --- sender verification --------------------------------------------------


def test_a_shared_email_without_headers_is_reported_unverifiable():
    """The DEFAULT case for share-to-app, not an edge case."""
    assessment = email_signals.evaluate(FORWARDED)
    assert assessment.sender_verification == "unverifiable"


def test_unverifiable_never_reads_as_verified():
    """#115: report 'could not verify sender', never 'sender verified'."""
    assessment = email_signals.evaluate(FORWARDED)
    assert assessment.caveats
    joined = " ".join(assessment.caveats).lower()
    assert "could not verify" in joined
    assert "verified" not in joined.replace("could not verify", "")


def test_a_failing_dmarc_is_read_from_the_receiving_server():
    assessment = email_signals.evaluate(RAW_FAILING)
    assert assessment.sender_verification == "fail"
    assert "dmarc_fail" in {s.name for s in assessment.signals}


def test_a_passing_dmarc_produces_no_sender_signal():
    """A pass is the absence of evidence against, not evidence for. It must not
    add a signal in either direction — and it must not suppress the link checks
    either, which is what a naive 'trusted sender' shortcut would do."""
    assessment = email_signals.evaluate(RAW_PASSING)
    assert assessment.sender_verification == "pass"
    assert not [s for s in assessment.signals if s.basis == email_signals.BASIS_SENDER_AUTH]


def test_we_never_claim_to_have_computed_spf_or_dkim_ourselves():
    """We read a result the receiving server reached. Claiming we checked would
    be a stronger statement than we can support: SPF needs the connecting IP and
    DKIM needs the raw bytes, and sharing destroys both."""
    assessment = email_signals.evaluate(RAW_FAILING)
    detail = " ".join(s.detail for s in assessment.signals).lower()
    assert "mx.google.com" in detail or "receiving mail server" in detail


# --- cannot-verify is not evidence ----------------------------------------


def test_being_unable_to_verify_adds_no_countable_witness():
    """The tightest constraint in this file.

    If inability to verify were a Signal, every forwarded email would carry a
    free witness toward blocking — absence of evidence promoted to evidence, on
    the most common input this feature has.
    """
    assessment = email_signals.evaluate(FORWARDED)
    assert assessment.sender_verification == "unverifiable"
    assert not [s for s in assessment.signals if s.basis == email_signals.BASIS_SENDER_AUTH]


def test_an_unverifiable_sender_does_not_change_the_witness_count():
    with_headers = email_signals.evaluate(RAW_PASSING)
    without = email_signals.evaluate(FORWARDED)
    # Both bodies carry one link; only the FORWARDED one is a phishing domain,
    # so the difference must come from the link, never from the missing headers.
    assert link_signals.independent_witnesses(with_headers.signals) == 0
    assert all(s.basis != email_signals.BASIS_SENDER_AUTH for s in without.signals)


# --- display-name spoofing ------------------------------------------------


def test_a_brand_display_name_on_an_unrelated_domain_is_flagged():
    """Works on shared text with no headers at all, which is what makes it the
    signal that survives the share-to-app constraint."""
    assessment = email_signals.evaluate(
        'From: HDFC Bank <winner12@gmail.com>\n\nClaim your refund at http://x.example/'
    )
    assert "display_name_brand_mismatch" in {s.name for s in assessment.signals}


def test_the_real_bank_sending_from_its_own_domain_is_not_flagged():
    assessment = email_signals.evaluate(
        'From: HDFC Bank <alerts@hdfcbank.com>\n\nYour statement is ready.'
    )
    assert "display_name_brand_mismatch" not in {s.name for s in assessment.signals}


def test_a_display_name_with_no_brand_in_it_is_not_flagged():
    """The false-positive half. Most mail is from people, not brands."""
    assessment = email_signals.evaluate(
        'From: Ravi Kumar <ravi@gmail.com>\n\nAre we still on for lunch?'
    )
    assert not assessment.signals


def test_display_name_spoofing_is_its_own_witness():
    """It is an observation about the *pair* — the claimed identity against the
    domain that actually sent it — so neither half explains it away, exactly as
    with display/target mismatch in stage 1."""
    assessment = email_signals.evaluate(
        'From: HDFC Bank <winner12@gmail.com>\n\nRefund at http://hdfc-verify.info/kyc'
    )
    assert link_signals.independent_witnesses(assessment.signals) >= 2


# --- the links in the body ------------------------------------------------


def test_links_in_the_body_are_evaluated_by_stage_one():
    """Email is mostly a delivery question. The detection is A2's."""
    assessment = email_signals.evaluate(FORWARDED)
    assert "brand_impersonation" in {s.name for s in assessment.signals}


def test_a_clean_email_from_a_real_bank_produces_nothing():
    """The half that costs users. A statement notice must be silent."""
    assessment = email_signals.evaluate(RAW_PASSING)
    assert assessment.signals == []


# --- attachments are out of scope -----------------------------------------


def test_an_attachment_is_neither_parsed_nor_scored():
    """#115: attachments are explicitly out of scope — that is malware
    analysis, a different product with a different risk profile. The test exists
    so adding one is a deliberate decision rather than a quiet feature."""
    with_attachment = (
        "From: HDFC Bank <alerts@hdfcbank.com>\n"
        "Content-Type: multipart/mixed; boundary=xyz\n\n"
        "--xyz\nContent-Type: text/plain\n\nYour statement is attached.\n"
        "--xyz\nContent-Type: application/pdf; name=statement.pdf\n"
        "Content-Disposition: attachment; filename=statement.pdf\n\nJVBERi0xLjQK\n--xyz--\n"
    )
    assessment = email_signals.evaluate(with_attachment)
    names = {s.name for s in assessment.signals}
    assert not any("attach" in name or "malware" in name for name in names)
