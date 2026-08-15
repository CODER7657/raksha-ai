"""Kill switches, budget caps and the run log (#32 D, AGENT-LAYER.md §09).

Three properties, in the order they matter.

**The detection path never calls into this module.** §09 says any agent can be
disabled "without touching the others or the detection path". If `scan.py` read
agent state, an unreachable table or a stuck switch would stop fraud warnings
reaching users — a cost control turned into an outage. `test_agent_control.py`
asserts nothing under `routes/scan.py` imports this.

**The switch fails closed, the console fails open.** `may_run` returns False if
it cannot reach the database: an agent that spends money on a burst of API calls
should not run when nobody can tell whether it was disabled. `overview` does the
opposite and surfaces the error, because a console that hides its own blindness
is worse than one that says it cannot see.

**A blocked run is still a run.** It goes in the log with `outcome='blocked'`.
An operator asking "did the kill switch work?" needs the evidence that it fired,
not the absence of evidence that it did not.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from app.core.supabase_client import get_supabase

logger = logging.getLogger(__name__)

#: Agents registered by migration 0006. Duplicated here so a typo in a CLI flag
#: is caught before a round trip, and so the CLIs have something to validate
#: against offline. `test_agent_ids_match_the_migration` keeps the two honest.
KNOWN_AGENTS = ("a6_redteam", "llm_benchmark")

OUTCOMES = ("ok", "failed", "blocked")


@dataclass(frozen=True)
class RunDecision:
    """Whether an agent may spend, and the sentence to print if not."""

    allowed: bool
    reason: str | None = None


def may_run(agent_id: str, planned_calls: int = 0) -> RunDecision:
    """Checked by an agent before it spends anything.

    Fails closed. If the control plane is unreachable we do not know whether
    someone disabled this agent an hour ago, and the cost of wrongly running is
    real money on the same free-tier keys production uses (#59). The cost of
    wrongly refusing is a human re-running a CLI.
    """
    if agent_id not in KNOWN_AGENTS:
        return RunDecision(False, f"Unknown agent '{agent_id}'. Known: {', '.join(KNOWN_AGENTS)}")

    try:
        rows = (
            get_supabase()
            .table("agent_overview")
            .select("enabled, disabled_reason, spend_cap_calls, calls_24h")
            .eq("agent_id", agent_id)
            .execute()
            .data
            or []
        )
    except Exception:
        logger.exception("Agent control plane unreachable while checking %s", agent_id)
        return RunDecision(
            False,
            "Cannot reach the agent control plane, so whether this agent is disabled is "
            "unknown. Refusing rather than spending API quota on a guess.",
        )

    if not rows:
        return RunDecision(False, f"'{agent_id}' is not registered. Run migration 0006.")

    state = rows[0]
    if not state["enabled"]:
        why = state.get("disabled_reason") or "no reason recorded"
        return RunDecision(False, f"'{agent_id}' is disabled: {why}")

    cap = state.get("spend_cap_calls")
    spent = state.get("calls_24h") or 0
    if cap is not None and spent + planned_calls > cap:
        # §09: "Exceeding the cap stops the agent, it does not degrade quality
        # silently." Refusing the whole run is the stop; a partial run would be
        # the silent degradation.
        return RunDecision(
            False,
            f"'{agent_id}' would exceed its 24h cap: {spent} used + {planned_calls} planned "
            f"> {cap}. Raise the cap deliberately or wait for the window to roll.",
        )

    return RunDecision(True)


def record_run(agent_id: str, outcome: str, model_calls: int = 0, detail: dict | None = None) -> None:
    """Append to the run log. Best-effort, and deliberately so.

    An agent that has already done its work must not fail because the log was
    unreachable — that would turn an observability gap into lost work. The
    failure is loud in the logs and shows up as a missing run in the console,
    which is the honest symptom.
    """
    if outcome not in OUTCOMES:
        raise ValueError(f"outcome must be one of {OUTCOMES}, got {outcome!r}")

    try:
        get_supabase().rpc(
            "record_agent_run",
            {
                "p_agent_id": agent_id,
                "p_outcome": outcome,
                "p_model_calls": model_calls,
                "p_detail": detail,
            },
        ).execute()
    except Exception:
        logger.exception("Could not record %s run for %s", outcome, agent_id)


def overview() -> dict:
    """What the console renders.

    Surfaces its own failure rather than returning an empty list: an operator
    who sees no agents cannot tell "none registered" from "cannot reach the
    database", and those call for opposite responses.
    """
    try:
        rows = get_supabase().table("agent_overview").select("*").order("agent_id").execute().data or []
    except Exception:
        logger.exception("Could not read the agent overview")
        return {"available": False, "agents": []}

    return {"available": True, "agents": [_with_budget(row) for row in rows]}


def _with_budget(row: dict) -> dict:
    """Spend as a fraction of cap, computed once here rather than in the UI.

    `budget_used` is None when uncapped — not 0, and not 1. An uncapped agent
    has no meaningful fraction, and rendering one as an empty progress bar
    reads as "plenty of room left" rather than "no limit is being enforced".
    """
    cap = row.get("spend_cap_calls")
    spent = row.get("calls_24h") or 0
    return {
        **row,
        "calls_24h": spent,
        "budget_used": round(spent / cap, 4) if cap else None,
        "over_cap": bool(cap and spent >= cap),
    }


def is_operator(user_id: str) -> bool:
    """Whether this user may stop or start an agent.

    An env-var allowlist, and a stopgap — it exists because there is no role
    system and signup is open, so `authenticated` means anyone who registers.
    That is fine for the read-only reviewer screens, which only disclose; this
    endpoint writes.

    Unset means nobody. An empty allowlist is "we have not said who the
    operators are", and reading that as "everyone" is the hole being closed.
    """
    from app.core.config import get_settings

    return user_id in get_settings().agent_operator_id_list


def set_enabled(agent_id: str, enabled: bool, reason: str | None, actor: str) -> dict:
    """Flip the switch. Raises, because unlike the read path a failure here must
    not look like success — an operator who believes they stopped an agent and
    did not is the worst outcome this screen can produce."""
    if agent_id not in KNOWN_AGENTS:
        raise ValueError(f"Unknown agent '{agent_id}'")
    if not enabled and not (reason or "").strip():
        # A switch with no reason gets flipped back by the next person, who
        # cannot tell whether it was deliberate.
        raise ValueError("Disabling an agent requires a reason")

    rows = (
        get_supabase()
        .rpc(
            "set_agent_enabled",
            {
                "p_agent_id": agent_id,
                "p_enabled": enabled,
                "p_reason": reason,
                "p_actor": actor,
            },
        )
        .execute()
        .data
    )
    return rows[0] if isinstance(rows, list) and rows else rows


def recent_runs(agent_id: str | None = None, limit: int = 25) -> list[dict]:
    try:
        query = get_supabase().table("agent_runs").select("*")
        if agent_id:
            query = query.eq("agent_id", agent_id)
        # `id desc` for the same reason `agent_overview` needs it: `now()` is
        # transaction-scoped, so runs recorded in one transaction share a
        # `started_at` and time alone orders them arbitrarily. Less severe here
        # — it misorders a list rather than naming the wrong "latest" — but
        # fixing the view and leaving the sibling path undercuts the reasoning.
        return (
            query.order("started_at", desc=True)
            .order("id", desc=True)
            .limit(limit)
            .execute()
            .data
            or []
        )
    except Exception:
        logger.exception("Could not read the agent run log")
        return []
