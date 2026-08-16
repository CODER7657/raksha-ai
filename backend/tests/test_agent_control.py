"""Kill switches and budget caps (#32 D, AGENT-LAYER.md §09).

The first test is the one that matters. Everything else here protects money;
that one protects users.
"""

import pathlib

import pytest

from app.services import agent_control

# --- the property that outranks the rest -----------------------------------


def test_the_control_plane_cannot_reach_the_detection_path():
    """§09: any agent can be disabled "without touching the others or the
    detection path".

    If `scan.py` imported this module, an unreachable control plane or a stuck
    switch would stop fraud warnings — turning a cost control into an outage,
    which is a strictly worse failure than the one it prevents. Asserted on the
    source rather than trusted to review, because the import that breaks it
    would look entirely reasonable in a diff.
    """
    scan_src = (pathlib.Path(__file__).resolve().parents[1] / "app/routes/scan.py").read_text(
        encoding="utf-8"
    )
    assert "agent_control" not in scan_src, (
        "scan.py must not consult the agent control plane. A disabled agent must "
        "never be able to stop a user getting a fraud warning."
    )

    for module in ("llm.py", "rag.py", "rule_engine.py", "trace.py", "verdict_cache.py"):
        src = (pathlib.Path(__file__).resolve().parents[1] / "app/services" / module).read_text(
            encoding="utf-8"
        )
        assert "agent_control" not in src, f"{module} is on the detection path and must stay clear"


def test_agent_ids_match_the_migrations():
    """KNOWN_AGENTS is duplicated from the migrations so a CLI typo fails before
    a round trip. This is what keeps the duplicate honest.

    Scans every migration rather than only 0006: agents are registered as they
    are built, and `a2_page_analysis` arrives in 0012. Pinning this to one file
    would mean a new agent could be in the tuple, absent from the database, and
    fail only at `may_run` — which fails closed, so the symptom would be an
    agent that silently never runs.
    """
    migrations = (pathlib.Path(__file__).resolve().parents[2] / "supabase/migrations")
    registered = "\n".join(
        path.read_text(encoding="utf-8") for path in sorted(migrations.glob("*.sql"))
    )
    for agent_id in agent_control.KNOWN_AGENTS:
        assert f"'{agent_id}'" in registered, (
            f"{agent_id} is in KNOWN_AGENTS and no migration registers it"
        )


def test_pulling_a2s_kill_switch_stops_it(monkeypatch):
    """#115: every agent under "a kill switch that has been **pulled and
    observed**". Present is not the same as working, so this pulls it.

    A2 is the agent this matters most for. The other two spend money when they
    misbehave; A2 fetches a URL an attacker chose, from our infrastructure. The
    switch is the thing that stops that inside one UPDATE, and a switch nobody
    has tried is a switch nobody knows the state of.
    """
    # Enabled first, so the refusal below is demonstrably the switch and not the
    # fail-closed path — an unreachable control plane refuses too, and a test
    # that cannot tell them apart proves nothing.
    _stub(monkeypatch, {"enabled": True, "spend_cap_calls": 100})
    assert agent_control.may_run("a2_page_analysis", 1).allowed

    _stub(monkeypatch, {"enabled": False, "disabled_reason": "pulled in a test"})
    decision = agent_control.may_run("a2_page_analysis", 1)

    assert not decision.allowed
    assert "pulled in a test" in (decision.reason or "")


def test_a2_is_registered_before_it_can_run():
    """`may_run` refuses an unknown agent, so an unregistered A2 cannot spend
    even if someone wires the sandbox up first."""
    assert "a2_page_analysis" in agent_control.KNOWN_AGENTS


# --- the switch fails closed ------------------------------------------------


def test_unreachable_control_plane_refuses_to_run(monkeypatch):
    """Fails closed on purpose. If we cannot tell whether someone disabled this
    agent an hour ago, the cost of wrongly running is real money on the keys
    production shares; the cost of wrongly refusing is re-running a CLI."""
    monkeypatch.setattr(agent_control, "get_supabase", _raises)

    decision = agent_control.may_run("a6_redteam", 10)
    assert not decision.allowed
    assert "unknown" in decision.reason.lower()


def test_unknown_agent_is_refused_without_a_round_trip(monkeypatch):
    monkeypatch.setattr(agent_control, "get_supabase", _raises)  # would blow up if reached
    decision = agent_control.may_run("typo_agent")
    assert not decision.allowed
    assert "Unknown agent" in decision.reason


def test_disabled_agent_is_refused_with_the_reason(monkeypatch):
    _stub(monkeypatch, {"enabled": False, "disabled_reason": "looping on transliteration"})

    decision = agent_control.may_run("a6_redteam", 10)
    assert not decision.allowed
    # The operator's note has to reach whoever hits the wall, or they just
    # re-enable it.
    assert "looping on transliteration" in decision.reason


def test_a_disabled_agent_with_no_reason_still_explains_itself(monkeypatch):
    _stub(monkeypatch, {"enabled": False, "disabled_reason": None})
    decision = agent_control.may_run("a6_redteam")
    assert not decision.allowed
    assert "no reason recorded" in decision.reason


# --- the cap stops rather than degrades ------------------------------------


def test_exceeding_the_cap_refuses_the_whole_run(monkeypatch):
    """§09: "Exceeding the cap stops the agent, it does not degrade quality
    silently." A partial run would be the silent degradation."""
    _stub(monkeypatch, {"enabled": True, "spend_cap_calls": 200, "calls_24h": 190})

    assert not agent_control.may_run("a6_redteam", 20).allowed
    # Still room for a smaller run — the cap bounds spend, it is not a tripwire
    # that latches.
    assert agent_control.may_run("a6_redteam", 5).allowed


def test_an_uncapped_agent_is_not_treated_as_capped_at_zero(monkeypatch):
    _stub(monkeypatch, {"enabled": True, "spend_cap_calls": None, "calls_24h": 5000})
    assert agent_control.may_run("a6_redteam", 1000).allowed


def test_budget_used_is_none_when_uncapped():
    """Not 0, and not 1. An uncapped agent has no meaningful fraction, and an
    empty progress bar reads as "plenty of room" rather than "no limit"."""
    row = agent_control._with_budget({"spend_cap_calls": None, "calls_24h": 900})
    assert row["budget_used"] is None
    assert row["over_cap"] is False

    row = agent_control._with_budget({"spend_cap_calls": 200, "calls_24h": 150})
    assert row["budget_used"] == 0.75
    assert row["over_cap"] is False

    row = agent_control._with_budget({"spend_cap_calls": 200, "calls_24h": 200})
    assert row["over_cap"] is True


# --- the console surfaces its own blindness --------------------------------


def test_overview_says_when_it_cannot_see(monkeypatch):
    """An operator seeing no agents must be able to tell "none registered" from
    "cannot reach the database" — those call for opposite responses."""
    monkeypatch.setattr(agent_control, "get_supabase", _raises)
    result = agent_control.overview()
    assert result["available"] is False
    assert result["agents"] == []


# --- writes must not look like successes when they fail --------------------


def test_disabling_requires_a_reason():
    with pytest.raises(ValueError, match="requires a reason"):
        agent_control.set_enabled("a6_redteam", False, "   ", "user-1")


def test_enabling_needs_no_reason(monkeypatch):
    captured = {}

    class Rpc:
        def __init__(self, name, params):
            captured.update(params)

        def execute(self):
            return type("R", (), {"data": [{"agent_id": "a6_redteam", "enabled": True}]})()

    monkeypatch.setattr(
        agent_control, "get_supabase", lambda: type("C", (), {"rpc": lambda s, n, p: Rpc(n, p)})()
    )
    assert agent_control.set_enabled("a6_redteam", True, None, "user-1")["enabled"] is True
    assert captured["p_enabled"] is True


def test_switching_an_unknown_agent_raises():
    with pytest.raises(ValueError, match="Unknown agent"):
        agent_control.set_enabled("nope", False, "reason", "user-1")


# --- the run log ------------------------------------------------------------


def test_a_bad_outcome_is_rejected_before_it_reaches_the_log():
    with pytest.raises(ValueError, match="outcome must be one of"):
        agent_control.record_run("a6_redteam", "weird", 1)


def test_recording_a_run_never_raises(monkeypatch):
    """An agent that has already done its work must not fail because the log
    was unreachable — that turns an observability gap into lost work."""
    monkeypatch.setattr(agent_control, "get_supabase", _raises)
    agent_control.record_run("a6_redteam", "ok", 42)  # must not raise


def test_blocked_is_a_recordable_outcome():
    """An operator asking "did the kill switch fire?" needs the evidence that
    it did, not the absence of evidence that it did not."""
    assert "blocked" in agent_control.OUTCOMES


def _raises(*_args, **_kwargs):
    raise RuntimeError("control plane unreachable")


def _stub(monkeypatch, row: dict):
    """Stubs the agent_overview read with one row."""
    full = {"enabled": True, "disabled_reason": None, "spend_cap_calls": None, "calls_24h": 0}
    full.update(row)

    class Query:
        def select(self, *_a):
            return self

        def eq(self, *_a):
            return self

        def execute(self):
            return type("R", (), {"data": [full]})()

    monkeypatch.setattr(
        agent_control, "get_supabase", lambda: type("C", (), {"table": lambda s, n: Query()})()
    )


# --- who may flip the switch (#75 review) ----------------------------------


def test_an_empty_allowlist_means_nobody(monkeypatch):
    """Not everybody. An unset allowlist is "we have not said who the operators
    are", and resolving that to "any signed-in user" is the hole this closes —
    signup is open, so authenticated means anyone who registers."""
    from app.core.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("AGENT_OPERATOR_IDS", "")
    try:
        assert not agent_control.is_operator("11111111-1111-1111-1111-111111111111")
    finally:
        get_settings.cache_clear()


def test_only_listed_operators_pass(monkeypatch):
    from app.core.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("AGENT_OPERATOR_IDS", "aaaa-1, bbbb-2")
    try:
        assert agent_control.is_operator("aaaa-1")
        # Whitespace around a comma-separated list is a real thing people type.
        assert agent_control.is_operator("bbbb-2")
        assert not agent_control.is_operator("cccc-3")
    finally:
        get_settings.cache_clear()


def test_the_write_endpoint_is_gated_and_the_reads_are_not():
    """The reads only disclose; this one writes. A stranger stopping the
    red-team loop, or planting a string in disabled_reason for the next
    operator to read, is a different thing from seeing a spend figure."""
    import pathlib

    src = (pathlib.Path(__file__).resolve().parents[1] / "app/routes/review.py").read_text(
        encoding="utf-8"
    )
    switch = src.split("def switch_agent(")[1]
    assert "is_operator" in switch, "the switch endpoint must check the operator allowlist"

    # The read endpoints stay open — tightening them was not the finding, and
    # doing it here would widen the change beyond what was asked.
    overview = src.split("def list_agents(")[1].split("def ")[0]
    assert "is_operator" not in overview
