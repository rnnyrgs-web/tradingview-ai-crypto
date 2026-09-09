from agents.autonomous_cloud_runner import load_config, reserved_cost_usd


def test_api_budget_targets_one_dollar_daily_and_stays_below_monthly_hard_cap():
    config = load_config()
    budget = config["budget"]
    assert budget["project_monthly_ceiling_usd"] == 30.0
    assert budget["runner_daily_api_budget_usd"] == 1.0
    assert budget["runner_monthly_api_budget_usd"] == 29.0
    assert budget["pause_buffer_usd"] == 1.0
    assert budget["runner_monthly_api_budget_usd"] + budget["pause_buffer_usd"] <= budget["project_monthly_ceiling_usd"]


def test_default_api_work_uses_luna_and_keeps_sol_disabled():
    config = load_config()
    assert config["roles"]["data-market"]["model"] == "gpt-5.6-luna"
    assert config["models"]["gpt-5.6-luna"]["enabled"] is True
    assert config["models"]["gpt-5.6-sol"]["enabled"] is False
    assert reserved_cost_usd(config, "data-market") < config["budget"]["runner_daily_api_budget_usd"]


def test_budget_mission_prioritizes_signal_quality_and_avoids_waste():
    mission = load_config()["roles"]["data-market"]["mission"].lower()
    assert "highest expected signal-quality" in mission
    assert "deterministic python" in mission
    assert "do not spend api budget merely to stay busy" in mission
    assert "insufficienthistory" in mission
