"""A2 stage 1 — static link checks that never fetch the page.

`PHASE-2-PLAN.md` §01 stage 1. No sandbox, no agent, no LLM, no network. The
checks run against the URL string as it arrived in the message, so nothing here
executes or even retrieves anything an attacker controls.

## What this returns, and why the shape is the point

A list of **named signals**, each declaring `deterministic`. Not a score.

The blocking policy in §01 needs to count *independent* signals and needs at
least one that page content cannot influence. A blended total — "this URL scored
0.82" — cannot be taken apart again into "which two things agreed, and was
either immune to the page", so a total destroys exactly the property the policy
is built on. Stage 2 and 3 add signals to this same list; the policy stays a
counting rule rather than a threshold that has to be retuned each time.

## Independence, and why it is not the signal count

`basis` says which observation a signal derives from, and
`independent_witnesses` counts distinct bases rather than signals. Three checks
reading one host label are one witness however many names they report under.

Without this, `pаytm.xyz` spelled with a Cyrillic 'а' produces homograph +
lookalike + suspicious-TLD, and a policy counting signals would read three
independent confirmations and auto-block for every user on what is really one
observation about one string. Blocking a genuine bank domain during a fraud
alert is the harm this product exists to prevent, so the count is deliberately
the conservative one.
"""

import codecs
import unicodedata
from dataclasses import dataclass, field
from urllib.parse import urlsplit

from app.services.brand_match import (
    IGNORED_LABELS,
    KNOWN_BRANDS,
    KNOWN_LEGITIMATE,
    SUSPICIOUS_TLDS,
    looks_machine_generated,
    nearest_brand,
)

# --- bases ----------------------------------------------------------------
# One constant per distinct observation. Two signals sharing a basis are one
# witness; adding a signal means deciding, explicitly, whether it is looking at
# something the existing ones already looked at.

BASIS_HOST_LABEL = "host_label"
BASIS_TLD = "tld"
BASIS_DISPLAY_PAIR = "display_pair"
BASIS_FEED = "feed"
BASIS_DOMAIN_AGE = "domain_age"


@dataclass(frozen=True)
class Signal:
    """One named observation about a URL.

    `deterministic` is False only for a signal whose value could be influenced
    by content an attacker wrote — which nothing in stage 1 can be, and which
    the stage-3 model verdict will be.
    """

    name: str
    basis: str
    deterministic: bool
    detail: str
    evidence: dict = field(default_factory=dict)


def independent_witnesses(signals: list[Signal]) -> int:
    """How many genuinely separate things agree — the number the blocking
    policy counts, never `len(signals)`."""
    return len({signal.basis for signal in signals})


def has_deterministic_witness(signals: list[Signal]) -> bool:
    """The Confirmed tier requires at least one signal immune to page content."""
    return any(signal.deterministic for signal in signals)


# --- homograph detection --------------------------------------------------

#: Non-ASCII characters that render close enough to an ASCII letter to carry a
#: fake brand. Scoped to Cyrillic and Greek, which is where these attacks
#: actually come from — a full Unicode TR39 confusables table is a data file
#: and a refresh job, and belongs with the feed work rather than here.
#:
#: Deliberately does NOT include any Indic character. Devanagari, Tamil and the
#: rest are normal scripts for legitimate domains in this product's market, and
#: a table that mapped them to ASCII would flag every genuine Indic domain.
_CONFUSABLE_TO_ASCII = {
    "а": "a", "е": "e", "о": "o", "р": "p", "с": "c",
    "у": "y", "х": "x", "і": "i", "ѕ": "s", "ԁ": "d",
    "ӏ": "l", "в": "b", "м": "m", "н": "h", "к": "k",
    "т": "t", "г": "r", "ј": "j",
    "ο": "o", "α": "a", "ε": "e", "ρ": "p", "ν": "v",
    "τ": "t", "ι": "i", "κ": "k", "χ": "x",
}


def _decode_label(label: str) -> str:
    """Punycode labels analysed in their decoded form.

    `xn--pytm-4qa` is inert as ASCII and reads as `öpytm` once decoded, which is
    where the imitation is. Checking the encoded form would miss every IDN
    homograph, and checking only *encoded* labels would flag legitimate Indic
    domains, which reach us punycoded too.
    """
    if not label.startswith("xn--"):
        return label
    try:
        return codecs.decode(label[4:].encode("ascii"), "punycode")
    except Exception:
        return label


def _ascii_skeleton(label: str) -> str:
    """The label as it would read to someone who cannot see the difference."""
    decomposed = unicodedata.normalize("NFKD", label)
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    return "".join(_CONFUSABLE_TO_ASCII.get(c, c) for c in stripped)


def _scripts_in(label: str) -> set[str]:
    scripts = set()
    for char in label:
        if char.isascii() and not char.isalpha():
            continue  # digits and hyphens belong to no script
        try:
            scripts.add(unicodedata.name(char).split()[0])
        except ValueError:
            continue
    return scripts


def _is_homograph(label: str) -> tuple[bool, str]:
    """Two independent triggers, because neither catches the other's cases.

    Mixed script catches `pаytm` (Latin p, Cyrillic а). It does not catch a
    label written *entirely* in one non-Latin script, which is the stronger
    attack. The ASCII skeleton catches that one, and also catches `öpytm`,
    which is single-script Latin and so invisible to a mixed-script test.
    """
    scripts = _scripts_in(label)
    if len(scripts) > 1:
        return True, f"mixes {' and '.join(sorted(scripts)).lower()} characters"

    skeleton = _ascii_skeleton(label)
    if skeleton != label and skeleton.isascii() and any(c.isalpha() for c in skeleton):
        return True, f"non-ASCII characters that read as '{skeleton}'"

    return False, ""


# --- URL parsing ----------------------------------------------------------


def _host_of(value: str) -> str | None:
    """The hostname, or None if there is not one.

    Runs on the hot path against text a scammer wrote, so every malformed shape
    returns None rather than raising — an exception here is a 500 on a scan,
    which fails unsafe.
    """
    value = (value or "").strip()
    if not value:
        return None
    try:
        parts = urlsplit(value)
        if parts.scheme and parts.scheme not in ("http", "https"):
            return None  # javascript:, data:, mailto: are not links to analyse
        host = parts.hostname
        if not host and not parts.scheme and "/" not in value and " " not in value:
            host = urlsplit(f"http://{value}").hostname  # bare host, e.g. link text
        if not host or "." not in host:
            return None
        return host.lower().rstrip(".")
    except ValueError:
        return None


def _labels_of(host: str) -> list[str]:
    return [_decode_label(label) for label in host.split(".") if label]


def _registrable_label(labels: list[str]) -> str:
    """The label immediately before the public suffix.

    An approximation — the exact answer needs the Public Suffix List, which is a
    data file with a refresh job. It is right for `paytm.com` and for
    `paytm.help.in`, and where it is wrong it is wrong towards treating a
    subdomain as registrable, which produces a *warning* rather than a missed
    detection. Worth replacing with the real list when the feed refresh job
    lands, since that job already has somewhere to put data files.
    """
    meaningful = [label for label in labels if label]
    if len(meaningful) < 2:
        return meaningful[0] if meaningful else ""
    if len(meaningful) >= 3 and len(meaningful[-1]) == 2 and len(meaningful[-2]) <= 3:
        return meaningful[-3]  # co.in, co.uk and friends
    return meaningful[-2]


# --- the checks -----------------------------------------------------------


def _homograph_signals(labels: list[str]) -> list[Signal]:
    signals = []
    for label in labels:
        flagged, why = _is_homograph(label)
        if flagged:
            signals.append(
                Signal(
                    name="homograph_domain",
                    basis=BASIS_HOST_LABEL,
                    deterministic=True,
                    detail=f"The domain part '{label}' {why}.",
                    evidence={"label": label, "skeleton": _ascii_skeleton(label)},
                )
            )
            break  # one host, one homograph finding
    return signals


def _lookalike_signals(labels: list[str]) -> list[Signal]:
    for label in labels:
        if label in IGNORED_LABELS:
            continue
        match = nearest_brand(label)
        if match:
            brand, distance = match
            return [
                Signal(
                    name="brand_lookalike",
                    basis=BASIS_HOST_LABEL,
                    deterministic=True,
                    detail=f"The domain '{label}' is {distance} character(s) from '{brand}'.",
                    evidence={"label": label, "brand": brand, "edit_distance": distance},
                )
            ]
    return []


def _impersonation_signals(labels: list[str]) -> list[Signal]:
    """A real brand name inside a domain that is not that brand's.

    `paytm-refund.info` and `paytm.help.in` — the shape `upi_check.py`'s own
    docstring names. Distance-based matching cannot see it: `paytm-refund` is
    seven edits from `paytm`, so it reads as unrelated rather than as an
    imitation. Matching on hyphen-separated parts rather than substrings keeps
    `hdfcbank` from being read as an impersonation of `hdfc`.
    """
    registrable = _registrable_label(labels)
    if not registrable or registrable in KNOWN_BRANDS:
        return []

    for label in labels:
        if label in IGNORED_LABELS:
            continue
        for part in label.split("-"):
            if part in KNOWN_BRANDS and part not in KNOWN_LEGITIMATE:
                return [
                    Signal(
                        name="brand_impersonation",
                        basis=BASIS_HOST_LABEL,
                        deterministic=True,
                        detail=(
                            f"Uses the name '{part}' but the domain is "
                            f"'{registrable}', which is not owned by them."
                        ),
                        evidence={"brand": part, "registrable_label": registrable},
                    )
                ]
    return []


def _tld_signals(host: str) -> list[Signal]:
    for tld in SUSPICIOUS_TLDS:
        if host.endswith(tld):
            return [
                Signal(
                    name="suspicious_tld",
                    basis=BASIS_TLD,
                    deterministic=True,
                    detail=f"Ends in {tld}, rarely used by real banks or wallets.",
                    evidence={"tld": tld},
                )
            ]
    return []


def _entropy_signals(labels: list[str]) -> list[Signal]:
    for label in labels:
        if label in IGNORED_LABELS:
            continue
        if looks_machine_generated(label):
            return [
                Signal(
                    name="high_entropy_host",
                    basis=BASIS_HOST_LABEL,
                    deterministic=True,
                    detail=f"The domain '{label}' looks machine-generated rather than chosen.",
                    evidence={"label": label},
                )
            ]
    return []


def _display_signals(host: str, display_text: str | None) -> list[Signal]:
    """Display text that names one destination while the link goes to another.

    The most common phishing tell in HTML, and genuinely independent evidence:
    it is an observation about the *pair*, not about either string, so neither
    can be explained away by the other.
    """
    if not display_text:
        return []
    shown = _host_of(display_text)
    if not shown or shown == host:
        return []
    if shown.lstrip("www.") == host.lstrip("www.") or shown.endswith(f".{host}") or host.endswith(f".{shown}"):
        return []
    return [
        Signal(
            name="display_target_mismatch",
            basis=BASIS_DISPLAY_PAIR,
            deterministic=True,
            detail=f"The link says '{shown}' but goes to '{host}'.",
            evidence={"displayed_host": shown, "actual_host": host},
        )
    ]


def evaluate(url: str, *, display_text: str | None = None) -> list[Signal]:
    """Every stage 1 signal for one URL. Never fetches, never raises."""
    host = _host_of(url)
    if not host:
        return []

    labels = _labels_of(host)
    return [
        *_homograph_signals(labels),
        *_lookalike_signals(labels),
        *_impersonation_signals(labels),
        *_entropy_signals(labels),
        *_tld_signals(host),
        *_display_signals(host, display_text),
    ]
