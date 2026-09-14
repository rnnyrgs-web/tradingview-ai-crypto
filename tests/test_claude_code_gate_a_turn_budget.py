import json
from pathlib import Path


def test_gate_a_turn_budget_matches_bounded_completion_plan():
    config = json.loads(Path("orchestration/autonomous_specialist_runner_claude_code.json").read_text())
    role = config["roles"]["testing-security"]
    mission = role["mission"]
    assert role["model"] == "claude-haiku-4-5"
    assert role["max_turns"] == 10
    assert "ISSUE #349" in mission
    assert "turns 9-10 stop" in mission
    assert config["budget"]["project_monthly_ceiling_usd"] == 30.0
    assert config["budget"]["runner_daily_api_budget_usd"] == 1.0
    assert config["policy"]["automatic_merge"] is False
    assert config["policy"]["trade_authority"] is False
    assert config["policy"]["broker_connected"] is False
