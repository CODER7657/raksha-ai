"""Rebuild the local known-bad hash lists. Off-path, never called by a handler.

`PHASE-2-PLAN.md` §00b bans a blocking network call on the scan path, which is
why the feeds are files on disk and why this is a script rather than a client
the scan imports. Run it on a schedule; the scan path picks up the new lists on
the next lookup.

    python scripts/refresh_threat_feeds.py
    python scripts/refresh_threat_feeds.py --feed urlhaus

Two of the four need no credentials and are fetched here. Google Safe Browsing
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

import httpx

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services import threat_feeds

TIMEOUT = httpx.Timeout(60.0)


def _fetch(url: str) -> str:
    response = httpx.get(url, timeout=TIMEOUT, follow_redirects=True)
    response.raise_for_status()
    return response.text


def fetch_urlhaus() -> list[str]:
    """URLhaus online CSV — fast on fresh campaigns, no key."""
    body = _fetch("https://urlhaus.abuse.ch/downloads/csv_online/")
    urls = []
    for row in csv.reader(io.StringIO(body)):
        if not row or row[0].startswith("#") or len(row) < 3:
            continue
        urls.append(row[2])
    return urls


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
