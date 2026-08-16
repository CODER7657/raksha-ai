"""UPI ID / link lookalike (typosquatting) checker.

Deliberately independent of the LLM — pure pattern matching, so it keeps
working even if both LLM providers are down. Levenshtein distance against a
small allowlist of legitimate brand domains/handles catches the common
"paytm-refund.info" / "paytm.help.in" style scams.

The Levenshtein, the brand allowlist and the TLD set now live in
`brand_match.py`, shared with A2 stage 1 (#115). The matching loop below stays
here rather than moving to `brand_match.nearest_brand`: this path is tuned for
UPI handles and its behaviour is pinned by `test_upi_check.py`, while stage 1
tightens the threshold on short tokens. Same primitives, two deliberately
different policies, one place to add a bank.
"""

import re

from app.services.brand_match import KNOWN_BRANDS, SUSPICIOUS_TLDS, levenshtein


def check_upi_or_link(value: str) -> dict:
    value = value.strip().lower()
    is_upi = bool(re.match(r"^[\w.\-]{2,256}@[a-z]{2,64}$", value))

    reasons = []
    for brand in KNOWN_BRANDS:
        if brand in value:
            continue  # exact brand mention is expected, not suspicious by itself
        distance = min(levenshtein(value.split("@")[0].split(".")[0], brand), 99)
        if 0 < distance <= 2 and len(value) > 3:
            reasons.append(f"Looks like a misspelling of '{brand}'")

    for tld in SUSPICIOUS_TLDS:
        if value.endswith(tld):
            reasons.append(f"Uses a suspicious domain ending ({tld}) rarely used by real banks/wallets")

    return {
        "is_upi": is_upi,
        "is_suspicious": len(reasons) > 0,
        "reasons": reasons,
    }
