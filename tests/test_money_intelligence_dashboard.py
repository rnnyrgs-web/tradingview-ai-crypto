import json
from pathlib import Path

import money_intelligence_dashboard as mid


def test_dashboard_state_is_fail_closed_until_evidence_exists():
    state = json.loads((Path(__file__).parents[1] / "money_intelligence" / "dashboard_state.json").read_text())
    assert isinstance(state.get("status"), str) and state["status"]
    assert isinstance(state.get("opportunities"), list)
    scorecard = state["prediction_scorecard"]
    assert isinstance(scorecard["resolved"], int) and scorecard["resolved"] >= 0
    if scorecard["resolved"] == 0:
        assert scorecard["directional_hit_rate"] is None

    # The original bootstrap state must remain explicitly fail-closed, but this
    # regression test must not freeze the live research state at bootstrap forever.
    if state["status"] == "BOOTSTRAP_LEARNING":
        assert state["opportunities"] == []


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


def test_spec_declares_hard_signal_separation():
    spec = (Path(__file__).parents[1] / "MONEY_INTELLIGENCE_SPEC.md").read_text()
    assert "Hard separation from the signal system" in spec
    assert "write to production signal tables" in spec
    assert "Immutable prediction ledger" in spec
    assert "Prediction must beat explanation" in spec
