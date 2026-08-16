"""Email phishing via share-to-app. `PHASE-2-PLAN.md` §01b, #115 §2.

Most of this is already A2 — the dangerous part of a phishing email is the link,
and stage 1 handles links. What email adds is a **sender**, and the sender is
what this module is for.

## What actually arrives, and what that costs

Share-to-app delivers `text/plain` through `EXTRA_TEXT` and nothing else:
`AndroidManifest.xml` declares only that mime type, and `MainActivity.handleShare`
reads only that extra. What we get is a body, sometimes under a mail client's
quoted "Forwarded message" block.

**SPF and DKIM cannot be computed from that**, and not merely in awkward cases:

- SPF is a statement about the IP that connected to the receiving server. A
  shared body has no IP.
- DKIM is a signature over the exact raw bytes plus its own header. Forwarding
  and sharing rewrite both.
- Even reading the *result* requires `Authentication-Results`, which the
  receiving server adds and which a shared body does not carry.

§01b calls sender authentication "the model-independent second witness the
blocking policy wants". It is exactly that, and it is **unreachable through the
route §115 §2 mandates**. This module therefore does the only honest thing: it
reads the receiving server's conclusion when the headers are there, and says
plainly that it cannot when they are not.

The signal that *does* survive share-to-app is `display_name_brand_mismatch` —
`"HDFC Bank" <winner12@gmail.com>` needs no headers at all.

## Why "cannot verify" is a caveat and not a signal

`independent_witnesses` counts signals toward blocking. Making inability to
verify a `Signal` would hand **every forwarded email a free witness toward being
blocked** — an absence of evidence promoted into evidence, on the most common
input this feature has. So it is a caveat: shown to the user, never counted.

A DMARC **pass** likewise adds no signal. A pass is the absence of evidence
against a sender, not evidence for one, and it must not suppress the link checks
— "trusted sender, skip the rest" is how a compromised real account delivers a
scam with our blessing.

## Attachments

Out of scope, per #115. Detonating attachments is malware analysis: a different
product with a different risk profile. Nothing here parses one.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from email.parser import Parser
from email.utils import parseaddr

from app.services import link_signals
from app.services.brand_match import BRAND_DOMAINS, KNOWN_BRANDS
from app.services.link_signals import Signal

#: What the receiving server concluded about the sender. Its own basis because
#: it is a fact about the delivery, independent of anything in the body.
BASIS_SENDER_AUTH = "sender_auth"

#: The claimed identity against the address that actually sent it — an
#: observation about the *pair*, so neither half explains the other away. Same
#: reasoning as `display_target_mismatch` in stage 1.
BASIS_SENDER_IDENTITY = "sender_identity"

#: Headers worth keeping from a forwarded block. Anything else a mail client
#: quotes is decoration.
_FORWARD_HEADERS = ("from", "date", "subject", "to", "reply-to")

_FORWARD_MARKER = re.compile(
    r"^\s*-{2,}\s*(?:forwarded message|original message)\s*-{2,}\s*$",
    re.IGNORECASE | re.MULTILINE,
)

_HEADER_LINE = re.compile(r"^([A-Za-z][A-Za-z0-9\-]*):\s*(.*)$")


@dataclass(frozen=True)
class ParsedEmail:
    headers: dict[str, str]
    body: str
    #: `raw` — a real message with real headers.
    #: `forwarded_block` — a mail client's quoted summary. Claims, not proof.
    #: `none` — a bare body.
    header_source: str


@dataclass
class EmailAssessment:
    """Countable evidence and uncountable honesty, kept apart on purpose."""

    signals: list[Signal] = field(default_factory=list)
    #: `pass` | `fail` | `unverifiable`
    sender_verification: str = "unverifiable"
    #: User-facing statements that are never counted as evidence.
    caveats: list[str] = field(default_factory=list)


def _split_headers(block: str) -> dict[str, str]:
    """RFC 5322 folded headers, lowercased keys, first occurrence wins."""
    headers: dict[str, str] = {}
    current: str | None = None
    for line in block.splitlines():
        if not line.strip():
            continue
        if line[:1] in (" ", "\t") and current:
            headers[current] += " " + line.strip()
            continue
        match = _HEADER_LINE.match(line)
        if not match:
            continue
        key = match.group(1).lower()
        current = key
        headers.setdefault(key, match.group(2).strip())
    return headers


def parse(text: str) -> ParsedEmail:
    """Headers and body out of whatever the share handed us. Never raises."""
    text = (text or "").replace("\r\n", "\n")
    if not text.strip():
        return ParsedEmail({}, "", "none")

    marker = _FORWARD_MARKER.search(text)
    if marker:
        # A client's quoted summary: headers follow the marker, body follows the
        # first blank line. These are the sender's *claims* — nothing in a
        # quoted block was verified by anyone.
        remainder = text[marker.end() :].lstrip("\n")
        head, _, body = remainder.partition("\n\n")
        headers = {k: v for k, v in _split_headers(head).items() if k in _FORWARD_HEADERS}
        if headers:
            return ParsedEmail(headers, body.strip(), "forwarded_block")

    head, blank, body = text.partition("\n\n")
    if blank and _HEADER_LINE.match(head.splitlines()[0] or ""):
        parsed = Parser().parsestr(text, headersonly=True)
        headers = {k.lower(): str(v).replace("\n", " ") for k, v in parsed.items()}
        if headers:
            source = "raw" if "authentication-results" in headers or len(headers) > 2 else "forwarded_block"
            return ParsedEmail(headers, body.strip(), source)

    return ParsedEmail({}, text.strip(), "none")


def _auth_verdicts(headers: dict[str, str]) -> tuple[dict[str, str], str | None]:
    """SPF/DKIM/DMARC results as the receiving server recorded them.

    **We read a conclusion, we do not reach one.** Claiming otherwise would be a
    stronger statement than the data supports.
    """
    raw = headers.get("authentication-results")
    if not raw:
        return {}, None

    server = raw.split(";", 1)[0].strip() or None
    verdicts = {
        method: result.lower()
        for method, result in re.findall(r"\b(spf|dkim|dmarc)\s*=\s*(\w+)", raw, re.IGNORECASE)
    }
    return verdicts, server


def _sender_signals(headers: dict[str, str], source: str) -> tuple[list[Signal], str, list[str]]:
    if source != "raw":
        return (
            [],
            "unverifiable",
            [
                (
                    "We could not verify who really sent this email. A shared or "
                    "forwarded message does not carry the information needed to "
                    "check the sender, so treat the sender name as a claim."
                )
            ],
        )

    verdicts, server = _auth_verdicts(headers)
    if not verdicts:
        return (
            [],
            "unverifiable",
            ["We could not verify who really sent this email — it carries no sender check."],
        )

    where = server or "the receiving mail server"
    failed = [method for method, result in verdicts.items() if result == "fail"]
    if not failed:
        # A pass is the absence of evidence against, never evidence for, and it
        # must not suppress anything downstream.
        return [], "pass", []

    return (
        [
            Signal(
                name=f"{method}_fail",
                basis=BASIS_SENDER_AUTH,
                deterministic=True,
                detail=(
                    f"{where} recorded that this message failed its {method.upper()} "
                    f"sender check, which usually means it was not sent by the "
                    f"organisation it claims to be from."
                ),
                evidence={"method": method, "result": "fail", "reported_by": where},
            )
            for method in sorted(failed)
        ],
        "fail",
        [],
    )


def _identity_signals(headers: dict[str, str]) -> list[Signal]:
    """A brand in the display name, an address that is not theirs.

    Needs no headers beyond `From`, which is why it survives share-to-app when
    sender authentication does not.
    """
    display, address = parseaddr(headers.get("from", ""))
    if not display or "@" not in address:
        return []

    domain = address.rsplit("@", 1)[-1].lower().strip()
    words = set(re.findall(r"[a-z]+", display.lower()))
    for brand in KNOWN_BRANDS:
        if brand not in words:
            continue
        if domain in BRAND_DOMAINS.get(brand, set()) or domain.endswith(
            tuple(f".{d}" for d in BRAND_DOMAINS.get(brand, set()))
        ):
            return []
        return [
            Signal(
                name="display_name_brand_mismatch",
                basis=BASIS_SENDER_IDENTITY,
                deterministic=True,
                detail=(
                    f"The sender calls itself '{display}' but the address is at "
                    f"'{domain}', which does not belong to them."
                ),
                evidence={"display_name": display, "address_domain": domain, "brand": brand},
            )
        ]
    return []


def evaluate(text: str) -> EmailAssessment:
    """Every email signal for one shared message. Never fetches, never raises."""
    parsed = parse(text)

    sender, verification, caveats = _sender_signals(parsed.headers, parsed.header_source)
    signals = [*sender, *_identity_signals(parsed.headers)]

    # Email is mostly a delivery question — the link detection is A2's, unchanged.
    for url in link_signals.extract_urls(parsed.body):
        signals.extend(link_signals.evaluate(url))

    return EmailAssessment(signals=signals, sender_verification=verification, caveats=caveats)
