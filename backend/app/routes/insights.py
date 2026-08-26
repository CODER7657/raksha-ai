"""Reviewer-facing surfaces for A3 and A1's measure (#115 §4, §5).

Both services were built, tested, and called by nothing. `campaign_correlator`
landed in #138 and `pattern_discovery` in #135/#139, and neither had a caller —
no route, no scheduler, no hook. Tested code that never executes is not a
feature; it is a claim with a test suite attached.

This is the caller. It composes rather than computes: every decision about what
counts as a campaign or a gap stays in the services, where it is tested. What
lives here is the reading of rows and the honesty about whether reading worked.

## The distinction this file exists to preserve

**"Nothing found" and "could not look" are different answers**, and a dashboard
that renders them the same way is worse than one that renders neither. A3
returning no campaigns is the correct and expected answer at current volume;
A3 returning no campaigns *because Supabase was unreachable* is an outage
wearing a clean bill of health.

So every payload carries an availability flag, the same shape `review.py` uses
for `decisions_available`, and every read that fails says so rather than
degrading into an empty list.

## The rule that is easiest to get wrong here

`pattern_discovery.rank_gaps` distinguishes a pattern count that is **absent**
from one that is **zero** — #139 fixed exactly that, after an earlier version
reported English, with forty patterns, as having no coverage. When the
`scam_patterns` read fails this module passes `None`, never `{}`. An empty dict
means "we looked and there are none"; `None` means "we did not find out". They
rank differently and they must.
"""

import logging
from collections import Counter
from dataclasses import asdict

from fastapi import APIRouter, Depends

from app.core.auth import get_current_user
from app.core.supabase_client import get_supabase
from app.services import (
    benchmark,
    campaign_correlator,
    pattern_discovery,
    pattern_review,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["insights"])

#: Enough to correlate over without paging. `community_reports` is one row per
#: distinct message digest rather than one per report, so this is a far smaller
#: table than the report count suggests.
_REPORT_LIMIT = 1000


def _read_community_reports() -> list[dict] | None:
    """Aggregate rows for A3, or `None` when the store could not be read.

    Selects exactly the five columns the correlator uses. It never reads message
    text because there is none to read — `community_reports` holds digests, not
    content — but naming the columns keeps that true by construction rather than
    by the table happening not to have a text column today.
    """
    try:
        response = (
            get_supabase()
            .table("community_reports")
            .select("pattern_hash,language,report_count,first_reported_at,last_reported_at")
            .limit(_REPORT_LIMIT)
            .execute()
        )
        return response.data or []
    except Exception:
        logger.exception("Could not read community_reports for the campaign view")
        return None


def _read_pattern_counts() -> dict[str, int] | None:
    """Patterns per language, or `None` when the store could not be read.

    `None` rather than `{}` on failure, and the difference is load-bearing: an
    empty dict tells `rank_gaps` that every language has zero patterns, which is
    the exact defect #139 fixed. Absent means unknown.
    """
    try:
        response = get_supabase().table("scam_patterns").select("language").execute()
    except Exception:
        logger.exception("Could not read scam_patterns for the discovery view")
        return None

    rows = response.data or []
    return dict(Counter(row["language"] for row in rows if row.get("language")))


@router.get("/insights/campaigns")
def campaign_view(_user_id: str = Depends(get_current_user)) -> dict:
    """Messages spreading fast enough to be worth calling a campaign.

    **Returns an empty list far more often than not**, and that is the correct
    answer at current volume rather than a failure to look hard enough. The
    thresholds are judgement rather than measurement — there is no data to tune
    them against yet, which is the point of §5.

    `coverage` travels with the numbers because the correlator is blind to two
    of the three things §04 asked it to cluster on: pattern similarity is
    impossible on a one-way digest, and region is not collected. A dashboard
    showing "3 campaigns" without that overstates what is known.
    """
    rows = _read_community_reports()

    if rows is None:
        return {
            "campaigns": [],
            "coverage": campaign_correlator.coverage(),
            "reports_available": False,
            "reports_scanned": 0,
        }

    found = campaign_correlator.campaigns(rows)
    return {
        "campaigns": [asdict(c) for c in found],
        "coverage": campaign_correlator.coverage(),
        "reports_available": True,
        "reports_scanned": len(rows),
    }


@router.get("/insights/discovery")
def discovery_view(_user_id: str = Depends(get_current_user)) -> dict:
    """Where drafting a pattern would buy the most, and how the loop is scoring.

    Two questions with one answer each, deliberately kept apart:

    - `gaps` ranks languages by the strongest reason to draft for them.
      Unmeasured gaps — no patterns at all — outrank measured misses, because a
      language with nothing to retrieve against is a stronger reason than one
      the benchmark happened to catch a miss in
    - `measure` is acceptance rate and rejections by reason. **There is no draft
      count**, on purpose: it is the number that makes a generator nobody
      accepts from look productive

    `acceptance_rate` is `None` rather than `0.0` for an undecided queue, and a
    client has to handle that third state. Zero and unknown are different
    claims, and reporting zero for a queue nobody has reviewed blames the
    generator for a reviewer backlog.
    """
    report = benchmark.run()
    languages = report.get("languages", [])

    missed_by_language = {
        entry["language"]: entry.get("missed_cases", []) for entry in languages
    }
    corpus_cases = {entry["language"]: entry.get("total_cases", 0) for entry in languages}

    pattern_counts = _read_pattern_counts()
    decisions = pattern_review.latest_decisions()

    gaps = pattern_discovery.rank_gaps(
        missed_by_language,
        corpus_cases=corpus_cases,
        pattern_counts=pattern_counts,
    )

    return {
        "gaps": [asdict(g) for g in gaps],
        "measure": pattern_discovery.report(decisions or {}),
        # Both flags matter and they fail independently. Ranking still works
        # without pattern counts — it simply cannot call anything unmeasured —
        # and the measure still works without the benchmark.
        "pattern_counts_available": pattern_counts is not None,
        "decisions_available": decisions is not None,
    }
