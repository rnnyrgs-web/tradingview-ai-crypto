from pathlib import Path


WORKFLOW = Path(".github/workflows/autonomous_claude_code_specialist.yml")


def _text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_changed_worktree_is_inspected_even_when_agent_exhausts_turns():
    text = _text()
    expected = (
        "- id: changes\n"
        "        name: Determine whether the working tree actually changed\n"
        "        if: steps.credential_gate.outputs.execute == 'true'\n"
    )
    assert expected in text
    assert (
        "if: steps.credential_gate.outputs.execute == 'true' && "
        "steps.agent.outcome == 'success'"
    ) not in text


def test_agent_failure_only_fails_when_no_publishable_change_was_recovered():
    text = _text()
    assert "name: Fail workflow after unrecovered bounded agent failure" in text
    assert (
        "steps.agent.outcome == 'failure' && "
        "steps.changes.outputs.status != 'READY_FOR_PR'"
    ) in text
