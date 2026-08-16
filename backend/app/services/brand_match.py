"""Brand-token matching shared by the UPI checker and A2 stage 1.

This was `upi_check.py`'s private guts. #115 asks stage 1 to reuse the
Levenshtein and the brand allowlist and *generalise in place* rather than
rebuild, so they moved here and `upi_check` imports them back. A second
Levenshtein and a second brand list would drift, and the way they would drift is
that somebody adds a bank to one of them.

Nothing here does I/O or reads anything a scammer controls beyond the string
being checked, which is what lets every signal built on it report
`deterministic: True`.
"""

import math

#: Brands a scammer imitates in this market. Extended from `upi_check.py`'s
#: original nine — the additions are the wallets and banks that show up in the
#: corpus rather than a guess at the whole Indian banking sector, because every
#: entry here is a false-positive surface as much as a detection.
#: **Nothing under four characters goes in this list.** `upi` and `pnb` were in
#: an earlier draft and both had to come out: at the distance-2 threshold
#: `upi_check` uses, `upi` calls `ubi@ybl` (Union Bank of India) a misspelling
#: and `pnb` does the same to `bob@ybl` (Bank of Baroda) and `iob@ybl` (Indian
#: Overseas Bank). Three real banks, reported as scams, from two list entries.
KNOWN_BRANDS = [
    "paytm", "phonepe", "googlepay", "gpay", "bhim",
    "sbi", "onlinesbi", "hdfc", "hdfcbank", "icici", "icicibank",
    "axisbank", "kotak", "bankofbaroda", "canarabank", "unionbank",
]

#: Cheap generic TLDs. Not evidence on their own — plenty of legitimate sites
#: use them — which is why this reports a named signal that the blocking policy
#: is free to weigh, rather than a verdict.
SUSPICIOUS_TLDS = {".info", ".xyz", ".top", ".click", ".online", ".site"}

#: Subdomain labels that carry no brand claim, skipped before lookalike
#: matching so `www` is not measured against a bank name.
IGNORED_LABELS = {"www", "m", "web", "app", "secure", "login", "com", "co", "in", "org", "net"}

#: Real institutions that sit within edit distance of a brand above and are
#: **not** imitations of it. Edit distance cannot separate these — `ubi` and
#: `cbi` are one edit from `sbi`, and so is a genuine typosquat — so the only
#: honest fix is to name the legitimate ones.
#:
#: This is the allowlist half of the check and it is the half that matters:
#: A2's benign set is larger than its phishing set, and reporting Union Bank of
#: India as a lookalike of SBI during a fraud alert is us causing the harm we
#: exist to prevent. Grows whenever a false positive is found; entries are real
#: institutions, never guesses.
KNOWN_LEGITIMATE = {
    "ubi", "unionbankofindia", "cbi", "centralbank", "idbi", "iob", "bob",
    "pnb", "canarabank", "indianbank", "bankofindia", "boi", "uco", "psb",
    "ybl", "okaxis", "oksbi", "okhdfcbank", "okicici", "ibl", "axl", "apl",
    "upi", "npci", "rbi", "airtel", "jio", "amazon", "flipkart",
}


def levenshtein(a: str, b: str) -> int:
    """Edit distance. Iterative and row-at-a-time — this runs on the hot path
    against every host label in a message."""
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


def nearest_brand(token: str, *, max_distance: int = 2) -> tuple[str, int] | None:
    """The closest brand within `max_distance`, or None.

    An exact match returns None rather than distance 0: `paytm.com` containing
    `paytm` is the expected case, not the suspicious one. Only a *near* miss is
    evidence.

    Short brands make a fixed distance proportionally loose — `sbl` is one edit
    from `sbi` — so the threshold tightens for tokens under five characters.
    `test_upi_check.py` pins the looser original behaviour for the UPI path,
    which is why that caller keeps its own loop rather than adopting this.
    """
    token = token.strip().lower()
    if not token or token in KNOWN_BRANDS or token in KNOWN_LEGITIMATE:
        return None

    best: tuple[str, int] | None = None
    for brand in KNOWN_BRANDS:
        limit = 1 if min(len(brand), len(token)) < 5 else max_distance
        distance = levenshtein(token, brand)
        if 0 < distance <= limit and (best is None or distance < best[1]):
            best = (brand, distance)
    return best


def shannon_entropy(value: str) -> float:
    if not value:
        return 0.0
    length = len(value)
    return -sum(
        (count / length) * math.log2(count / length)
        for count in (value.count(c) for c in set(value))
    )


def looks_machine_generated(label: str) -> bool:
    """Whether a host label looks algorithmically generated rather than chosen.

    **Entropy alone does not work here, and the measurements say so.** Shannon
    entropy over a short domain label is close to a length proxy — every
    distinct character adds to it:

        x7f2q9k3mz8vb1n4   H=4.00   (algorithmic)
        secure-login-update H=3.79  (hand-written phishing)
        verify-account     H=3.66   (hand-written phishing)
        paytm-refund       H=3.58   (hand-written phishing)
        hdfcbank           H=3.00   (a real bank)

    A threshold that catches the first would flag the next three, and those are
    the shapes a *legitimate* campaign page also uses. What actually separates
    them is character composition: generated labels carry digits or run out of
    vowels, and hand-written ones do neither.

    Requiring entropy **and** a composition tell keeps the real bank and the
    three hand-written strings out, which matters more than catching one more
    generated domain — a blocked bank domain during a fraud alert is us causing
    the harm.

    ASCII labels only. A Devanagari label has no ASCII vowels by construction,
    so applying the vowel test to one would flag every genuine Indic domain.
    """
    core = label.replace("-", "")
    if not core or not core.isascii():
        return False
    if shannon_entropy(label) < 3.5:
        return False
    digit_ratio = sum(c.isdigit() for c in core) / len(core)
    vowel_ratio = sum(c in "aeiou" for c in core) / len(core)
    return digit_ratio >= 0.25 or vowel_ratio <= 0.10
