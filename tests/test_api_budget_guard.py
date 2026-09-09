from datetime import datetime, timezone
import json
from pathlib import Path

from api_budget_guard import check_budget

NOW = datetime(2026, 9, 9, 4, 0, tzinfo=timezone.utc)


def _state(tmp_path: Path, spend: float) -> Path:
    path = tmp_path / "state.json"
    payload = {
        "version": 1,
        "runs": [{"finished_at": "2026-09-09T02:00:00Z", "actual_cost_usd": spend}],
        "active_task": None,
        "next_eligible_at": None,
        "paused_reason": None,
        "last_seen_main_sha": None,
        "task_failures": {},
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_guard_applies_three_x_reserve_before_daily_limit(tmp_path):
    ok, reason, metrics = check_budget(_state(tmp_path, 0.90), "data-market", NOW)
    assert ok is False
    assert reason == "DAILY_API_BUDGET"
    assert metrics["retry_safety_multiplier"] == 3.0
    assert metrics["protected_reserved_call_usd"] > metrics["raw_reserved_call_usd"]


def test_guard_allows_high_value_call_when_protected_headroom_exists(tmp_path):
    ok, reason, _ = check_budget(_state(tmp_path, 0.50), "data-market", NOW)
    assert ok is True
    assert reason == "OK"
