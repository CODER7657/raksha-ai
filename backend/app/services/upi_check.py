"""UPI ID / link lookalike (typosquatting) checker.

Deliberately independent of the LLM — pure pattern matching, so it keeps
working even if both LLM providers are down. Levenshtein distance against a
small allowlist of legitimate brand domains/handles catches the common
"paytm-refund.info" / "paytm.help.in" style scams.
"""

import re

KNOWN_BRANDS = ["paytm", "phonepe", "googlepay", "gpay", "bhim", "sbi", "hdfc", "icici", "axisbank"]

SUSPICIOUS_TLDS = {".info", ".xyz", ".top", ".click", ".online", ".site"}


def _levenshtein(a: str, b: str) -> int:
    if len(a) < len(b):
        a, b = b, a
    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        current = [i]
        for j, cb in enumerate(b, 1):
            cost = 0 if ca == cb else 1
            current.append(min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + cost))
        previous = current
    return previous[-1]


def check_upi_or_link(value: str) -> dict:
    value = value.strip().lower()
    is_upi = bool(re.match(r"^[\w.\-]{2,256}@[a-z]{2,64}$", value))

    reasons = []
    for brand in KNOWN_BRANDS:
        if brand in value:
            continue  # exact brand mention is expected, not suspicious by itself
        distance = min(_levenshtein(value.split("@")[0].split(".")[0], brand), 99)
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
