"""Rebuild the local known-bad hash lists. Off-path, never called by a handler.

`PHASE-2-PLAN.md` §00b bans a blocking network call on the scan path, which is
why the feeds are files on disk and why this is a script rather than a client
the scan imports. Run it on a schedule; the scan path picks up the new lists on
the next lookup.

    python scripts/refresh_threat_feeds.py
    python scripts/refresh_threat_feeds.py --feed urlhaus

OpenPhish needs no credentials. URLhaus needs a free abuse.ch Auth-Key
(URLHAUS_AUTH_KEY) since abuse.ch retired keyless downloads. Google Safe Browsing
and PhishTank both require keys, and rather than pretend otherwise this skips
them with a message naming the environment variable each wants. A feed that is
skipped leaves its existing file untouched — a refresh must never silently
empty a list that was working.

**Every URL is stored as a digest, never as a URL.** See `data/feeds/README.md`.
"""

from __future__ import annotations

import argparse
import csv
import io
import os
import sys
import zipfile
from urllib.parse import quote

import httpx

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services import threat_feeds

TIMEOUT = httpx.Timeout(60.0)


def _fetch(url: str) -> str:
    response = httpx.get(url, timeout=TIMEOUT, follow_redirects=True)
    response.raise_for_status()
    return response.text


URLHAUS_KEY_VARIABLE = "URLHAUS_AUTH_KEY"
URLHAUS_EXPORT = "https://urlhaus-api.abuse.ch/v2/files/exports/{key}/recent.csv"


def _redact(text: str, secret: str) -> str:
    """Remove `secret`, raw or URL-encoded, from `text`."""
    for form in {secret, quote(secret, safe="")} - {""}:
        text = text.replace(form, "***")
    return text


def _download_urlhaus(key: str) -> str:
    """The keyed v2 export. Returns CSV text, unzipping if abuse.ch zipped it.

    abuse.ch retired every keyless download on 2026-10-21 — `csv_online/` and
    its siblings answer **410 Gone** — and the replacement takes the free
    Auth-Key (auth.abuse.ch) **in the URL path**, not a header. So any error
    that quotes the URL quotes the key. httpx's own messages do exactly that,
    which is why this re-raises with the key redacted rather than letting the
    exception reach `refresh()`'s print and the Actions log.
    """
    url = URLHAUS_EXPORT.format(key=quote(key, safe=""))
    try:
        response = httpx.get(url, timeout=TIMEOUT, follow_redirects=True)
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        hint = f" — check {URLHAUS_KEY_VARIABLE}" if status in (401, 403) else ""
        raise RuntimeError(f"HTTP {status} from the URLhaus export{hint}") from None
    except httpx.HTTPError as exc:
        raise RuntimeError(_redact(f"{type(exc).__name__}: {exc}", key)) from None

    body = response.content
    if body[:2] == b"PK":
        with zipfile.ZipFile(io.BytesIO(body)) as archive:
            names = [n for n in archive.namelist() if n.endswith(".csv")]
            if not names:
                raise RuntimeError("URLhaus export zip holds no .csv")
            body = archive.read(names[0])
    return body.decode("utf-8", errors="replace")


def parse_urlhaus_csv(body: str) -> list[str]:
    """URLs still marked online, from a URLhaus CSV.

    The commented header (`# id,dateadded,url,url_status,...`) names the
    columns and is used when present, so a reordered export still parses. The
    fallback is the layout URLhaus has always shipped: url third, status fourth.

    `recent.csv` is the last 30 days with offline entries included — about
    63,000 rows, against the ~16,000 the retired `csv_online` held. Keeping
    only `online` rows keeps the old meaning, and keeps the committed list (and
    its daily git churn, costed in the workflow) the size it was.
    """
    url_col, status_col = 2, 3
    urls = []
    for row in csv.reader(io.StringIO(body)):
        if not row:
            continue
        if row[0].startswith("#"):
            header = [cell.strip().lstrip("#").strip() for cell in row]
            if "url" in header:
                url_col = header.index("url")
                status_col = header.index("url_status") if "url_status" in header else None
            continue
        if len(row) <= url_col:
            continue
        if status_col is not None and len(row) > status_col and row[status_col].strip() != "online":
            continue
        urls.append(row[url_col])
    return urls


def fetch_urlhaus() -> list[str]:
    """URLhaus — fast on fresh campaigns. Needs a free abuse.ch Auth-Key."""
    key = os.environ.get(URLHAUS_KEY_VARIABLE, "").strip()
    if not key:
        raise RuntimeError(f"needs {URLHAUS_KEY_VARIABLE} (free at auth.abuse.ch)")
    return parse_urlhaus_csv(_download_urlhaus(key))


def fetch_openphish() -> list[str]:
    """OpenPhish community feed — plain text, one URL per line, 12h refresh."""
    return [line.strip() for line in _fetch("https://openphish.com/feed.txt").splitlines() if line.strip()]


def fetch_safebrowsing() -> list[str]:
    raise RuntimeError("needs GOOGLE_SAFE_BROWSING_API_KEY and the Update API client")


def fetch_phishtank() -> list[str]:
    raise RuntimeError("needs PHISHTANK_APP_KEY (registered application)")


FETCHERS = {
    "urlhaus": fetch_urlhaus,
    "openphish": fetch_openphish,
    "safebrowsing": fetch_safebrowsing,
    "phishtank": fetch_phishtank,
}


def existing_count(feed: str) -> int:
    """How many digests the feed file already holds. Missing file counts zero."""
    path = threat_feeds.FEED_DIR / f"{feed}.txt"
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return 0
    return sum(1 for line in lines if line.strip() and not line.startswith("#"))


def refresh(feed: str, *, allow_empty: bool = False) -> int:
    """Rewrite one feed's file. Returns the digest count, or -1 if skipped.

    **A successful fetch that yields nothing does not overwrite a working
    list.** The docstring at the top of this file has always promised that a
    refresh never silently empties a list, and the exception path honoured it —
    but a feed answering 200 with an empty body, or with a changed format this
    parser no longer understands, produced zero digests and wrote them out.

    That is the worst available failure. `lookup()` returning `[]` reads as "no
    feed listed this URL", so an emptied list is not a broken feature, it is a
    clean bill of health issued to every URL on the scan path, and nothing
    upstream would have noticed: the old code returned a success count of 0.

    `--allow-empty` exists for the case where a feed genuinely has no live
    entries and someone has checked. It has to be asked for.
    """
    try:
        urls = FETCHERS[feed]()
    except Exception as exc:
        print(f"  {feed}: skipped — {exc}")
        return -1

    digests = sorted({threat_feeds.digest_for(url) for url in urls if url})
    digests = [d for d in digests if d != threat_feeds.digest_for("")]

    if not digests and not allow_empty:
        held = existing_count(feed)
        if held:
            print(
                f"  {feed}: REFUSED — fetch returned nothing and {held} digest(s) "
                f"are already on disk. Left untouched. The feed is more likely "
                f"down or reformatted than genuinely empty; re-run with "
                f"--allow-empty if it really is."
            )
            return -1

    path = threat_feeds.FEED_DIR / f"{feed}.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"# {feed} — SHA-256 digests of canonicalised known-bad URLs, one per line.\n"
        f"# Rebuilt by scripts/refresh_threat_feeds.py. {len(digests)} entries.\n"
        + "\n".join(digests)
        + "\n",
        encoding="utf-8",
    )
    print(f"  {feed}: {len(digests)} digests")
    return len(digests)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--feed", choices=sorted(FETCHERS), help="refresh one feed only")
    parser.add_argument(
        "--allow-empty",
        action="store_true",
        help="permit a fetch that returned nothing to replace a non-empty list",
    )
    args = parser.parse_args()

    feeds = [args.feed] if args.feed else list(threat_feeds.FEEDS)
    print(f"Refreshing {len(feeds)} feed(s) into {threat_feeds.FEED_DIR}")

    counts = {feed: refresh(feed, allow_empty=args.allow_empty) for feed in feeds}
    threat_feeds.reset_cache()

    refreshed = [f for f, c in counts.items() if c >= 0]
    skipped = [f for f, c in counts.items() if c < 0]
    print(f"\n{len(refreshed)} refreshed, {len(skipped)} skipped: {', '.join(skipped) or 'none'}")

    # Reported per feed rather than as a total. A combined number would let a
    # feed that returned nothing hide behind one that returned plenty, and
    # "single-feed detection is under 60%" is the entire reason there are four.
    return 0 if refreshed else 1


if __name__ == "__main__":
    raise SystemExit(main())
