# Known-bad URL feeds

Local hash lists read by `app/services/threat_feeds.py` on the scan path.

**These files are empty.** They are populated by `scripts/refresh_threat_feeds.py`,
which runs off-path. An empty list is an honest empty result, not a clean bill of
health — `lookup()` returning `[]` means "no feed listed it", which today means
"no feed data is loaded".

## Format

One lowercase hex SHA-256 per line. `#` starts a comment. Blank lines ignored.

The digest is over the **canonicalised** URL — see `threat_feeds.canonicalise`.
Host is lowercased and the default port dropped; the fragment is stripped; **the
path stays case-sensitive**, because servers treat it that way and folding it
would collide distinct URLs into one listing.

Generate one with:

```bash
python -c "from app.services.threat_feeds import digest_for; print(digest_for('http://example.com/login'))"
```

## Why hashes rather than URLs

We ship and diff these files. Storing digests means the repository never carries
a directory of live phishing URLs, and a leaked copy is not a working target
list. It also makes the hot-path lookup a set membership test rather than a
string scan.

## Why four feeds and not one

`docs/PHASE-2-PLAN.md` §01. Independent research puts single-feed detection well
under 60%. Stacking cuts false negatives meaningfully — but a listing is still
**a signal, never the answer**.

All four share one `basis` in the signal model, so four simultaneous listings
count as **one** independent witness. Feeds ingest each other, so agreement
between them is correlated rather than independent; §01's Confirmed tier spends
exactly one slot on "known-bad feed" however many agree.

| Feed | Refresh | Needs |
|---|---|---|
| `safebrowsing` | Update API, local database | Google API key |
| `urlhaus` | Public CSV, ~5 min | — |
| `openphish` | Community feed, 12 h | — |
| `phishtank` | Community-verified | Registered app key |

## Refreshing

```bash
python scripts/refresh_threat_feeds.py
```

Writes the files, then calls `threat_feeds.reset_cache()`. The scan path picks up
the new lists on the next lookup. **Never call the refresh from a request
handler** — §00b bans a blocking network call on the scan path, and that ban is
the reason this is a file on disk rather than an API client.
