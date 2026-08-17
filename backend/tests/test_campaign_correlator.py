"""A3 — campaigns out of aggregate reports. #115 §5, `AGENT-LAYER.md` §04.

> Individual reports are noise; campaigns are signal. [...] Read-only over
> aggregate data — it never touches raw message content.

#115 §5 is unusually clear that this is expected to say little:

> **The honest blocker is data, not code.** A correlator that finds no campaigns
> across 14 patterns is working correctly. Build it, expect it to say little,
> let it become useful as volume arrives.

So the tests that matter are the ones asserting it stays quiet when it should,
and never manufactures a campaign to look useful.

## What §04 asks for, against what is stored

`community_reports` holds `pattern_hash`, `language`, `report_count`,
`last_reported_at`. §04 asks to cluster "by pattern similarity, timing and
region". Two of those three are not available, and one of them never will be:

- **Similarity is impossible over a one-way digest.** Two variants of one
  campaign — "your KYC expires today" and "...expires tomorrow" — have
  unrelated SHA-256s. Hash equality finds *identical* messages only, which is a
  narrower and honest claim
- **Region is not collected**, and that is a privacy decision rather than an
  oversight. Locating every report is a real change to "no message leaves the
  phone", not a column
- **Timing is half there.** `last_reported_at` without a first sighting cannot
  give velocity, and velocity is what separates a campaign from a popular
  message. That one is fixable, and 0014 fixes it

What remains is genuinely useful: one exact message reported many times, fast,
is a campaign — and it is the shape most Indian scam SMS actually takes, because
the same script is blasted verbatim.
"""

from datetime import datetime, timedelta, timezone

import pytest

from app.services import campaign_correlator

NOW = datetime(2026, 8, 17, 12, 0, tzinfo=timezone.utc)


def _report(digest: str, count: int, hours: float, language: str = "en", first=None) -> dict:
    return {
        "pattern_hash": digest,
        "language": language,
        "report_count": count,
        "first_reported_at": (first or (NOW - timedelta(hours=hours))).isoformat(),
        "last_reported_at": NOW.isoformat(),
    }


# --- it stays quiet ---------------------------------------------------------


def test_no_reports_is_no_campaigns():
    assert campaign_correlator.campaigns([], now=NOW) == []


def test_a_single_report_is_not_a_campaign():
    """One person seeing one message is the definition of noise."""
    assert campaign_correlator.campaigns([_report("a", 1, 2)], now=NOW) == []


def test_a_slow_trickle_is_not_a_campaign():
    """40 reports over three months is a message that circulates, not a campaign.
    Without velocity this is indistinguishable from a burst, which is why 0014
    adds the first sighting."""
    assert campaign_correlator.campaigns([_report("a", 40, 24 * 90)], now=NOW) == []


def test_the_expected_answer_today_is_nothing(caplog):
    """#115 §5: "a correlator that finds no campaigns across 14 patterns is
    working correctly". Pinned so a future change that starts inventing
    campaigns to look useful has to break a test that says why."""
    realistic = [_report(f"h{i}", 1, 5) for i in range(14)]
    assert campaign_correlator.campaigns(realistic, now=NOW) == []


# --- what it does find ------------------------------------------------------


def test_one_message_reported_many_times_quickly_is_a_campaign():
    found = campaign_correlator.campaigns([_report("a", 40, 6)], now=NOW)
    assert len(found) == 1
    assert found[0].pattern_hash == "a"


def test_a_campaign_reports_its_velocity_rather_than_a_bare_count():
    """"40 reports" is not actionable. "40 reports in 6 hours" is the sentence a
    cyber cell acts on."""
    campaign = campaign_correlator.campaigns([_report("a", 40, 6)], now=NOW)[0]
    assert campaign.reports_per_hour == pytest.approx(40 / 6, rel=0.01)
    assert campaign.window_hours == pytest.approx(6, rel=0.01)


def test_campaigns_are_ordered_by_velocity_not_by_total():
    """A slower message with a larger total is not the more urgent one.

    Both qualify here on purpose — 90 over 30h is 3/hour and 30 over 2h is
    15/hour — so this tests the ordering rather than the threshold. A dashboard
    sorted by total would put last month's biggest at the top of a panel meant
    to show what is happening now.
    """
    found = campaign_correlator.campaigns(
        [_report("slow", 90, 30), _report("fast", 30, 2)], now=NOW
    )
    assert [c.pattern_hash for c in found] == ["fast", "slow"]


def test_the_language_is_carried():
    campaign = campaign_correlator.campaigns([_report("a", 40, 6, language="hi")], now=NOW)[0]
    assert campaign.language == "hi"


# --- it never touches raw content -------------------------------------------


def test_the_correlator_never_reads_message_text():
    """§04: read-only over aggregate data, never raw message content. Asserted
    on the source, because the join that breaks it would look reasonable."""
    import ast
    import inspect

    tree = ast.parse(inspect.getsource(campaign_correlator))
    names = {
        node.value for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    } | {
        node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)
    }
    for banned in ("input_text", "scans", "explanation", "flagged_phrases"):
        assert banned not in names, (
            f"campaign_correlator references {banned!r}; A3 is aggregates only"
        )


def test_a_campaign_carries_the_digest_and_never_a_message():
    campaign = campaign_correlator.campaigns([_report("a", 40, 6)], now=NOW)[0]
    assert not hasattr(campaign, "text")
    assert campaign.pattern_hash == "a"


# --- the honesty of what it cannot do ---------------------------------------


def test_two_variants_of_one_campaign_are_not_correlated():
    """The limit worth stating out loud, and it is not a bug to fix later.

    §04 asks to cluster by "pattern similarity". `pattern_hash` is a one-way
    digest, so two wordings of the same scam have unrelated hashes and nothing
    here can join them. Doing so would need something derived from the message,
    which we deliberately do not store.

    So this reports two campaigns rather than one, and that is the honest
    answer — an under-count we can explain, not an over-count we cannot.
    """
    found = campaign_correlator.campaigns(
        [_report("variant-1", 30, 4), _report("variant-2", 28, 4)], now=NOW
    )
    assert len(found) == 2


def test_coverage_states_what_it_could_not_cluster_on():
    """A dashboard showing "3 campaigns" without saying the correlator is blind
    to rewording and to geography overstates what it knows."""
    note = campaign_correlator.coverage()
    assert "similar" in note["cannot_cluster_on"][0].lower()
    assert any("region" in item.lower() for item in note["cannot_cluster_on"])


# --- missing first sighting -------------------------------------------------


def test_a_report_with_no_first_sighting_is_skipped_rather_than_guessed():
    """Rows written before 0014 have no first sighting. Assuming one would
    invent a velocity, and velocity is the whole finding."""
    stale = {
        "pattern_hash": "a", "language": "en", "report_count": 40,
        "first_reported_at": None, "last_reported_at": NOW.isoformat(),
    }
    assert campaign_correlator.campaigns([stale], now=NOW) == []


def test_a_malformed_timestamp_does_not_take_the_run_down():
    broken = {
        "pattern_hash": "a", "language": "en", "report_count": 40,
        "first_reported_at": "not-a-date", "last_reported_at": NOW.isoformat(),
    }
    assert campaign_correlator.campaigns([broken], now=NOW) == []
