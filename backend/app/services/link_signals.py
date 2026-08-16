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
import ipaddress
import re
import unicodedata
from dataclasses import dataclass, field
from urllib.parse import parse_qsl, unquote, urlsplit

from app.services.brand_match import (
    BRAND_DOMAINS,
    IGNORED_LABELS,
    KNOWN_BRANDS,
    KNOWN_LEGITIMATE,
    SUSPICIOUS_TLDS,
    URL_SHORTENERS,
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
        if parts.scheme and parts.scheme.lower() not in ("http", "https"):
            return None  # javascript:, data:, mailto: are not links to analyse
        host = parts.hostname
        if not host and not parts.scheme and " " not in value:
            # A bare host, with or without a path. SMS does not contain
            # `http://` — `paytm-refund.info/verify` is the shape people
            # actually send, and requiring a scheme meant the most common
            # real-world case was never checked at all (A6).
            host = urlsplit(f"http://{value}").hostname
        if not host:
            return None
        host = host.lower().rstrip(".")
        return host if ("." in host or _as_ip(host)) else None
    except ValueError:
        return None


def _as_ip(host: str) -> str | None:
    """The host as an IP address, or None.

    Handles the dotted form and the integer form — `3405803820` is `203.0.113.44`
    written as one number, which browsers still resolve and naive parsers read as
    a hostname.
    """
    try:
        return str(ipaddress.ip_address(host))
    except ValueError:
        pass
    if host.isdigit():
        try:
            return str(ipaddress.ip_address(int(host)))
        except (ValueError, ipaddress.AddressValueError):
            return None
    return None


def _labels_of(host: str) -> list[str]:
    return [_decode_label(label) for label in host.split(".") if label]


def _suffix_length(labels: list[str]) -> int:
    """How many trailing labels form the public suffix. 1 or 2, approximated.

    The exact answer needs the Public Suffix List, a data file with a refresh
    job. `data/feeds/` now exists and the refresh job has somewhere to put one,
    which makes replacing this cheap when someone wants to.
    """
    if len(labels) >= 3 and len(labels[-1]) <= 3 and len(labels[-2]) <= 3:
        return 2  # co.in, co.uk, com.co, org.in and friends
    return 1


def _registrable_label(labels: list[str]) -> str:
    """The label immediately before the public suffix.

    **Not sufficient to decide whether a domain belongs to a brand**, and A6
    found the case that proves it: `hdfcbank.com.co` and `hdfcbank.com` both
    reduce to `hdfcbank` here. An earlier version of this docstring claimed that
    where the approximation is wrong it errs towards treating a subdomain as
    registrable, producing a warning rather than a missed detection. That was
    wrong in both directions — `com.co` is a real public suffix, so the error ran
    the other way and produced a *missed detection* on a domain anybody can buy.

    Ownership is decided by `_registrable_domain` against `BRAND_DOMAINS`. This
    stays only for the checks that genuinely are about one label.
    """
    meaningful = [label for label in labels if label]
    if len(meaningful) < 2:
        return meaningful[0] if meaningful else ""
    return meaningful[-(_suffix_length(meaningful) + 1)]


def _registrable_domain(labels: list[str]) -> str:
    """The whole registration — label plus public suffix, e.g. `hdfcbank.com.co`.

    This is the unit a brand can be said to own. Comparing it against
    `BRAND_DOMAINS` is what separates HDFC's domain from one that merely ends up
    with the same label.
    """
    meaningful = [label for label in labels if label]
    if len(meaningful) < 2:
        return meaningful[0] if meaningful else ""
    return ".".join(meaningful[-(_suffix_length(meaningful) + 1) :])


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
    domain = _registrable_domain(labels)
    if not domain:
        return []

    for label in labels:
        if label in IGNORED_LABELS:
            continue
        for part in label.split("-"):
            if part not in KNOWN_BRANDS or part in KNOWN_LEGITIMATE:
                continue
            # Ownership is membership of the brand's real domains, never a
            # label comparison — `hdfcbank.com.co` has the same label as
            # `hdfcbank.com` and is not HDFC (A6).
            if domain in BRAND_DOMAINS.get(part, set()):
                return []
            return [
                Signal(
                    name="brand_impersonation",
                    basis=BASIS_HOST_LABEL,
                    deterministic=True,
                    detail=(
                        f"Uses the name '{part}' but the domain is "
                        f"'{domain}', which is not owned by them."
                    ),
                    evidence={"brand": part, "registrable_domain": domain},
                )
            ]
    return []


def _ip_signals(host: str) -> list[Signal]:
    """A bare IP where a name should be.

    No bank serves from one, and it defeats every host-name check at once —
    there is no name left to compare against anything (A6).
    """
    address = _as_ip(host)
    if not address:
        return []
    return [
        Signal(
            name="ip_address_host",
            basis=BASIS_HOST_LABEL,
            deterministic=True,
            detail=f"Goes to a raw IP address ({address}) instead of a website name.",
            evidence={"host": host, "ip": address},
        )
    ]


def _shortener_signals(host: str) -> list[Signal]:
    """A shortener is not evidence of fraud. It is evidence of *not knowing*.

    Stage 1 cannot resolve one without fetching, which is stage 2 by
    definition. So the honest signal is "the destination is hidden" — a fact,
    deterministic, and precisely the thing that makes a link worth escalating to
    a stage allowed to fetch it (A6).
    """
    if host not in URL_SHORTENERS:
        return []
    return [
        Signal(
            name="hidden_destination",
            basis=BASIS_HOST_LABEL,
            deterministic=True,
            detail=f"'{host}' is a link shortener, so where this really goes cannot be seen.",
            evidence={"shortener": host},
        )
    ]


#: Embedded URLs are followed one level. A nested chain is otherwise a cheap way
#: to make one scan do arbitrary work, on the hot path, from attacker-controlled
#: text.
_MAX_EMBED_DEPTH = 1

_EMBEDDED_URL = re.compile(r"https?://[^\s&]+", re.IGNORECASE)


def _embedded_urls(url: str) -> list[str]:
    """URLs carried inside another URL's query — the open-redirect shape.

    `google.com/url?q=http://paytm-refund.info` has a completely genuine host,
    and reading only the outer one lets a legitimate domain launder the whole
    check (A6).
    """
    try:
        query = urlsplit(url).query
    except ValueError:
        return []
    if not query:
        return []

    found = []
    for _, value in parse_qsl(query, keep_blank_values=False):
        candidate = unquote(value).strip()
        if _EMBEDDED_URL.match(candidate):
            found.append(candidate)
    return found


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


#: Links as they appear in an SMS. Two shapes, because people send both and the
#: bare one is far more common — an SMS almost never contains `http://`.
#:
#: The bare-host branch requires a plausible alphabetic TLD, which is what keeps
#: it from matching `Rs.500`, `12.30pm`, a version number or a sentence that
#: happens to lack a space after a full stop. Being slightly conservative here is
#: the right direction: a missed link costs one unchecked signal, while matching
#: prose would run brand comparisons against arbitrary words on the hot path.
_URL_IN_TEXT = re.compile(
    r"""(?xi)
    (?:
        https?://[^\s<>"']+                       # explicit scheme
      | (?<![@\w.])                               # not an email or a longer host
        (?:[a-z0-9](?:[a-z0-9\-]*[a-z0-9])?\.)+   # one or more labels
        [a-z]{2,24}\b                             # a plausible TLD
        (?:/[^\s<>"']*)?                          # optional path
    )
    """
)


def extract_urls(text: str, *, limit: int = 10) -> list[str]:
    """Links found in a message, in order, de-duplicated.

    `limit` bounds the work one message can cause on the hot path — a message
    stuffed with hundreds of links is itself adversarial input, and the first
    few carry the fraud.
    """
    if not text:
        return []

    seen: set[str] = set()
    found: list[str] = []
    for match in _URL_IN_TEXT.finditer(text):
        candidate = match.group(0).rstrip(".,;:!?)’\"'")
        if not _host_of(candidate):
            continue
        key = candidate.lower()
        if key in seen:
            continue
        seen.add(key)
        found.append(candidate)
        if len(found) >= limit:
            break
    return found


def evaluate(
    url: str, *, display_text: str | None = None, _depth: int = 0
) -> list[Signal]:
    """Every stage 1 signal for one URL. Never fetches, never raises."""
    host = _host_of(url)
    if not host:
        return []

    if _as_ip(host):
        # No labels to read — every name-based check has nothing to work with,
        # which is the whole point of using one.
        return [*_ip_signals(host), *_display_signals(host, display_text)]

    labels = _labels_of(host)
    signals = [
        *_shortener_signals(host),
        *_homograph_signals(labels),
        *_lookalike_signals(labels),
        *_impersonation_signals(labels),
        *_entropy_signals(labels),
        *_tld_signals(host),
        *_display_signals(host, display_text),
    ]

    if _depth < _MAX_EMBED_DEPTH:
        for embedded in _embedded_urls(url):
            signals.extend(evaluate(embedded, _depth=_depth + 1))

    return signals
