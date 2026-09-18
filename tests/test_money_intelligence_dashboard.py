import json
from pathlib import Path

import money_intelligence_dashboard as mid


_ALLOWED_RESEARCH_STATES = {
    "BOOTSTRAP_LEARNING",
    "INITIAL_VALIDATED_ASSESSMENT",
    "VALIDATED_CAUSAL_UPDATE_WAIT_NO_EDGE",
}


def test_money_intelligence_state_is_explicitly_fail_closed():
    state = json.loads((Path(__file__).parents[1] / "money_intelligence" / "dashboard_state.json").read_text())
    assert state["status"] in _ALLOWED_RESEARCH_STATES
    scorecard = state["prediction_scorecard"]
    if scorecard["resolved"] == 0:
        assert scorecard["directional_hit_rate"] is None
        assert scorecard["brier_score"] is None
    if state["status"] == "BOOTSTRAP_LEARNING":
        assert state["opportunities"] == []
    elif state["status"] == "INITIAL_VALIDATED_ASSESSMENT":
        assert all(opportunity.get("action") == "WAIT" for opportunity in state["opportunities"])
    else:
        # Money Intelligence may publish research-only BUY/HOLD/REDUCE/etc. hypotheses,
        # but its dashboard state must never claim live/execution authority.
        for opportunity in state["opportunities"]:
            action = str(opportunity.get("action") or "").upper()
            assert "EXECUTE" not in action
            assert "LIVE" not in action


def test_money_dashboard_has_independent_sections(monkeypatch):
    monkeypatch.setattr(mid, "_authorized", lambda request: True)
    response = mid.money_dashboard_page(object())
    body = response.body.decode("utf-8")
    assert "Money Intelligence" in body
    assert "Where money is moving" in body
    assert "Best current opportunities" in body
    assert "Causal chains" in body
    assert "Prediction scorecard" in body
    assert "Research frontier" in body
    assert "These are not signal-engine outputs" in body
    assert "It does not authorize real-money execution" in body


def test_spec_declares_hard_signal_separation():
    spec = (Path(__file__).parents[1] / "MONEY_INTELLIGENCE_SPEC.md").read_text()
    assert "Hard separation from the signal system" in spec
    assert "write to production signal tables" in spec
    assert "Immutable prediction ledger" in spec
    assert "Prediction must beat explanation" in spec
    assert "authorize or execute real-money trades" in spec
