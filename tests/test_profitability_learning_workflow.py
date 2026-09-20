from pathlib import Path


WORKFLOW = Path(".github/workflows/profitability-learning-runtime-acceptance.yml")
DOCKERFILE = Path("Dockerfile")


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
        "orchestration/rejected_fingerprints.json",
        "orchestration/signal_development_objective.json",
        "orchestration/trusted_executor_manifest.json",
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
    assert "detail: .detail?" not in workflow
    assert "evidence_boundaries: .evidence_boundaries?" not in workflow
    assert "safety: .safety?" not in workflow
    for field in (
        "untouched_oos_opened: .evidence_boundaries.untouched_oos_opened?",
        "genuine_forward_opened: .evidence_boundaries.genuine_forward_opened?",
        "trade_authority: .safety.trade_authority?",
        "promotion_authority: .safety.promotion_authority?",
        "broker_connected: .safety.broker_connected?",
    ):
        assert field in workflow


def test_runtime_acceptance_dependencies_are_packaged_in_web_image():
    dockerfile = DOCKERFILE.read_text(encoding="utf-8")

    for instruction in (
        "COPY profitability_learning/ profitability_learning/",
        "COPY orchestration/evidence/disc_btc_leadlag_001_20260919.json.gz orchestration/evidence/",
        "COPY orchestration/rejected_fingerprints.py orchestration/",
        "COPY orchestration/rejected_fingerprints.json orchestration/",
        "COPY orchestration/signal_development_objective.json orchestration/",
        "COPY orchestration/trusted_executor_manifest.json orchestration/",
    ):
        assert instruction in dockerfile
