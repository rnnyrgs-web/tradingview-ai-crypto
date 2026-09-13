import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from agents.autonomous_cloud_runner import default_state, load_config
from orchestration.shared_budget import (
    combined_spend_since,
    fleet_budget_gate,
    load_sibling_states,
    pacing_snapshot,
)

NOW = datetime(2026, 9, 13, 12, 0, tzinfo=timezone.utc)
CLAUDE_CONFIG_PATH = Path("orchestration/autonomous_specialist_runner_claude.json")


def _cfg():
    return load_config(CLAUDE_CONFIG_PATH)


def _state_with_spend(amount: float, when: str) -> dict:
    state = default_state()
    state["runs"].append({"finished_at": when, "actual_cost_usd": amount})
    return state


def test_combined_spend_since_sums_across_states():
    a = _state_with_spend(1.5, "2026-09-05T00:00:00Z")
    b = _state_with_spend(2.5, "2026-09-06T00:00:00Z")
    total = combined_spend_since([a, b], datetime(2026, 9, 1, tzinfo=timezone.utc))
    assert total == pytest.approx(4.0)


def test_load_sibling_states_skips_missing_files(tmp_path):
    existing = tmp_path / "exists.json"
    existing.write_text(json.dumps(default_state()), encoding="utf-8")
    missing = tmp_path / "does_not_exist.json"
    states = load_sibling_states([existing, missing])
    assert len(states) == 1


def test_load_sibling_states_fails_closed_on_malformed_existing_file(tmp_path):
    malformed = tmp_path / "bad.json"
    malformed.write_text("not-json", encoding="utf-8")
    with pytest.raises(Exception):
        load_sibling_states([malformed])


def test_fleet_gate_passes_with_no_prior_spend_anywhere():
    ok, reason, reserve = fleet_budget_gate(_cfg(), default_state(), [], "signal-accuracy", NOW)
    assert ok is True
    assert reason == "OK"
    assert reserve > 0


def test_fleet_gate_fails_when_sibling_spend_alone_would_exceed_shared_ceiling():
    own = default_state()
    sibling_near_ceiling = _state_with_spend(29.9, "2026-09-01T00:00:00Z")
    ok, reason, _ = fleet_budget_gate(_cfg(), own, [sibling_near_ceiling], "signal-accuracy", NOW)
    assert ok is False
    assert reason == "FLEET_MONTHLY_WOULD_EXCEED_PROJECT_CEILING"


def test_fleet_gate_ignores_spend_from_a_prior_month():
    own = default_state()
    sibling = _state_with_spend(29.9, "2026-08-15T00:00:00Z")
    ok, reason, _ = fleet_budget_gate(_cfg(), own, [sibling], "signal-accuracy", NOW)
    assert ok is True
    assert reason == "OK"


def test_pacing_target_advances_through_month_and_carry_forward_is_available():
    cfg = _cfg()
    early = datetime(2026, 9, 5, 0, 0, tzinfo=timezone.utc)
    later = datetime(2026, 9, 15, 0, 0, tzinfo=timezone.utc)
    early_snapshot = pacing_snapshot(cfg, default_state(), [], early)
    later_snapshot = pacing_snapshot(cfg, default_state(), [], later)
    assert later_snapshot["target_to_now_usd"] > early_snapshot["target_to_now_usd"]
    assert later_snapshot["paced_limit_usd"] > early_snapshot["paced_limit_usd"]


def test_saved_budget_allows_two_to_three_dollar_important_day():
    cfg = _cfg()
    # By Sep 13 noon the paced target is ~12.5. With only $9 spent previously,
    # there is enough carried-forward allowance for a materially larger day.
    own = _state_with_spend(9.0, "2026-09-10T00:00:00Z")
    ok, reason, reserve = fleet_budget_gate(cfg, own, [], "signal-accuracy", NOW)
    assert reserve < 3.0
    assert ok is True
    assert reason == "OK"


def test_early_month_overspending_is_throttled_before_monthly_ceiling():
    cfg = _cfg()
    now = datetime(2026, 9, 3, 12, 0, tzinfo=timezone.utc)
    own = _state_with_spend(5.0, "2026-09-03T08:00:00Z")
    ok, reason, _ = fleet_budget_gate(cfg, own, [], "signal-accuracy", now)
    assert ok is False
    assert reason in {"FLEET_DAILY_BURST_CAP", "FLEET_PACING_AHEAD_OF_SCHEDULE"}


def test_daily_fleet_burst_cap_applies_across_multiple_engines():
    cfg = _cfg()
    own = _state_with_spend(1.4, "2026-09-13T08:00:00Z")
    sibling = _state_with_spend(1.4, "2026-09-13T09:00:00Z")
    ok, reason, reserve = fleet_budget_gate(cfg, own, [sibling], "signal-accuracy", NOW)
    assert 2.8 + reserve > 3.0
    assert ok is False
    assert reason == "FLEET_DAILY_BURST_CAP"


def test_pacing_throttles_after_a_burst_until_calendar_catches_up():
    cfg = _cfg()
    now = datetime(2026, 9, 5, 12, 0, tzinfo=timezone.utc)
    # Target is ~4.5 by this point; target + $2 burst allowance is ~6.5.
    own = _state_with_spend(6.4, "2026-09-04T12:00:00Z")
    ok, reason, _ = fleet_budget_gate(cfg, own, [], "signal-accuracy", now)
    assert ok is False
    assert reason == "FLEET_PACING_AHEAD_OF_SCHEDULE"


def test_projected_month_end_metric_warns_when_current_velocity_is_too_high():
    cfg = _cfg()
    now = datetime(2026, 9, 5, 0, 0, tzinfo=timezone.utc)
    own = _state_with_spend(8.0, "2026-09-04T23:00:00Z")
    snapshot = pacing_snapshot(cfg, own, [], now)
    assert snapshot["projected_month_end_usd"] > snapshot["ceiling_usd"]


def test_end_of_month_can_use_remaining_budget_without_exceeding_hard_ceiling():
    cfg = _cfg()
    now = datetime(2026, 9, 30, 20, 0, tzinfo=timezone.utc)
    own = _state_with_spend(28.5, "2026-09-29T12:00:00Z")
    ok, reason, reserve = fleet_budget_gate(cfg, own, [], "signal-accuracy", now)
    if 28.5 + reserve <= 30.0:
        assert ok is True
        assert reason == "OK"
    else:
        assert ok is False
        assert reason == "FLEET_MONTHLY_WOULD_EXCEED_PROJECT_CEILING"


def test_fleet_gate_sums_own_state_plus_multiple_siblings():
    own = _state_with_spend(10.0, "2026-09-02T00:00:00Z")
    sib1 = _state_with_spend(10.0, "2026-09-03T00:00:00Z")
    sib2 = _state_with_spend(9.5, "2026-09-04T00:00:00Z")
    ok, reason, reserve = fleet_budget_gate(_cfg(), own, [sib1, sib2], "signal-accuracy", NOW)
    assert 29.5 + reserve <= 30.0
    # Even if the hard ceiling still has room, pacing may intentionally defer
    # the request because this amount should not have been spent by Sep 13.
    assert ok is False
    assert reason == "FLEET_PACING_AHEAD_OF_SCHEDULE"
    sib2["runs"].append({"finished_at": "2026-09-04T00:00:01Z", "actual_cost_usd": 0.5})
    ok, reason, _ = fleet_budget_gate(_cfg(), own, [sib1, sib2], "signal-accuracy", NOW)
    assert ok is False
    assert reason == "FLEET_MONTHLY_WOULD_EXCEED_PROJECT_CEILING"
