"""Resolve pending domain registration dates. Off-path, never called by a handler.

The warm half of `app/services/domain_age.py`. WHOIS takes seconds and the scan
path has 100ms (`PHASE-2-PLAN.md` §00b), so the scan reads the cache and this
fills it.

    python scripts/refresh_domain_ages.py
    python scripts/refresh_domain_ages.py --limit 20

Plain WHOIS over port 43, no dependency: ask IANA which server owns the TLD, then
ask that server. Registries answer in inconsistent formats, so the date parser
takes the first field it recognises and records `unresolved` when it recognises
none.

**`unresolved` is written, not skipped.** Plenty of TLDs refuse WHOIS outright;
without recording the refusal this retries the same domains on every pass
forever. `domain_age.signals_for` treats `unresolved` exactly like an unknown
domain — no signal — so a refusal costs a signal rather than inventing one.
"""

from __future__ import annotations

import argparse
import os
import re
import socket
import sys
from datetime import date, datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services import domain_age

WHOIS_PORT = 43
TIMEOUT = 10.0

#: Registries label the registration date a dozen different ways.
_DATE_FIELDS = re.compile(
    r"^\s*(?:creation date|created|created on|created date|registered on|"
    r"registration time|domain registration date|record created)\s*:\s*(.+)$",
    re.IGNORECASE | re.MULTILINE,
)


def _query(server: str, request: str) -> str:
    with socket.create_connection((server, WHOIS_PORT), timeout=TIMEOUT) as sock:
        sock.sendall(f"{request}\r\n".encode())
        chunks = []
        while True:
            chunk = sock.recv(4096)
            if not chunk:
                break
            chunks.append(chunk)
    return b"".join(chunks).decode("utf-8", errors="replace")


def _server_for(domain: str) -> str | None:
    """IANA knows which registry owns a TLD; asking it avoids shipping a map
    that goes stale every time a new TLD is delegated."""
    tld = domain.rsplit(".", 1)[-1]
    match = re.search(r"^whois:\s*(\S+)", _query("whois.iana.org", tld), re.IGNORECASE | re.MULTILINE)
    return match.group(1) if match else None


def _parse_date(body: str) -> date | None:
    """The registration date, whatever shape the registry wrote it in.

    ISO first because most registries use it, then a small set of legacy
    formats against the first whitespace-delimited token — trailing time zones
    and free text after the date are common and are not worth parsing.
    """
    match = _DATE_FIELDS.search(body)
    if not match:
        return None
    raw = match.group(1).strip()

    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).date()
    except ValueError:
        pass

    token = raw.split()[0] if raw.split() else ""
    for fmt in ("%Y-%m-%d", "%d-%b-%Y", "%Y.%m.%d", "%Y/%m/%d"):
        try:
            # DTZ007 is not a risk here: the result is reduced to a date
            # immediately, so an absent time zone cannot shift anything.
            return datetime.strptime(token, fmt).date()  # noqa: DTZ007
        except ValueError:
            continue
    return None


def resolve(domain: str) -> tuple[str, date | None]:
    try:
        server = _server_for(domain)
        if not server:
            return "unresolved", None
        registered = _parse_date(_query(server, domain))
    except (OSError, UnicodeError):
        return "unresolved", None
    return ("resolved", registered) if registered else ("unresolved", None)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=100, help="how many pending domains to resolve")
    args = parser.parse_args()

    pending = domain_age.pending_domains(args.limit)
    if not pending:
        print("Nothing pending.")
        return 0

    print(f"Resolving {len(pending)} domain(s)")
    resolved = 0
    for domain in pending:
        status, registered = resolve(domain)
        domain_age.record(domain, registered, status=status)
        if status == "resolved":
            resolved += 1
        print(f"  {domain}: {status}{f' — registered {registered}' if registered else ''}")

    # Both numbers, always. "Refreshed 100 domains" reads as success when 97 of
    # them were refusals, and the refusals are the ones that silently cost a
    # signal on the scan path.
    print(f"\n{resolved} resolved, {len(pending) - resolved} unresolved")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
