import re
from pathlib import Path

from agents.autonomous_orchestrator import bounded_tool_steps, extract_json, normalize_relpath, path_allowed
from agents.autonomous_worker import _completion_text


ROOT = Path(__file__).resolve().parents[1]


def test_role_path_allowlists_are_fail_closed():
    assert path_allowed("quant-research", "strategy_families.py")
    assert path_allowed("data-market", "market_data.py")
    assert path_allowed("production-risk", "safety.py")
    assert not path_allowed("quant-research", "market_data.py")
    assert not path_allowed("data-market", "engine.py")


def test_protected_paths_are_never_specialist_writable():
    for role in (
        "quant-research",
        "data-market",
        "strategy-registry",
        "production-risk",
        "testing-security",
    ):
        assert not path_allowed(role, "AI_STATE.md")
        assert not path_allowed(role, "agents/autonomous_orchestrator.py")
        assert not path_allowed(role, "agents/roles.json")
        assert not path_allowed(role, ".github/workflows/autonomous_lead.yml")
        assert not path_allowed(role, ".github/workflows/security.yml")
        assert not path_allowed(role, "requirements.txt")
        assert not path_allowed(role, "Dockerfile")


def test_testing_security_larger_budget_is_role_scoped_and_absolutely_capped():
    workflow = (ROOT / ".github/workflows/autonomous_agents.yml").read_text(encoding="utf-8")
    budget_lines = [line.strip() for line in workflow.splitlines() if "AGENT_MAX_STEPS:" in line]

    assert len(budget_lines) == 1
    assert re.fullmatch(
        r"AGENT_MAX_STEPS:\s*\$\{\{\s*matrix\.role\s*==\s*'testing-security'\s*&&\s*'32'\s*\|\|\s*'20'\s*\}\}",
        budget_lines[0],
    )
    assert bounded_tool_steps("32") == 32
    assert bounded_tool_steps("33") == 32
    assert bounded_tool_steps(str(10**100)) == 32


def test_path_traversal_is_rejected():
    assert not path_allowed("testing-security", "../AI_STATE.md")
    assert not path_allowed("testing-security", "/tmp/test.py")


def test_normalize_relpath_rejects_empty_and_parent_paths():
    for unsafe in ("", "../x", "a/../../x", "/etc/passwd"):
        try:
            normalize_relpath(unsafe)
        except ValueError:
            pass
        else:
            raise AssertionError(f"unsafe path accepted: {unsafe}")


def test_extract_json_accepts_plain_and_fenced_json():
    assert extract_json('{"approve": true}') == {"approve": True}
    assert extract_json('```json\n{"approve": false}\n```') == {"approve": False}


def test_worker_completion_marker_is_required():
    payload = {"output_text": "done"}
    try:
        _completion_text(payload)
    except RuntimeError:
        pass
    else:
        raise AssertionError("worker accepted completion without CHANGE_STATUS")


def test_worker_accepts_explicit_ready_or_no_change_markers():
    assert "READY_FOR_PR" in _completion_text({"output_text": "CHANGE_STATUS: READY_FOR_PR"})
    assert "NO_CHANGE" in _completion_text({"output_text": "CHANGE_STATUS: NO_CHANGE"})


def test_tool_step_budget_is_always_hard_bounded():
    assert bounded_tool_steps(None) == 12
    assert bounded_tool_steps("20") == 20
    assert bounded_tool_steps("32") == 32
    assert bounded_tool_steps("999") == 32
    assert bounded_tool_steps("0") == 1
    assert bounded_tool_steps("invalid") == 12
