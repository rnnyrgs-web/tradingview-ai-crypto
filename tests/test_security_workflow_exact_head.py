from pathlib import Path


def test_security_workflow_binds_pull_request_runs_to_exact_head_sha():
    workflow = (Path(__file__).resolve().parents[1] / ".github" / "workflows" / "security.yml").read_text(
        encoding="utf-8"
    )

    assert "EXACT_HEAD_PR_CHECKOUT_V1" in workflow
    assert "github.event.pull_request.head.sha" in workflow
    assert "Verify checked-out commit identity" in workflow
    assert 'ACTUAL_SHA="$(git rev-parse HEAD)"' in workflow
    assert 'if [ "$ACTUAL_SHA" != "$EXPECTED_SHA" ]; then' in workflow


def test_security_workflow_preserves_non_pr_event_sha_fallback():
    workflow = (Path(__file__).resolve().parents[1] / ".github" / "workflows" / "security.yml").read_text(
        encoding="utf-8"
    )

    exact_ref_expression = "github.event_name == 'pull_request' && github.event.pull_request.head.sha || github.sha"
    assert workflow.count(exact_ref_expression) >= 2
