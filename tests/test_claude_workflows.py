from pathlib import Path

import yaml


def _read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def test_claude_research_workflow_is_valid_yaml_and_cost_bounded():
    text = _read(".github/workflows/autonomous_claude_specialist.yml")
    parsed = yaml.safe_load(text)
    assert parsed["jobs"]["specialist-cycle"]["timeout-minutes"] == 35
    assert 'cron: "13 * * * *"' in text
    assert "ANTHROPIC_API_KEY" in text
    assert "MISSING_ANTHROPIC_API_KEY" in text
    assert "orchestration.shared_budget" in text
    assert "claude_specialist_runner.py" in text
    assert "gh pr merge" not in text
    assert "enable-auto-merge" not in text
    assert "git push origin main" not in text
    assert "place_order" not in text
    assert "trade_authority" not in text
    assert "gh workflow run security.yml" in text


def test_claude_code_workflow_is_valid_yaml_and_cost_bounded():
    text = _read(".github/workflows/autonomous_claude_code_specialist.yml")
    parsed = yaml.safe_load(text)
    assert parsed["jobs"]["specialist-cycle"]["timeout-minutes"] == 35
    assert 'cron: "26 * * * *"' in text
    assert "ANTHROPIC_API_KEY" in text
    assert "MISSING_ANTHROPIC_API_KEY" in text
    assert "orchestration.shared_budget" in text
    assert "claude_code_specialist_runner.py" in text
    assert "anthropics/claude-code-action@v1" in text
    assert "gh pr merge" not in text
    assert "enable-auto-merge" not in text
    assert "git push origin main" not in text
    assert "place_order" not in text
    assert "trade_authority" not in text
    assert "gh workflow run security.yml" in text


def test_claude_code_action_is_denied_git_and_general_shell_access():
    """The action must not itself be able to commit/push/open a PR --
    publication stays under this workflow's own allowlist-checked control,
    enforced here by restricting --allowedTools to Read/Write/Edit and a
    pytest-only Bash pattern, never a bare unrestricted Bash grant."""
    text = _read(".github/workflows/autonomous_claude_code_specialist.yml")
    assert "Bash(pytest*)" in text
    assert "claude_args" in text
    claude_args_line = next(line for line in text.splitlines() if "claude_args:" in line)
    assert "Bash(pytest*)" in claude_args_line
    assert '"Bash"' not in claude_args_line
    assert ",Bash," not in claude_args_line


def test_claude_workflows_run_the_allowlist_rejection_step_before_publishing():
    for path in (
        ".github/workflows/autonomous_claude_specialist.yml",
        ".github/workflows/autonomous_claude_code_specialist.yml",
    ):
        text = _read(path)
        assert "Reject any actual change outside the role allowlist" in text
        assert "path_allowed" in text


def test_claude_workflows_reserve_against_the_shared_fleet_ledger_not_a_stale_local_snapshot():
    """Regression for BUG_REGRESSION_LEDGER.md FLEET-BUDGET-RACE-001: each
    workflow's budget check must use the race-free `reserve` subcommand
    (live, lock-protected reads of sibling state) rather than best-effort
    local sibling files fetched once at job start."""
    for path, expected_siblings in (
        (".github/workflows/autonomous_claude_specialist.yml", ["runner_state.json", "runner_state_claude_code.json"]),
        (".github/workflows/autonomous_claude_code_specialist.yml", ["runner_state.json", "runner_state_claude.json"]),
    ):
        text = _read(path)
        assert "orchestration.shared_budget reserve" in text
        assert "--sibling-state-path" in text
        for sibling in expected_siblings:
            assert sibling in text
        # The old best-effort local prefetch pattern must be gone.
        assert "/tmp/sibling_" not in text
        assert "fetch_or_skip" not in text


def test_claude_workflows_clear_reservation_after_run_concludes():
    for path in (
        ".github/workflows/autonomous_claude_specialist.yml",
        ".github/workflows/autonomous_claude_code_specialist.yml",
    ):
        text = _read(path)
        assert "orchestration.shared_budget clear-reservation" in text
        assert "Clear fleet budget reservation now that this run has concluded" in text
        assert "steps.fleet_budget.outputs.reservation_id" in text


def test_openai_workflow_also_gained_the_race_free_fleet_reservation():
    text = _read(".github/workflows/autonomous_cloud_specialist.yml")
    assert "orchestration.shared_budget reserve" in text
    assert "orchestration.shared_budget clear-reservation" in text
    assert "--sibling-state-path" in text
    assert "runner_state_claude.json" in text
    assert "runner_state_claude_code.json" in text
    assert "/tmp/sibling_" not in text
    assert "fetch_or_skip" not in text


def test_lead_workflow_requires_claude_adversarial_approval():
    text = _read(".github/workflows/autonomous_lead.yml")
    assert "claude-adversarial" in text
    assert "Require all three independent reviewers to approve" in text
    assert "ANTHROPIC_API_KEY" in text
    assert "Fail closed if Claude adversarial review could not run" in text
    # The protected-path guard must use the canonical shared checker, not a
    # separately maintained regex.
    assert "orchestration.protected_paths" in text
    assert "grep -Eq" not in text
