import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from agents.autonomous_cloud_runner import default_state, load_config
from orchestration.shared_budget import combined_spend_since, fleet_budget_gate, load_sibling_states

NOW = datetime(2026, 9, 13, 12, 0, tzinfo=timezone.utc)
CLAUDE_CONFIG_PATH = Path("orchestration/autonomous_specialist_runner_claude.json")


def _cfg():
    return load_config(CLAUDE_CONFIG_PATH)


def test_combined_spend_since_sums_across_states():
    a = default_state()
    a["runs"].append({"finished_at": "2026-09-05T00:00:00Z", "actual_cost_usd": 1.5})
    b = default_state()
    b["runs"].append({"finished_at": "2026-09-06T00:00:00Z", "actual_cost_usd": 2.5})
    total = combined_spend_since([a, b], datetime(2026, 9, 1, tzinfo=timezone.utc))
    assert total == pytest.approx(4.0)


def test_load_sibling_states_skips_missing_files(tmp_path):
    existing = tmp_path / "exists.json"
    existing.write_text(json.dumps(default_state()), encoding="utf-8")
    missing = tmp_path / "does_not_exist.json"
    states = load_sibling_states([existing, missing])
    assert len(states) == 1


def test_fleet_gate_passes_with_no_prior_spend_anywhere():
    ok, reason, reserve = fleet_budget_gate(_cfg(), default_state(), [], "signal-accuracy", NOW)
    assert ok is True
    assert reason == "OK"
    assert reserve > 0


def test_fleet_gate_fails_when_sibling_spend_alone_would_exceed_shared_ceiling():
    own = default_state()
    sibling_near_ceiling = default_state()
    sibling_near_ceiling["runs"].append({"finished_at": "2026-09-01T00:00:00Z", "actual_cost_usd": 29.9})
    ok, reason, _ = fleet_budget_gate(_cfg(), own, [sibling_near_ceiling], "signal-accuracy", NOW)
    assert ok is False
    assert reason == "FLEET_MONTHLY_WOULD_EXCEED_PROJECT_CEILING"


def test_fleet_gate_ignores_spend_from_a_prior_month():
    own = default_state()
    sibling = default_state()
    sibling["runs"].append({"finished_at": "2026-08-15T00:00:00Z", "actual_cost_usd": 29.9})
    ok, reason, _ = fleet_budget_gate(_cfg(), own, [sibling], "signal-accuracy", NOW)
    assert ok is True
    assert reason == "OK"


def test_fleet_gate_sums_own_state_plus_multiple_siblings():
    own = default_state()
    own["runs"].append({"finished_at": "2026-09-02T00:00:00Z", "actual_cost_usd": 10.0})
    sib1 = default_state()
    sib1["runs"].append({"finished_at": "2026-09-03T00:00:00Z", "actual_cost_usd": 10.0})
    sib2 = default_state()
    sib2["runs"].append({"finished_at": "2026-09-04T00:00:00Z", "actual_cost_usd": 9.5})
    ok, reason, reserve = fleet_budget_gate(_cfg(), own, [sib1, sib2], "signal-accuracy", NOW)
    # 10 + 10 + 9.5 = 29.5, plus this role's reserve (~0.39) would push
    # combined spend to ~29.89, still under the 30.0 ceiling.
    assert ok is True
    sib2["runs"].append({"finished_at": "2026-09-04T00:00:01Z", "actual_cost_usd": 0.5})
    ok, reason, _ = fleet_budget_gate(_cfg(), own, [sib1, sib2], "signal-accuracy", NOW)
    assert ok is False
    assert reason == "FLEET_MONTHLY_WOULD_EXCEED_PROJECT_CEILING"
