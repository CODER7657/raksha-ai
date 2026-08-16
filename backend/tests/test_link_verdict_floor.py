"""A `safe` verdict must not sit on top of evidence that contradicts it.

Raised in review of #124. `addenda` reached `trace` and never touched `result`,
so a user could be shown:

    verdict: safe
    trace.link_signals.independent_witnesses: 3

Three independent bases saying the link is phishing, under a verdict saying the
message is fine. **The user reads the verdict.** They do not open the trace and
reconcile it, and if they did we have told them two things. Constraint 4 is
*fail safe, never confidently wrong*, and this is exactly confidently wrong.

The fix is a **floor, not an override**, matching what `scan.py` already does
for offline rules: link evidence can only ever make a verdict more cautious.
`suspicious` and `high_risk` are untouched, and nothing here can lower a
verdict.

## Where the thresholds come from

A floor at *any* deterministic signal would be wrong in the other direction: one
weak signal is a `.xyz` domain, and every cheap TLD would stop being `safe`.
A2's benign half is larger than its phishing half.

So: **two independent bases with at least one deterministic** — §01's "High"
tier, the point at which the policy is already willing to block for the
reporting user. Plus a **feed listing on its own**, because that is a statement
about this exact URL made by someone who looked at it, rather than an inference
drawn from its spelling.
"""

import pytest

from app.routes import scan
from app.services import trace as trace_service
from app.services.link_signals import BASIS_FEED, BASIS_HOST_LABEL, BASIS_TLD, Signal

SAFE = {
    "risk_score": 5,
    "verdict": "safe",
    "flagged_phrases": [],
    "explanation": "Nothing unusual in the wording.",
    "recommended_action_id": "no_action",
    "recommended_action": "No action needed.",
}


def _block(*signals: Signal) -> dict:
    return trace_service.link_signal_block(list(signals))


def _sig(name: str, basis: str, deterministic: bool = True) -> Signal:
    return Signal(name=name, basis=basis, deterministic=deterministic, detail="d")


# --- when the floor applies -----------------------------------------------


def test_two_independent_deterministic_bases_stop_a_safe_verdict():
    trace = {"link_signals": _block(
        _sig("brand_impersonation", BASIS_HOST_LABEL), _sig("suspicious_tld", BASIS_TLD)
    )}
    result, floored = scan._apply_link_floor(dict(SAFE), trace)

    assert result["verdict"] == "suspicious"
    assert floored["link_signals"]["verdict_floor_applied"] is True


def test_a_feed_listing_alone_stops_a_safe_verdict():
    """One basis, and enough. A blocklist entry is a statement about this exact
    URL by someone who looked at it, not an inference from its spelling."""
    trace = {"link_signals": _block(_sig("known_bad_feed", BASIS_FEED))}
    result, _ = scan._apply_link_floor(dict(SAFE), trace)
    assert result["verdict"] == "suspicious"


def test_the_floored_verdict_explains_that_it_was_the_link():
    """"This message is a scam" and "the wording was fine but the link was not"
    are different stories, and the user acts on the second one differently."""
    trace = {"link_signals": _block(
        _sig("brand_impersonation", BASIS_HOST_LABEL), _sig("suspicious_tld", BASIS_TLD)
    )}
    result, _ = scan._apply_link_floor(dict(SAFE), trace)
    assert "link" in result["explanation"].lower()


def test_the_floored_action_comes_from_the_closed_set():
    """#113: there is exactly one place user-facing advice is written. A floor
    that invented its own sentence would be a second."""
    trace = {"link_signals": _block(_sig("known_bad_feed", BASIS_FEED))}
    result, _ = scan._apply_link_floor(dict(SAFE), trace)
    assert result["recommended_action_id"]
    assert result["recommended_action"] != SAFE["recommended_action"]


def test_the_floored_score_is_not_the_offline_fallback_score():
    """70 means "a rule fired and no model answered". This is "a model answered
    safe and the link disagrees", a weaker claim that should not read as the
    same confidence."""
    trace = {"link_signals": _block(_sig("known_bad_feed", BASIS_FEED))}
    result, _ = scan._apply_link_floor(dict(SAFE), trace)
    assert result["risk_score"] == 60


# --- when it does not ------------------------------------------------------


def test_one_weak_signal_does_not_floor_anything():
    """The false-positive half, and the reason the threshold is not "any
    deterministic signal". Flooring here would make every `.xyz` non-safe."""
    trace = {"link_signals": _block(_sig("suspicious_tld", BASIS_TLD))}
    result, floored = scan._apply_link_floor(dict(SAFE), trace)

    assert result["verdict"] == "safe"
    assert floored["link_signals"]["verdict_floor_applied"] is False


def test_two_signals_sharing_one_basis_do_not_floor():
    """The counting rule, enforced where it matters. Three checks reading one
    host label are one witness — a single lookalike domain must not floor on its
    own reflections."""
    trace = {"link_signals": _block(
        _sig("homograph_domain", BASIS_HOST_LABEL),
        _sig("brand_lookalike", BASIS_HOST_LABEL),
        _sig("high_entropy_host", BASIS_HOST_LABEL),
    )}
    result, _ = scan._apply_link_floor(dict(SAFE), trace)
    assert result["verdict"] == "safe"


def test_a_message_with_no_links_is_untouched():
    result, trace = scan._apply_link_floor(dict(SAFE), {})
    assert result["verdict"] == "safe"
    assert trace == {}


@pytest.mark.parametrize("verdict,score", [("suspicious", 70), ("high_risk", 95)])
def test_the_floor_never_lowers_a_verdict(verdict, score):
    """It is a floor. A weaker link finding must not talk a high_risk verdict
    down, which an override would."""
    original = {**SAFE, "verdict": verdict, "risk_score": score}
    trace = {"link_signals": _block(_sig("known_bad_feed", BASIS_FEED))}
    result, floored = scan._apply_link_floor(original, trace)

    assert result["verdict"] == verdict
    assert result["risk_score"] == score
    assert floored["link_signals"]["verdict_floor_applied"] is False


def test_a_non_deterministic_pair_does_not_floor():
    """Stage 1 is all deterministic, so this guards stages 2-3: a model that has
    just read attacker-controlled text cannot be the sole witness to its own
    conclusion, however many bases it produces."""
    trace = {"link_signals": _block(
        _sig("agent_verdict", "page_content", deterministic=False),
        _sig("agent_reasoning", "page_reasoning", deterministic=False),
    )}
    result, _ = scan._apply_link_floor(dict(SAFE), trace)
    assert result["verdict"] == "safe"
