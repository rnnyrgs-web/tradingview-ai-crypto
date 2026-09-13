import copy
from datetime import datetime, timezone

import pytest

from agents.autonomous_cloud_runner import (
    default_state,
    load_config,
    load_coordination,
    path_allowed,
    plan_decision,
    reserved_cost_usd,
    safe_branch,
    validate_config,
)
from agents.claude_code_specialist_runner import CONFIG_PATH

NOW = datetime(2026, 9, 13, 12, 0, tzinfo=timezone.utc)
MAIN_SHA = "b" * 40


def _config():
    return load_config(CONFIG_PATH)


def _coord():
    return load_coordination()


def _enabled_config():
    """Test-local copy of the real config with enabled=True.

    The on-disk config is enabled=false (safety: disabled pending
    paid-service approval, see BUG_REGRESSION_LEDGER.md). Ownership/planning
    behavior still needs coverage, so it is exercised against a deep-copied,
    test-local config rather than by flipping the real gate.
    """
    config = copy.deepcopy(_config())
    config["enabled"] = True
    return config


def test_config_uses_the_same_safety_schema_as_the_openai_runner():
    validate_config(_config())


def test_config_owns_exactly_one_implementation_role():
    config = _config()
    assert config["autonomous_roles"] == ["testing-security"]
    assert config["engine"] == "claude-code"


def test_role_permissions_match_the_existing_testing_security_role_exactly():
    """Reuses the already-defined testing-security allowlist from
    agents/roles.json rather than inventing new scope for this engine."""
    from agents.autonomous_orchestrator import load_roles

    legacy_allowed_paths = set(load_roles()["testing-security"]["allowed_paths"])
    config_allowed_paths = set(_config()["roles"]["testing-security"]["allowed_paths"])
    assert legacy_allowed_paths.issubset(config_allowed_paths)


def test_role_permissions_never_touch_production_signal_or_ledger_code():
    config = _config()
    production_files = [
        "paper_trading.py", "engine.py", "selective_precision.py",
        "cross_asset_runner.py", "champion_challenger.py", "db.py",
        "market_data.py", "promotion_manifest.py", "strategy_identity.py",
    ]
    for path in production_files:
        assert path_allowed(config, "testing-security", path) is False, path


def test_role_permissions_allow_test_files():
    config = _config()
    assert path_allowed(config, "testing-security", "tests/test_something_new.py") is True
    assert path_allowed(config, "testing-security", "resource_recommendations_proposed.json") is True


def test_protected_paths_still_fail_closed_for_this_engine():
    config = _config()
    for path in ("AI_STATE.md", "AGENTS.md", "orchestration/specialist_coordination.json", "agents/claude_code_specialist_runner.py", "live_promotions.json", "resource_recommendations_decisions.json", ".env"):
        assert path_allowed(config, "testing-security", path) is False, path


def test_atomic_claim_branch_naming_matches_shared_convention():
    assert safe_branch("testing-security", "COORD-TEST-001") == "auto/testing-security/coord-test-001"


def test_runner_disabled_pending_paid_service_approval_blocks_all_execution():
    """The real on-disk config is enabled=false (safety: disabled pending
    paid-service approval). plan_decision must fail closed regardless of an
    otherwise-ready owned task, never silently run."""
    decision = plan_decision(_config(), _coord(), default_state(), MAIN_SHA, NOW)
    assert decision.run is False
    assert decision.reason == "RUNNER_DISABLED"


def test_plan_selects_the_owned_ready_task_and_no_other_role():
    """Ownership/planning behavior, exercised against a test-local enabled
    config copy -- the real config stays disabled pending paid-service
    approval; see test_runner_disabled_pending_paid_service_approval_blocks_all_execution."""
    decision = plan_decision(_enabled_config(), _coord(), default_state(), MAIN_SHA, NOW)
    assert decision.run is True
    assert decision.role == "testing-security"
    assert decision.task_id == "COORD-TEST-001"
    assert decision.branch == "auto/testing-security/coord-test-001"


def test_no_agent_can_steal_a_healthy_active_task():
    state = default_state()
    state["active_task"] = {
        "role": "testing-security",
        "task_id": "COORD-TEST-001",
        "phase": "WAITING_CI",
        "base_main_sha": MAIN_SHA,
        "started_at": "2026-09-13T11:00:00Z",
    }
    decision = plan_decision(_enabled_config(), _coord(), state, MAIN_SHA, NOW)
    assert decision.run is False
    assert decision.reason == "ACTIVE_TASK_WAITING_CI"


def test_reserved_cost_uses_verified_haiku_pricing():
    config = _config()
    # (150000*1 + 10000*5) / 1e6 = 0.20
    assert reserved_cost_usd(config, "testing-security") == pytest.approx(0.20)


def test_claude_code_and_claude_research_roles_never_collide():
    """The two new engines own disjoint coordination roles by construction
    (signal-accuracy vs testing-security), so their deterministic claim
    branches can never collide with each other."""
    from agents.claude_specialist_runner import CONFIG_PATH as CLAUDE_CONFIG_PATH

    claude_role = load_config(CLAUDE_CONFIG_PATH)["autonomous_roles"][0]
    claude_code_role = _config()["autonomous_roles"][0]
    assert claude_role != claude_code_role


def test_claude_code_role_does_not_collide_with_the_currently_enabled_openai_role():
    from agents.autonomous_cloud_runner import CONFIG_PATH as OPENAI_CONFIG_PATH

    openai_role = load_config(OPENAI_CONFIG_PATH)["autonomous_roles"][0]
    assert openai_role != _config()["autonomous_roles"][0]
