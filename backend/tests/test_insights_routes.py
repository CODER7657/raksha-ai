"""The A3 and A1-measure surfaces (#115 §4, §5).

Both services were built, tested, and called by nothing until `insights.py`.
These tests cover the part the services cannot cover for themselves: whether the
caller reads honestly, and whether it preserves the two distinctions this
project has already paid to learn.

**"Nothing found" against "could not look".** A3 returning no campaigns is the
expected answer at current volume. A3 returning no campaigns because the store
was unreachable is an outage wearing a clean bill of health, and a dashboard
cannot tell them apart unless the payload does.

**Absent against zero.** #139 fixed `rank_gaps` reporting English, with forty
patterns, as having no coverage — because a missing `pattern_counts` argument
was defaulted to `{}` rather than kept as `None`. A route that catches a failed
read and passes `{}` reintroduces exactly that defect one layer up, and it would
do it silently: the ranking would still return, just wrong.

The route functions are called directly rather than through a `TestClient`.
There is no HTTP-level test infrastructure in this suite and adding it for two
endpoints would be a larger change than the endpoints; what a client would add
here is coverage of FastAPI's own dependency injection. The auth requirement is
asserted against the route definitions instead, which is the part that is ours
to get wrong.
"""

from datetime import datetime, timedelta, timezone

import pytest

from app.routes import insights
from app.services import pattern_discovery

NOW = datetime(2026, 8, 18, 12, 0, tzinfo=timezone.utc)


def _campaign_row(**overrides) -> dict:
    """A row that clears every threshold, so a test that wants a campaign gets
    one and a test that wants none can move a single field."""
    row = {
        "pattern_hash": "a" * 64,
        "language": "hi",
        "report_count": 60,
        "first_reported_at": (NOW - timedelta(hours=4)).isoformat(),
        "last_reported_at": NOW.isoformat(),
    }
    row.update(overrides)
    return row


# --- A3: the campaign view -------------------------------------------------


def test_an_unreachable_store_is_not_reported_as_no_campaigns(monkeypatch):
    """The distinction this file exists for. Both cases return an empty list;
    only the flag says whether anybody looked."""
    monkeypatch.setattr(insights, "_read_community_reports", lambda: None)

    payload = insights.campaign_view()

    assert payload["campaigns"] == []
    assert payload["reports_available"] is False
    assert payload["reports_scanned"] == 0


def test_no_campaigns_from_real_rows_is_a_different_answer(monkeypatch):
    """Fourteen singleton patterns is today's reality and the correct output is
    an empty list — but a *looked and found nothing* empty list."""
    rows = [_campaign_row(pattern_hash=str(i), report_count=1) for i in range(14)]
    monkeypatch.setattr(insights, "_read_community_reports", lambda: rows)

    payload = insights.campaign_view()

    assert payload["campaigns"] == []
    assert payload["reports_available"] is True
    assert payload["reports_scanned"] == 14


def test_a_real_campaign_is_returned_and_serialised(monkeypatch):
    """The control. A view that only ever returns nothing would pass both tests
    above while being completely broken."""
    monkeypatch.setattr(insights, "_read_community_reports", lambda: [_campaign_row()])

    payload = insights.campaign_view()

    assert len(payload["campaigns"]) == 1
    campaign = payload["campaigns"][0]
    assert campaign["language"] == "hi"
    assert campaign["reports"] == 60
    assert campaign["reports_per_hour"] == pytest.approx(15.0)
    assert isinstance(campaign, dict), "dataclasses must be serialised, not returned raw"


def test_the_campaign_view_never_carries_message_text(monkeypatch):
    """`community_reports` holds digests, and the correlator has no text field.
    Asserted at the payload because that is what a dashboard renders."""
    monkeypatch.setattr(insights, "_read_community_reports", lambda: [_campaign_row()])

    payload = insights.campaign_view()

    for campaign in payload["campaigns"]:
        for banned in ("text", "message", "body", "input_text"):
            assert banned not in campaign, f"{banned} reached a campaign payload"


def test_coverage_travels_with_the_number_even_when_empty(monkeypatch):
    """A count without the caveat overstates what is known, and the empty case
    is exactly where somebody would be tempted to drop it."""
    monkeypatch.setattr(insights, "_read_community_reports", list)

    payload = insights.campaign_view()

    assert payload["coverage"]["cannot_cluster_on"], "the blind spots must be reported"


# --- A1: the discovery view ------------------------------------------------


def test_a_failed_pattern_count_read_passes_none_not_an_empty_dict(monkeypatch):
    """The #139 defect, one layer up.

    An empty dict tells `rank_gaps` that every language has zero patterns, which
    is how English — with forty — was reported as uncovered. A route that
    swallows a read failure into `{}` reintroduces that silently: the ranking
    still returns, it is simply wrong.
    """
    seen: dict = {}

    def capture(missed, *, corpus_cases=None, pattern_counts=None):
        seen["pattern_counts"] = pattern_counts
        seen["called"] = True
        return []

    monkeypatch.setattr(insights, "_read_pattern_counts", lambda: None)
    monkeypatch.setattr(insights.pattern_review, "latest_decisions", dict)
    monkeypatch.setattr(insights.pattern_discovery, "rank_gaps", capture)

    insights.discovery_view()

    assert seen["called"], "rank_gaps was never reached"
    assert seen["pattern_counts"] is None, (
        "a failed read must stay unknown; {} means 'we looked and found none'"
    )


def test_a_successful_pattern_count_read_is_passed_through(monkeypatch):
    """The control for the test above — otherwise it would pass with the read
    permanently broken."""
    seen: dict = {}

    def capture(missed, *, corpus_cases=None, pattern_counts=None):
        seen["pattern_counts"] = pattern_counts
        return []

    monkeypatch.setattr(insights, "_read_pattern_counts", lambda: {"en": 40, "gu": 14})
    monkeypatch.setattr(insights.pattern_review, "latest_decisions", dict)
    monkeypatch.setattr(insights.pattern_discovery, "rank_gaps", capture)

    insights.discovery_view()

    assert seen["pattern_counts"] == {"en": 40, "gu": 14}


def test_availability_flags_fail_independently(monkeypatch):
    """Ranking works without pattern counts and the measure works without the
    decision store. One failing must not report the other as unavailable."""
    monkeypatch.setattr(insights, "_read_pattern_counts", lambda: None)
    monkeypatch.setattr(insights.pattern_review, "latest_decisions", lambda: {"d1": {}})

    payload = insights.discovery_view()

    assert payload["pattern_counts_available"] is False
    assert payload["decisions_available"] is True


def test_an_unreadable_decision_store_is_not_an_empty_queue(monkeypatch):
    """`latest_decisions` returns None when it cannot read. Reporting that as a
    queue nobody has decided on would blame the reviewer for an outage."""
    monkeypatch.setattr(insights, "_read_pattern_counts", dict)
    monkeypatch.setattr(insights.pattern_review, "latest_decisions", lambda: None)

    payload = insights.discovery_view()

    assert payload["decisions_available"] is False
    assert payload["measure"]["acceptance_rate"] is None


def test_the_measure_carries_no_draft_count(monkeypatch):
    """#115 §4: the measure is acceptance rate, not draft count. Draft count is
    the number that makes a generator nobody accepts from look productive, and a
    route is where it would get added back for a nicer dashboard."""
    monkeypatch.setattr(insights, "_read_pattern_counts", dict)
    monkeypatch.setattr(insights.pattern_review, "latest_decisions", dict)

    payload = insights.discovery_view()

    for banned in ("drafts", "draft_count", "drafted", "total_drafts"):
        assert banned not in payload["measure"], f"{banned} is not the measure"


def test_gaps_are_serialised_and_ranked_unmeasured_first(monkeypatch):
    """End to end against the real service, so the composition is exercised
    rather than only the reading. Nine languages have no patterns; those are the
    ones a reviewer should be sent to first."""
    monkeypatch.setattr(
        insights, "_read_pattern_counts", lambda: {"en": 40, "hi": 40, "gu": 14}
    )
    monkeypatch.setattr(insights.pattern_review, "latest_decisions", dict)

    payload = insights.discovery_view()

    assert payload["gaps"], "the real benchmark should surface gaps"
    assert all(isinstance(g, dict) for g in payload["gaps"])
    kinds = [g["kind"] for g in payload["gaps"]]
    assert kinds == sorted(kinds, key=lambda k: 0 if k == "unmeasured" else 1), (
        "unmeasured gaps must outrank measured ones"
    )


def test_gap_shape_matches_the_service(monkeypatch):
    """The payload is `asdict` over the dataclass, so a field added to `Gap`
    reaches the client without anyone editing this route. Pinned so that a
    rename is a visible break rather than a quietly missing key."""
    monkeypatch.setattr(insights, "_read_pattern_counts", lambda: {"en": 40})
    monkeypatch.setattr(insights.pattern_review, "latest_decisions", dict)

    payload = insights.discovery_view()

    expected = set(pattern_discovery.Gap.__dataclass_fields__)
    assert set(payload["gaps"][0]) == expected


# --- both surfaces ---------------------------------------------------------


def test_every_insights_route_requires_authentication():
    """Neither of these is public. The campaign view names which languages are
    being targeted and the discovery view names where our coverage is thinnest —
    a map of where the safety net is weakest, which is not a thing to serve
    anonymously.

    Asserted against the route definitions because calling the functions
    directly bypasses FastAPI's dependency injection entirely, so no direct call
    could ever catch a missing `Depends`.
    """
    assert insights.router.routes, "the router has no routes at all"

    for route in insights.router.routes:
        names = [d.call.__name__ for d in route.dependant.dependencies]
        assert "get_current_user" in names, (
            f"{route.path} does not require authentication"
        )
