"""A3 — campaigns out of aggregate reports. #115 §5, `AGENT-LAYER.md` §04.

> Individual reports are noise; campaigns are signal. [...] Read-only over
> aggregate data — it never touches raw message content.

#115 §5 is unusually direct that this will say little for a while:

> **The honest blocker is data, not code.** A correlator that finds no campaigns
> across 14 patterns is working correctly.

So the design goal is not to find campaigns. It is to be **right about there not
being any**, and to become useful as volume arrives without anyone re-tuning it.

## What §04 asks for, against what we store

`community_reports` holds `pattern_hash`, `language`, `report_count`,
`last_reported_at`. §04 asks for clustering "by pattern similarity, timing and
region". Two of the three are unavailable, and one of them permanently:

**Similarity cannot be done over a one-way digest.** Two wordings of one
campaign — "your KYC expires today" and "...expires tomorrow" — produce
unrelated SHA-256s. Hash equality finds identical messages only. Clustering by
similarity would need something derived from the message, and not storing that
is the privacy posture the product is sold on, so this is a permanent limit
rather than a later feature.

**Region is not collected.** Not a missing column — locating every report is a
real change to "no message leaves the phone", and it should be argued on its
own rather than arrive inside a correlator.

**Timing was half there.** `last_reported_at` with no first sighting cannot
give velocity, and velocity is the whole difference between a campaign and a
message that merely circulates. Migration 0014 adds `first_reported_at`.

## What is left is the shape that actually matters here

One exact message, reported many times, fast. That is most Indian scam SMS:
the same script blasted verbatim to thousands of numbers. The narrower claim is
also the more defensible one — an under-count we can explain beats an
over-count we cannot.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

#: Below this, one message reported twice is two people receiving spam. The
#: number is deliberately unexciting: with 14 patterns in the corpus, a
#: correlator that fires at 3 would report noise as intelligence and teach a
#: cyber cell to ignore it.
MIN_REPORTS = 10

#: Reports per hour. A campaign is defined by rate, not by total — 90 reports
#: over three months is a message that circulates, and 30 in two hours is
#: someone running a blast right now.
MIN_REPORTS_PER_HOUR = 2.0

#: Shorter windows are not evidence of speed, they are evidence of a short
#: window. Two reports a minute apart would otherwise compute as 120/hour.
MIN_WINDOW_HOURS = 0.5


@dataclass(frozen=True)
class Campaign:
    """One message spreading, described without quoting it."""

    pattern_hash: str
    language: str
    reports: int
    window_hours: float
    reports_per_hour: float

    #: Deliberately no `text`. The digest is the identity; the message itself is
    #: not stored by this path and must not be reachable from a campaign object,
    #: or a dashboard would eventually render it.


def _parsed(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        stamped = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return stamped if stamped.tzinfo else stamped.replace(tzinfo=timezone.utc)


def campaigns(reports: list[dict], *, now: datetime | None = None) -> list[Campaign]:
    """Campaigns visible in the aggregate table, fastest first.

    Returns `[]` far more often than not, and that is the correct answer at
    current volume rather than a failure to look hard enough.

    A row without a usable first sighting is **skipped, not guessed at**. Rows
    written before 0014 have none, and assuming one would invent a velocity —
    which is the entire finding.
    """
    now = now or datetime.now(timezone.utc)
    found: list[Campaign] = []

    for row in reports or []:
        count = row.get("report_count") or 0
        if count < MIN_REPORTS:
            continue

        first = _parsed(row.get("first_reported_at"))
        if first is None:
            # Pre-0014 rows, and anything malformed. Silent per row rather than
            # fatal: one bad timestamp must not cost the whole run.
            continue

        last = _parsed(row.get("last_reported_at")) or now
        window = (last - first).total_seconds() / 3600
        if window < MIN_WINDOW_HOURS:
            # Not fast, just briefly observed.
            continue

        rate = count / window
        if rate < MIN_REPORTS_PER_HOUR:
            continue

        found.append(
            Campaign(
                pattern_hash=row["pattern_hash"],
                language=row.get("language", "en"),
                reports=count,
                window_hours=window,
                reports_per_hour=rate,
            )
        )

    # By rate. A slower message with a larger total is not the more urgent one,
    # and a list sorted by total would put last month's biggest at the top of a
    # dashboard meant to show what is happening now.
    return sorted(found, key=lambda c: (-c.reports_per_hour, c.pattern_hash))


def coverage() -> dict[str, list[str]]:
    """What this correlator is blind to, for anything that renders its output.

    A dashboard reporting "3 campaigns" without this overstates what is known.
    Carried as data rather than left in a docstring precisely so the surface
    that shows the number can show the caveat beside it.
    """
    return {
        "clusters_on": [
            "Identical messages, by digest",
            "How fast reports of one message are arriving",
        ],
        "cannot_cluster_on": [
            (
                "Similar-but-reworded messages. Reports are stored as one-way "
                "digests, so two wordings of one campaign look unrelated. Fixing "
                "this would mean storing something derived from the message, "
                "which is the privacy posture rather than a missing feature."
            ),
            (
                "Region or district. Location is not collected, and collecting "
                "it is a decision to argue on its own rather than inside a "
                "correlator."
            ),
        ],
    }
