"""Known-bad URL feeds, stacked and read from local hash lists.

`PHASE-2-PLAN.md` §01 stacks four feeds rather than picking one, because
independent research puts single-feed detection well under 60% and reports that
combining sources cuts false negatives meaningfully. Any one feed is a signal,
never the answer.

## Two constraints shape everything here

**No network call on the scan path.** §00b is explicit: local hash lists only.
Feeds refresh out of band into files on disk; the hot path reads a frozenset.
That keeps the check inside the 100ms budget and, more importantly, keeps
detection working when a feed provider is down — a scan must never fail because
someone else's API did.

**Hash lists, not URL lists.** We ship and diff these files. Storing them as
SHA-256 digests means the repository never carries a directory of live phishing
URLs, and a leaked file is not a working target list.

## Status

The shipped lists are **empty**. The loader, the canonicalisation, the signal
shape and the tests are what stage 1 delivers; populating them needs the
refresh job, which runs off-path and needs a Google Safe Browsing API key.
`lookup` returning `[]` today is an honest empty result, not a clean bill of
health, and nothing downstream should read it as one.
"""

import hashlib
import logging
import pathlib
from urllib.parse import urlsplit, urlunsplit

from app.services.link_signals import BASIS_FEED, Signal

logger = logging.getLogger(__name__)

#: One file per feed, one lowercase hex SHA-256 per line, `#` for comments.
FEED_DIR = pathlib.Path(__file__).resolve().parents[2] / "data" / "feeds"

#: Stacked, not chosen. Order here is display order only — see `signals_for`
#: for why the count of these never becomes a count of witnesses.
FEEDS = ("safebrowsing", "urlhaus", "openphish", "phishtank")

_cache: dict[str, frozenset[str]] | None = None


def reset_cache() -> None:
    """Drop the loaded lists. Called by the refresh job after it writes, and by
    tests."""
    global _cache
    _cache = None


def canonicalise(url: str) -> str:
    """One spelling per URL, so a listing matches the message that carries it.

    Host case, the default port, a fragment and surrounding whitespace do not
    make a different URL. **The path is left case-sensitive**, because servers
    treat it that way — folding it would collide distinct URLs and turn one
    feed listing into a false positive on an unrelated page.
    """
    parts = urlsplit((url or "").strip())
    host = (parts.hostname or "").lower().rstrip(".")
    if not host:
        return ""

    port = parts.port
    default_port = {"http": 80, "https": 443}.get(parts.scheme)
    netloc = host if port in (None, default_port) else f"{host}:{port}"

    return urlunsplit((parts.scheme or "http", netloc, parts.path or "/", parts.query, ""))


def digest_for(url: str) -> str:
    return hashlib.sha256(canonicalise(url).encode("utf-8")).hexdigest()


def _load_all() -> dict[str, frozenset[str]]:
    """Read every feed file. A missing directory is normal on a fresh clone."""
    loaded: dict[str, frozenset[str]] = {}
    for feed in FEEDS:
        path = FEED_DIR / f"{feed}.txt"
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        digests = {
            line.strip().lower()
            for line in lines
            if line.strip() and not line.startswith("#")
        }
        if digests:
            loaded[feed] = frozenset(digests)
    return loaded


def _feeds() -> dict[str, frozenset[str]]:
    global _cache
    if _cache is None:
        try:
            _cache = _load_all()
        except Exception:
            # A malformed feed file degrades this one check. It must never take
            # down a scan — the offline rules and the static checks still run.
            logger.exception("Threat feed load failed; continuing without feeds")
            _cache = {}
    return _cache


def lookup(url: str) -> list[str]:
    """Feeds listing this URL, by name. Never raises, never touches the network."""
    if not url:
        return []
    try:
        digest = digest_for(url)
    except Exception:
        return []
    return sorted(feed for feed, digests in _feeds().items() if digest in digests)


def signals_for(url: str) -> list[Signal]:
    """One signal per listing feed — and all of them share `BASIS_FEED`.

    **Four feeds are one witness.** Feeds ingest each other, so simultaneous
    listings are correlated rather than independent, and §01's Confirmed tier
    spends exactly one slot on "known-bad feed" however many agree. Giving each
    feed its own basis would let a single widely-syndicated listing auto-block
    for every user with no other evidence at all.

    Named individually anyway, because "on a blocklist" is not appealable and
    "on URLhaus, listed under this digest" is.
    """
    return [
        Signal(
            name="known_bad_feed",
            basis=BASIS_FEED,
            deterministic=True,
            detail=f"Listed as malicious by {feed}.",
            evidence={"feed": feed, "digest": digest_for(url)},
        )
        for feed in lookup(url)
    ]
