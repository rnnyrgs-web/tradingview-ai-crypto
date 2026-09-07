from agents.autonomous_orchestrator import (
    MAX_ACTIVE_TASKS_PER_CYCLE,
    _retry_delay,
    bounded_tool_steps,
    extract_json,
    load_roles,
    normalize_relpath,
    path_allowed,
    validate_plan,
)
from agents.autonomous_worker import _completion_text


def test_15_agent_architecture_has_14_specialists_plus_lead():
    roles = load_roles()
    assert len(roles) == 14
    assert "quant-trend" in roles
    assert "quant-mean-reversion" in roles
    assert "quant-breakout-volatility" in roles
    assert "quant-cross-asset" in roles
    assert "data-market" in roles
    assert "data-integrity" in roles
    assert "market-microstructure" in roles
    assert "onchain-tokenomics" in roles
    assert "news-macro" in roles
    assert "strategy-registry" in roles
    assert "portfolio-risk" in roles
    assert "production-signals" in roles
    assert "testing-security" in roles
    assert "infra-cost" in roles


def test_role_path_allowlists_are_fail_closed():
    assert path_allowed("quant-trend", "strategy_families.py")
    assert path_allowed("data-market", "market_data.py")
    assert path_allowed("portfolio-risk", "safety.py")
    assert path_allowed("news-macro", "news_macro.py")
    assert not path_allowed("quant-trend", "market_data.py")
    assert not path_allowed("data-market", "engine.py")
    assert not path_allowed("infra-cost", ".github/workflows/autonomous_agents.yml")


def test_protected_paths_are_never_specialist_writable():
    for role in load_roles():
        assert not path_allowed(role, "AI_STATE.md")
        assert not path_allowed(role, "agents/autonomous_orchestrator.py")
        assert not path_allowed(role, ".github/workflows/security.yml")
        assert not path_allowed(role, "requirements.txt")
        assert not path_allowed(role, "Dockerfile")


def test_planner_requires_every_specialist_to_be_active():
    roles = load_roles()
    assert MAX_ACTIVE_TASKS_PER_CYCLE == len(roles) == 14
    tasks = {role: {"status": "TASK", "task": "bounded task"} for role in roles}
    validate_plan({"tasks": tasks}, roles)

    inactive_role = next(iter(roles))
    tasks[inactive_role] = {"status": "NO_TASK", "task": ""}
    try:
        validate_plan({"tasks": tasks}, roles)
    except RuntimeError as exc:
        assert "activate every specialist" in str(exc)
    else:
        raise AssertionError("planner accepted an inactive specialist")


def test_planner_requires_exact_role_set():
    roles = load_roles()
    tasks = {role: {"status": "NO_TASK", "task": ""} for role in roles}
    tasks.pop(next(iter(tasks)))
    try:
        validate_plan({"tasks": tasks}, roles)
    except RuntimeError as exc:
        assert "invalid role set" in str(exc)
    else:
        raise AssertionError("planner accepted an incomplete specialist roster")


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


def test_retry_delay_uses_bounded_backoff_without_retry_after():
    assert _retry_delay(None, 0) == 5.0
    assert _retry_delay(None, 4) == 60.0
    assert _retry_delay(None, 999) == 60.0


class _HeadersOnlyResponse:
    def __init__(self, retry_after: str):
        self.headers = {"retry-after": retry_after}


def test_retry_delay_honors_and_caps_retry_after():
    assert _retry_delay(_HeadersOnlyResponse("17"), 0) == 17.0
    assert _retry_delay(_HeadersOnlyResponse("999"), 0) == 120.0
    assert _retry_delay(_HeadersOnlyResponse("invalid"), 1) == 10.0


def test_hourly_workflows_keep_cost_routing_and_verified_auto_merge_enabled():
    specialist_workflow = open(
        ".github/workflows/autonomous_agents.yml", encoding="utf-8"
    ).read()
    lead_workflow = open(".github/workflows/autonomous_lead.yml", encoding="utf-8").read()

    assert 'cron: "17 * * * *"' in specialist_workflow
    assert "max-parallel: 14" in specialist_workflow
    assert "OPENAI_AGENT_MODEL: gpt-5.6-luna" in specialist_workflow
    assert "'gpt-5.6-sol' || 'gpt-5.6-luna'" in specialist_workflow
    assert "OPENAI_AGENT_MODEL: gpt-5.6-sol" in lead_workflow
    assert 'AUTONOMOUS_MERGE_ENABLED: "true"' in lead_workflow
    assert "Require exact candidate Security and Reliability success" in lead_workflow
    assert "Require both AI reviewers to approve" in lead_workflow
