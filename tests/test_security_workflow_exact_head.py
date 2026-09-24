from pathlib import Path

import yaml


WORKFLOW_PATH = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "security.yml"


def _verify_steps():
    workflow = yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))
    steps = workflow["jobs"]["verify"]["steps"]
    return {step.get("name"): step for step in steps if isinstance(step, dict) and step.get("name")}


def test_security_workflow_binds_pull_request_runs_to_exact_head_sha():
    text = WORKFLOW_PATH.read_text(encoding="utf-8")
    steps = _verify_steps()

    checkout = steps["Checkout exact pull-request head"]
    verify = steps["Verify pull-request checkout identity"]

    assert "EXACT_HEAD_PR_CHECKOUT_V2" in text
    assert checkout["if"] == "github.event_name == 'pull_request'"
    assert checkout["uses"] == "actions/checkout@v4"
    assert checkout["with"]["ref"] == "${{ github.event.pull_request.head.sha }}"
    assert verify["if"] == "github.event_name == 'pull_request'"
    assert verify["env"]["EXPECTED_SHA"] == "${{ github.event.pull_request.head.sha }}"
    assert 'ACTUAL_SHA="$(git rev-parse HEAD)"' in verify["run"]
    assert 'test "$ACTUAL_SHA" = "$EXPECTED_SHA"' in verify["run"]


def test_security_workflow_binds_non_pr_runs_to_triggering_sha_without_boolean_fallback():
    text = WORKFLOW_PATH.read_text(encoding="utf-8")
    steps = _verify_steps()

    checkout = steps["Checkout exact non-PR triggering commit"]
    verify = steps["Verify non-PR checkout identity"]

    assert checkout["if"] == "github.event_name != 'pull_request'"
    assert checkout["uses"] == "actions/checkout@v4"
    assert checkout["with"]["ref"] == "${{ github.sha }}"
    assert verify["if"] == "github.event_name != 'pull_request'"
    assert verify["env"]["EXPECTED_SHA"] == "${{ github.sha }}"
    assert 'ACTUAL_SHA="$(git rev-parse HEAD)"' in verify["run"]
    assert 'test "$ACTUAL_SHA" = "$EXPECTED_SHA"' in verify["run"]
    assert "&& github.event.pull_request.head.sha || github.sha" not in text


def test_security_workflow_has_no_unscoped_checkout_step():
    workflow = yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))
    checkout_steps = [
        step
        for step in workflow["jobs"]["verify"]["steps"]
        if isinstance(step, dict) and step.get("uses") == "actions/checkout@v4"
    ]

    assert len(checkout_steps) == 2
    assert all(step.get("if") in {"github.event_name == 'pull_request'", "github.event_name != 'pull_request'"} for step in checkout_steps)
    assert all(step.get("with", {}).get("ref") for step in checkout_steps)
