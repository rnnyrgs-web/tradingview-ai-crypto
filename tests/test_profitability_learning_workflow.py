from pathlib import Path


WORKFLOW = Path(".github/workflows/profitability-learning-runtime-acceptance.yml")


def test_runtime_acceptance_runs_automatically_after_relevant_main_changes():
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "workflow_dispatch:" in workflow
    assert "push:" in workflow
    assert "branches: [main]" in workflow
    assert "paths:" in workflow
    for path in (
        ".github/workflows/profitability-learning-runtime-acceptance.yml",
        "Dockerfile",
        "requirements.txt",
        "app.py",
        "config.py",
        "btc_leadlag_selection.py",
        "volatility_breakout_selection.py",
        "db.py",
        "profitability_learning/**",
        "orchestration/evidence/disc_btc_leadlag_001_20260919.json.gz",
        "research_artifact.py",
        "research_heavy_experiment_scheduler.py",
        "signal_development.py",
        "supabase/migrations/**",
    ):
        assert f"- {path}" in workflow


def test_runtime_acceptance_failure_diagnostics_are_sanitized():
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert 'last_http_status=$status' in workflow
    assert "response_not_json" in workflow
    assert 'cat "$response"' not in workflow
