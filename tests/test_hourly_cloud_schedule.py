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


def test_review_only_lead_is_triggered_after_cloud_specialist_completion():
    workflow = (ROOT / ".github/workflows/autonomous_lead.yml").read_text(encoding="utf-8")
    assert "- Cost-Bounded Autonomous Cloud Specialist" in workflow
    assert 'AUTONOMOUS_MERGE_ENABLED: "false"' in workflow
    assert "contents: read" in workflow
