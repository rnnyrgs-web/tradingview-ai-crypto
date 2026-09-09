import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_cloud_specialist_checks_hourly_but_model_cooldown_stays_12h():
    workflow = (ROOT / ".github/workflows/autonomous_cloud_specialist.yml").read_text(encoding="utf-8")
    config = json.loads((ROOT / "orchestration/autonomous_specialist_runner.json").read_text(encoding="utf-8"))

    assert 'cron: "41 * * * *"' in workflow
    assert config["policy"]["schedule_check_hours"] == 1
    assert config["policy"]["successful_run_cooldown_hours"] == 12
    assert config["policy"]["max_concurrent_agent_runs"] == 1
    assert config["policy"]["max_agent_runs_per_invocation"] == 1
    assert config["budget"]["runner_daily_api_budget_usd"] == 1.0
    assert config["budget"]["project_monthly_ceiling_usd"] == 30.0
    assert config["policy"]["automatic_merge"] is False
    assert config["policy"]["trade_authority"] is False


def test_hourly_review_asks_add_remove_question_without_relaxing_budget_or_authority():
    config = json.loads((ROOT / "orchestration/autonomous_specialist_runner.json").read_text(encoding="utf-8"))
    question = config["policy"]["hourly_self_improvement_question"]
    policy = config["policy"]["hourly_self_improvement_policy"]
    mission = config["roles"]["data-market"]["mission"]
    assert "added" in question
    assert "removed" in question
    assert "after-cost" in question
    assert "12-hour" in policy
    assert "$1/day" in policy
    assert "what should be added, removed" in mission.lower()
    assert config["policy"]["successful_run_cooldown_hours"] == 12
    assert config["budget"]["runner_daily_api_budget_usd"] == 1.0
    assert config["policy"]["automatic_merge"] is False
    assert config["policy"]["trade_authority"] is False
    assert config["policy"]["broker_connected"] is False


def test_accuracy_profitability_roadmap_preserves_scientific_and_cost_limits():
    roadmap = json.loads((ROOT / "orchestration/accuracy_profitability_roadmap.json").read_text(encoding="utf-8"))
    constraints = roadmap["constraints"]
    ids = {item["id"] for item in roadmap["priority_programs"]}
    assert {"META_WAIT_ECONOMIC", "REGIME_STRATEGY_ROUTER", "CROSS_SECTIONAL_RESIDUAL", "ECONOMIC_CALIBRATION", "MICROSTRUCTURE_VETO", "ENSEMBLE_DIVERSITY"} <= ids
    assert constraints["monthly_infrastructure_ceiling_usd"] == 30
    assert constraints["logical_specialist_target"] == 256
    assert constraints["increase_logical_specialists_without_evidence"] is False
    assert constraints["heavy_experiment_concurrency"] == 1
    assert constraints["blind_indicator_parameter_mining"] is False
    assert constraints["trade_authority"] is False
    assert constraints["promotion_authority"] is False
    assert constraints["broker_connected"] is False


def test_review_only_lead_is_triggered_after_cloud_specialist_completion():
    workflow = (ROOT / ".github/workflows/autonomous_lead.yml").read_text(encoding="utf-8")
    assert "- Cost-Bounded Autonomous Cloud Specialist" in workflow
    assert 'AUTONOMOUS_MERGE_ENABLED: "false"' in workflow
    assert "contents: read" in workflow
