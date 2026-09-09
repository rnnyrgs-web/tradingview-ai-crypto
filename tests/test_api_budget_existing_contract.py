from agents.autonomous_cloud_runner import load_config, reserved_cost_usd


def test_retry_reserve_contract_remains_within_project_ceiling():
    config = load_config()
    budget = config["budget"]
    retry_reserve = reserved_cost_usd(config, "data-market") * budget["provider_retry_safety_multiplier"]
    assert budget["provider_retry_safety_multiplier"] == 3.0
    assert (
        budget["baseline_infrastructure_reserve_usd"]
        + budget["runner_monthly_api_budget_usd"]
        + budget["pause_buffer_usd"]
        <= budget["project_monthly_ceiling_usd"]
    )
    assert retry_reserve < budget["runner_daily_api_budget_usd"]
