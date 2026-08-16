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

from app.services import threat_feeds  # noqa: E402

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


def refresh(feed: str) -> int:
    """Rewrite one feed's file. Returns the digest count, or -1 if skipped."""
    try:
        urls = FETCHERS[feed]()
    except Exception as exc:
        print(f"  {feed}: skipped — {exc}")
        return -1

    digests = sorted({threat_feeds.digest_for(url) for url in urls if url})
    digests = [d for d in digests if d != threat_feeds.digest_for("")]

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
    args = parser.parse_args()

    feeds = [args.feed] if args.feed else list(threat_feeds.FEEDS)
    print(f"Refreshing {len(feeds)} feed(s) into {threat_feeds.FEED_DIR}")

    counts = {feed: refresh(feed) for feed in feeds}
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
