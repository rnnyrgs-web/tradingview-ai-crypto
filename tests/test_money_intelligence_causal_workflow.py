from pathlib import Path


WORKFLOW = Path(".github/workflows/money-intelligence-causal-runtime-acceptance.yml")


def test_causal_acceptance_runs_automatically_after_relevant_main_changes():
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "workflow_dispatch:" in workflow
    assert "push:" in workflow
    assert "branches: [main]" in workflow
    for path in (
        ".github/workflows/money-intelligence-causal-runtime-acceptance.yml",
        "Dockerfile",
        "app.py",
        "db.py",
        "money_intelligence_causal_acceptance.py",
        "money_intelligence_causal_memory.py",
        "money_intelligence_causal_runtime.py",
        "money_intelligence_causal_supabase.py",
        "research_director.py",
        "research_director_runtime.py",
        "orchestration/rejected_fingerprints.json",
        "supabase/migrations/**",
    ):
        assert f"- {path}" in workflow


def test_causal_acceptance_workflow_verifies_exact_sha_transitions_and_safety():
    workflow = WORKFLOW.read_text(encoding="utf-8")

    for assertion in (
        ".deployed_sha == $sha",
        ".persistence.replay_idempotent == true",
        ".persistence.restart_equal == true",
        ".transitions.support_stage.mission_count == 4",
        ".transitions.contradiction_removed == true",
        ".transitions.decay_removed == true",
        ".transitions.current_acceptance_mission_count == 0",
        ".safety.trade_authority == false",
        ".safety.promotion_authority == false",
        ".safety.oos_opening_authority == false",
        ".safety.broker_connected == false",
    ):
        assert assertion in workflow


def test_causal_acceptance_failure_diagnostics_are_sanitized():
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert 'last_http_status=$status' in workflow
    assert "response_not_json" in workflow
    assert 'cat "$response"' not in workflow
    assert "detail: .detail?" not in workflow
