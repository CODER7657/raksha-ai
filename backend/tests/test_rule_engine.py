"""The offline rule engine is the last line of defence: when both LLM
providers are down it is the only thing standing between a user and a scam.
Every case below is a message shape that was silently missed before, so these
are regression tests, not illustrations.
"""

import pytest

from app.services.rule_engine import RULES, offline_flag, offline_rule_hits


def ids_for(text: str, language: str = "en") -> set[str]:
    return {hit.rule_id for hit in offline_rule_hits(text, language)}


# --- Regressions: each of these returned zero hits before the rewrite -------

@pytest.mark.parametrize(
    "text, expected_id",
    [
        # "share" before "OTP" — the original pattern required the reverse
        # order and so could not fire on any realistic phrasing.
        ("Please share OTP 123456 to complete the transaction", "otp_share"),
        ("Share your OTP now", "otp_share"),
        ("Kindly send the OTP received on your mobile", "otp_share"),
        # "expiring", not "expire" — the original matched only the exact stem.
        ("Your KYC is expiring today", "kyc_expiry"),
        ("KYC verification pending, update immediately", "kyc_expiry"),
        # "blocked" contains "lock" but not at a word boundary, and account
        # comes first — the original failed on both counts.
        ("Your account will be blocked", "account_lock"),
        ("Dear customer your account has been suspended", "account_lock"),
    ],
)
def test_previously_missed_messages_now_fire(text: str, expected_id: str):
    assert expected_id in ids_for(text)


def test_the_canonical_scam_sms_fires_all_three_rules():
    """The most common Indian scam SMS shape. Before the rewrite this returned
    an empty list, which meant a 503 rather than a conservative verdict when
    the LLM path was unavailable."""
    text = (
        "Dear customer, your KYC is expiring today. Share your OTP now "
        "or your account will be blocked."
    )
    assert ids_for(text) >= {"otp_share", "kyc_expiry", "account_lock"}


# --- Rules that already worked must keep working ---------------------------

@pytest.mark.parametrize(
    "text, expected_id",
    [
        ("You have won a lottery of Rs 10,00,000", "lottery_win"),
        ("Claim your refund now, click here", "refund_click"),
        ("Urgently verify your details", "urgent_verify"),
        ("We will lock your account today", "account_lock"),
        ("Your KYC will expire tomorrow", "kyc_expiry"),
    ],
)
def test_existing_rules_still_fire(text: str, expected_id: str):
    assert expected_id in ids_for(text)


# --- Ordinary messages must stay quiet -------------------------------------

@pytest.mark.parametrize(
    "text",
    [
        "Your order has been shipped and will arrive on Tuesday",
        "Rs 500 debited from your account ending 4321 at BigBazaar",
        "Happy birthday! Hope you have a great day",
        "Your electricity bill of Rs 1,240 is due on 20th",
    ],
)
def test_benign_messages_do_not_fire(text: str):
    assert ids_for(text) == set()


def test_a_bank_warning_is_flagged_and_that_is_deliberate():
    """A legitimate "never share your OTP" notice trips otp_share. Suppressing
    it would need a negation heuristic that could equally suppress "do not
    delay, share your OTP now" — the module errs toward over-warning on
    purpose. If this test ever needs changing, that trade-off is being
    reversed, so read the module docstring first."""
    assert "otp_share" in ids_for("Bank will never ask you to share your OTP")


# --- Structure of a hit -----------------------------------------------------

def test_hit_carries_the_text_that_tripped_it():
    hits = offline_rule_hits("Please share OTP 123456 now", "en")
    hit = next(h for h in hits if h.rule_id == "otp_share")
    assert hit.matched_text
    assert hit.matched_text in "Please share OTP 123456 now"
    assert hit.pattern


def test_each_rule_fires_at_most_once():
    text = "Share OTP, share OTP, share the OTP again"
    hits = offline_rule_hits(text, "en")
    assert len(hits) == len({h.rule_id for h in hits})


def test_offline_flag_stays_backwards_compatible():
    """scan.py's degraded path and the community counter both still call this."""
    flags = offline_flag("Share your OTP now", "en")
    assert isinstance(flags, list)
    assert all(isinstance(f, str) for f in flags)
    assert flags


# --- Indic and code-mixed ---------------------------------------------------

def test_hindi_message_fires():
    assert "otp_share" in ids_for("कृपया अपना ओटीपी शेयर करें", "hi")


def test_gujarati_message_fires():
    assert "kyc_expiry" in ids_for("તમારું કેવાયસી અપડેટ કરો", "gu")


def test_code_mixed_hindi_message_hits_the_english_rule():
    """Indian scam SMS routinely mixes scripts — an English "OTP" inside Hindi
    copy must still fire, which is why English rules run after the language's
    own."""
    assert "otp_share" in ids_for("अपना OTP share karein turant", "hi")


def test_rule_ids_are_shared_across_languages():
    """The frontend looks a rule id up in one `trace.rules.*` bundle, so an id
    must mean the same thing in every language it appears in."""
    en_ids = {r.rule_id for r in RULES["en"]}
    for language, rules in RULES.items():
        unknown = {r.rule_id for r in rules} - en_ids
        assert not unknown, f"{language} has rule ids absent from en: {unknown}"


def test_no_duplicate_rule_ids_within_a_language():
    for language, rules in RULES.items():
        ids = [r.rule_id for r in rules]
        assert len(ids) == len(set(ids)), f"{language} has duplicate rule ids"
