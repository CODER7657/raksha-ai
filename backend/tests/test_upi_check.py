"""Pins `upi_check.check_upi_or_link` before A2 stage 1 generalises its guts.

`upi_check.py` shipped with no tests. #115 says stage 1 must reuse its
Levenshtein and brand allowlist and *generalise in place* rather than rebuild,
which means editing a live detection path with no coverage under it. These
tests exist so that refactor is provably behaviour-preserving rather than
believed to be.

Every expectation here was taken from the code as it ran before the refactor,
including the ones that are arguably wrong. Pinning current behaviour and
changing it are two different pull requests; where the pinned behaviour looks
like a bug it is marked rather than fixed.
"""

import pytest

from app.services.upi_check import check_upi_or_link

# --- UPI id recognition ---------------------------------------------------


@pytest.mark.parametrize("value", ["paytm@ybl", "hdfc@okaxis", "paytnn@ybl", "icici@icici"])
def test_a_handle_is_recognised_as_upi(value):
    assert check_upi_or_link(value)["is_upi"] is True


@pytest.mark.parametrize("value", ["http://paytm-refund.info", "verify.xyz", "x@ybl"])
def test_a_non_handle_is_not_recognised_as_upi(value):
    """`x@ybl` fails the pattern because the local part needs two characters."""
    assert check_upi_or_link(value)["is_upi"] is False


# --- brand lookalikes -----------------------------------------------------


def test_a_misspelled_brand_handle_is_suspicious():
    result = check_upi_or_link("paytnn@ybl")
    assert result["is_suspicious"] is True
    assert result["reasons"] == ["Looks like a misspelling of 'paytm'"]


def test_the_real_brand_handle_is_not_suspicious():
    assert check_upi_or_link("paytm@ybl")["is_suspicious"] is False


def test_an_unrelated_bank_handle_is_not_suspicious():
    assert check_upi_or_link("hdfc@okaxis")["is_suspicious"] is False


def test_edit_distance_one_from_a_short_brand_fires():
    """Pinned, and worth a second look later: `sbl` is one edit from `sbi`, so a
    genuine handle beginning `sbl` is reported as a misspelling. Short brands
    make the distance-2 threshold proportionally loose. Recorded rather than
    changed — the false-positive half of A2 is where this gets revisited."""
    assert check_upi_or_link("sbl@ybl")["reasons"] == ["Looks like a misspelling of 'sbi'"]


# --- TLD reputation -------------------------------------------------------


@pytest.mark.parametrize("tld", [".info", ".xyz", ".top", ".click", ".online", ".site"])
def test_each_suspicious_tld_is_flagged(tld):
    result = check_upi_or_link(f"http://verify-account{tld}")
    assert result["is_suspicious"] is True
    assert any(tld in reason for reason in result["reasons"])


def test_a_brand_on_a_suspicious_tld_is_caught_by_the_tld_not_the_brand():
    """The docstring advertises `paytm-refund.info`, and it is caught — but by
    the TLD rule. The brand rule skips it, because `paytm` appears verbatim and
    an exact brand mention is treated as expected rather than suspicious.

    Pinned deliberately: it is the shape of scam the module names, and the fact
    that only one of its two rules covers it is the kind of thing that quietly
    stops being true.

    Stage 1 does not inherit the gap, but not via edit distance — `paytm-refund`
    is seven edits from `paytm` and reads as unrelated to any distance check.
    `link_signals.brand_impersonation` covers it instead, by matching
    hyphen-separated parts of the host against the brand list and comparing the
    registrable label."""
    result = check_upi_or_link("http://paytm-refund.info")
    assert result["reasons"] == [
        "Uses a suspicious domain ending (.info) rarely used by real banks/wallets"
    ]


# --- shape ----------------------------------------------------------------


def test_input_is_case_and_whitespace_insensitive():
    assert check_upi_or_link("  PayTNN@YBL  ") == check_upi_or_link("paytnn@ybl")


def test_result_keys_are_stable():
    assert set(check_upi_or_link("paytm@ybl")) == {"is_upi", "is_suspicious", "reasons"}
