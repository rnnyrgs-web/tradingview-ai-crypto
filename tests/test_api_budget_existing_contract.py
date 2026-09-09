from agents.autonomous_cloud_runner import load_config


def test_existing_retry_reserve_contract_remains_within_project_ceiling():
    config = load_config()
    budget = config["budget"]
    assert (
        budget["baseline_infrastructure_reserve_usd"]
        + budget["runner_monthly_api_budget_usd"] * budget["provider_retry_safety_multiplier"]
        + budget["pause_buffer_usd"]
        <= budget["project_monthly_ceiling_usd"]
    )
