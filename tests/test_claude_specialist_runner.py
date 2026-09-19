import copy
from datetime import datetime, timezone

import pytest

from agents.autonomous_cloud_runner import (
    PolicyError,
    default_state,
    load_config,
    load_coordination,
    path_allowed,
    plan_decision,
    reserved_cost_usd,
    safe_branch,
    validate_config,
)
from agents.claude_specialist_runner import CONFIG_PATH, _anthropic_headers

NOW = datetime(2026, 9, 13, 12, 0, tzinfo=timezone.utc)
MAIN_SHA = "a" * 40


def _config():
    return load_config(CONFIG_PATH)


def _coord():
    return load_coordination()

def _ready_role_task(role):
    ready = [
        task for task in _coord()["tasks"]
        if task["owner"] == role
        and task["status"] == "READY"
        and task["id"].startswith("COORD-DISC-")
    ]
    assert len(ready) == 1, (role, ready)
    return ready[0]



def _disabled_config():
    """Test-local copy of the real config with enabled=False.

    The real on-disk config is now enabled=true (owner-approved recurring
    Anthropic usage within the shared $30/month ceiling, see
    resource_recommendations_decisions.json RESOURCE-REC-001). The
    RUNNER_DISABLED fail-closed codepath still needs regression coverage, so
    it is exercised against a deep-copied, test-local config rather than by
    flipping the real gate back off.
    """
    config = copy.deepcopy(_config())
    config["enabled"] = False
    return config


def test_config_uses_the_same_safety_schema_as_the_openai_runner():
    # validate_config() enforces every project-wide safety policy field
    # (broker disconnected, no self-merge, no writes to main, shared cost
    # ceiling, single-agent single-run v1 discipline, model must be listed
    # enabled, per-turn output/turn ceilings) identically for any engine's
    # config -- this test proves the Claude config actually satisfies it,
    # not merely that the function exists.
    validate_config(_config())


def test_config_owns_exactly_one_research_only_role():
    config = _config()
    assert config["autonomous_roles"] == ["signal-accuracy"]
    assert config["engine"] == "claude"


def test_role_permissions_never_touch_production_signal_or_ledger_code():
    """Research-only/audit work cannot mutate production code."""
    config = _config()
    production_files = [
        "paper_trading.py", "engine.py", "selective_precision.py",
        "cross_asset_runner.py", "champion_challenger.py", "db.py",
        "market_data.py", "promotion_manifest.py", "strategy_identity.py",
    ]
    for path in production_files:
        assert path_allowed(config, "signal-accuracy", path) is False, path


def test_role_permissions_allow_only_research_design_artifacts():
    config = _config()
    assert path_allowed(config, "signal-accuracy", "docs/research/signal_accuracy_validation_design.md") is True
    assert path_allowed(config, "signal-accuracy", "tests/test_signal_accuracy_validation_design.py") is True
    assert path_allowed(config, "signal-accuracy", "resource_recommendations_proposed.json") is True


def test_protected_paths_still_fail_closed_for_this_engine():
    config = _config()
    for path in ("AI_STATE.md", "AGENTS.md", "orchestration/specialist_coordination.json", "agents/claude_specialist_runner.py", "live_promotions.json", "resource_recommendations_decisions.json", ".env"):
        assert path_allowed(config, "signal-accuracy", path) is False, path


def test_atomic_claim_branch_naming_matches_shared_convention():
    """Deterministic branch naming is the actual race-prevention mechanism
    (git ref creation is atomic); this proves Claude's runner computes the
    identical branch name any other engine would for the same task, so two
    engines racing for the same task_id collide on the same git ref rather
    than each succeeding under a different name."""
    assert safe_branch("signal-accuracy", "COORD-DISC-VAL-002") == "auto/signal-accuracy/coord-disc-val-002"


def test_disabled_config_still_blocks_all_execution():
    """Regression coverage for the fail-closed RUNNER_DISABLED codepath,
    exercised against a test-local disabled config copy rather than the real
    (now owner-approved, enabled) on-disk config."""
    decision = plan_decision(_disabled_config(), _coord(), default_state(), MAIN_SHA, NOW)
    assert decision.run is False
    assert decision.reason == "RUNNER_DISABLED"



def test_plan_selects_the_owned_ready_task_and_no_other_role():
    """Owner-approved bounded runner selects exactly its current discovery task."""
    expected = _ready_role_task("signal-accuracy")
    decision = plan_decision(_config(), _coord(), default_state(), MAIN_SHA, NOW)
    assert decision.run is True
    assert decision.role == "signal-accuracy"
    assert decision.task_id == expected["id"]
    assert decision.branch == safe_branch("signal-accuracy", expected["id"])


def test_no_agent_can_steal_a_healthy_active_task():
    expected = _ready_role_task("signal-accuracy")
    state = default_state()
    state["active_task"] = {
        "role": "signal-accuracy",
        "task_id": expected["id"],
        "phase": "WAITING_CI",
        "base_main_sha": MAIN_SHA,
        "started_at": "2026-09-13T11:00:00Z",
    }
    decision = plan_decision(_config(), _coord(), state, MAIN_SHA, NOW)
    assert decision.run is False
    assert decision.reason == "ACTIVE_TASK_WAITING_CI"

def test_reserved_cost_uses_verified_haiku_pricing_and_full_turn_ceiling():
    config = _config()
    # $1/MTok input, $5/MTok output. Reserve the full configured output
    # ceiling: 4 turns * 2000 output tokens = 8000 tokens.
    # (100000*1 + 8000*5) / 1e6 = 0.14
    assert reserved_cost_usd(config, "signal-accuracy") == pytest.approx(0.14)


def test_credential_gate_fails_closed_without_anthropic_api_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(PolicyError, match="ANTHROPIC_API_KEY"):
        _anthropic_headers()


def test_credential_gate_succeeds_with_anthropic_api_key(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-not-real")
    headers = _anthropic_headers()
    assert headers["x-api-key"] == "test-key-not-real"
    assert headers["anthropic-version"]


def test_engine_never_gets_a_second_active_role():
    config = _config()
    assert len(config["autonomous_roles"]) == 1
