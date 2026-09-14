import json
from pathlib import Path

import money_intelligence_dashboard as mid


def test_bootstrap_state_is_explicitly_fail_closed():
    state = json.loads((Path(__file__).parents[1] / "money_intelligence" / "dashboard_state.json").read_text())
    assert state["status"] == "BOOTSTRAP_LEARNING"
    assert state["opportunities"] == []
    assert state["prediction_scorecard"]["resolved"] == 0
    assert state["prediction_scorecard"]["directional_hit_rate"] is None


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
