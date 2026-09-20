from __future__ import annotations

import copy
from datetime import datetime, timezone
from pathlib import Path

import pytest

from agents.autonomous_cloud_runner import (
    PolicyError,
    apply_ci_status,
    budget_gate,
    default_state,
    highest_ready_task,
    load_config,
    load_coordination,
    path_allowed,
    plan_decision,
    recover_state,
    reserved_cost_usd,
    retry_delay_seconds,
    safe_branch,
    validate_action,
    validate_branch,
    validate_config,
    validate_outcome_dict,
)

NOW = datetime(2026, 9, 9, 4, 0, tzinfo=timezone.utc)
MAIN_SHA = "a" * 40


def _config():
    return load_config()


def _coord():
    return load_coordination()


def _coord_with_ready_discovery_task():
    coordination = copy.deepcopy(_coord())
    completed = next(
        task for task in coordination["tasks"]
        if task["id"] == "COORD-DISC-QUANT-004"
    )
    task = copy.deepcopy(completed)
    task.update(
        {
            "id": "COORD-DISC-QUANT-TEST",
            "status": "READY",
            "fingerprint_id": None,
            "issue": None,
            "pr": None,
        }
    )
    task.pop("completion_evidence", None)
    coordination["tasks"].append(task)
    return coordination, task


def test_coordination_loader_applies_canonical_overrides():
    coordination = _coord()
    tasks = {task["id"]: task for task in coordination["tasks"]}
    assert tasks["COORD-DATA-005"]["status"] == "DONE"
    assert tasks["COORD-DATA-007"]["status"] == "BLOCKED"
    assert tasks["COORD-DISC-DATA-001"]["status"] == "DONE"

    current = tasks["COORD-DISC-QUANT-004"]
    assert current["status"] == "DONE"
    assert current["fingerprint_id"] == "DISC-BTC-LEADLAG-001-v1"
    assert current["completion_evidence"]["decision"] == "REJECTED_PRE_OOS"
    primitive = tasks["COORD-MI-CAUSAL-001"]
    assert primitive["status"] == "DONE"
    assert primitive["pr"] == 454
    assert primitive["completion_evidence"]["exact_head_sha"] == (
        "8da3ff1d212d28cfd9f04521c7ab7b5ec5a4d8e3"
    )
    assert primitive["completion_evidence"]["phase_2_complete"] is False
    assert primitive["completion_evidence"]["broker_or_live_authority"] is False
    runtime = tasks["COORD-MI-CAUSAL-002"]
    assert runtime["status"] == "DONE"
    assert runtime["completion_evidence"]["phase_2_complete"] is True
    adversarial = tasks["COORD-ARCH-ADVERSARIAL-001"]
    assert adversarial["status"] == "READY"
    assert adversarial["owner"] == "testing-security"
    assert adversarial["branch"] == "agent/testing-security"
    assert highest_ready_task(_config(), coordination) is None

def test_runner_is_single_execution_multi_role_cost_bounded_and_broker_disconnected():
    config = _config()
    assert config["autonomous_roles"] == ["data-market", "quant-research"]
    assert config["policy"]["max_concurrent_agent_runs"] == 1
    assert config["policy"]["max_agent_runs_per_invocation"] == 1
    assert config["roles"]["data-market"]["max_turns"] <= 8
    assert config["roles"]["data-market"]["max_output_tokens_per_turn"] <= 2000
    assert config["roles"]["quant-research"]["max_turns"] <= 8
    assert config["roles"]["quant-research"]["max_output_tokens_per_turn"] <= 2000
    assert "point_in_time_universe.py" in config["roles"]["data-market"]["allowed_paths"]
    assert "strategy-discovery" in config["roles"]["data-market"]["mission"].lower()
    assert config["roles"]["quant-research"]["model"] == "gpt-5.6-terra"
    assert config["models"]["gpt-5.6-terra"]["enabled"] is True
    assert config["policy"]["automatic_merge"] is False
    assert config["policy"]["trade_authority"] is False
    assert config["policy"]["broker_connected"] is False
    assert config["policy"]["specialists_write_main"] is False
    assert config["policy"]["specialists_merge_own_prs"] is False
    assert config["policy"]["max_retries"] == 0
    assert config["policy"]["task_retry_limit"] == 2
    assert config["budget"]["provider_retry_safety_multiplier"] == 3.0
    assert (
        config["budget"]["baseline_infrastructure_reserve_usd"]
        + config["budget"]["runner_monthly_api_budget_usd"]
        + config["budget"]["pause_buffer_usd"]
        <= config["budget"]["project_monthly_ceiling_usd"]
    )


def test_runaway_loop_configuration_is_rejected():
    config = _config()
    bad = copy.deepcopy(config)
    bad["policy"]["max_agent_runs_per_invocation"] = 2
    with pytest.raises(PolicyError):
        validate_config(bad)
    bad = copy.deepcopy(config)
    bad["roles"]["data-market"]["max_turns"] = 9
    with pytest.raises(PolicyError):
        validate_config(bad)
    bad = copy.deepcopy(config)
    bad["autonomous_roles"] = ["data-market", "quant-research", "signal-accuracy", "testing-security"]
    bad["roles"]["signal-accuracy"] = copy.deepcopy(bad["roles"]["quant-research"])
    bad["roles"]["testing-security"] = copy.deepcopy(bad["roles"]["quant-research"])
    with pytest.raises(PolicyError):
        validate_config(bad)



def test_duplicate_active_task_prevents_second_ownership():
    coordination, task = _coord_with_ready_discovery_task()
    state = default_state()
    state["active_task"] = {
        "role": "quant-research",
        "task_id": task["id"],
        "phase": "WAITING_CI",
        "base_main_sha": MAIN_SHA,
        "started_at": "2026-09-09T03:30:00Z",
    }
    decision = plan_decision(_config(), coordination, state, MAIN_SHA, NOW)
    assert decision.run is False
    assert decision.reason == "ACTIVE_TASK_WAITING_CI"

def test_api_cost_limit_reserves_worst_case_before_model_call():
    config = _config()
    state = default_state()
    reserve = reserved_cost_usd(config, "data-market")
    assert reserve == pytest.approx(0.0416)
    state["runs"].append({
        "finished_at": "2026-09-09T02:00:00Z",
        "actual_cost_usd": 0.98,
    })
    ok, reason, _ = budget_gate(config, state, "data-market", NOW)
    assert ok is False
    assert reason == "DAILY_API_BUDGET"


def test_project_monthly_ceiling_fails_closed_even_if_role_budget_is_relaxed():
    config = _config()
    config = copy.deepcopy(config)
    config["budget"]["runner_daily_api_budget_usd"] = 10
    config["budget"]["runner_monthly_api_budget_usd"] = 10
    config["budget"]["baseline_infrastructure_reserve_usd"] = 29.73
    state = default_state()
    ok, reason, _ = budget_gate(config, state, "data-market", NOW)
    assert ok is False
    assert reason == "PROJECT_MONTHLY_CEILING"


def test_task_retry_backoff_is_bounded_but_outer_api_retry_is_disabled():
    config = _config()
    assert config["policy"]["max_retries"] == 0
    assert config["policy"]["task_retry_limit"] == 2
    assert retry_delay_seconds(config, 0) == 30
    assert retry_delay_seconds(config, 1) == 60
    assert retry_delay_seconds(config, 99) == 300



def test_stale_main_blocks_active_work():
    coordination, task = _coord_with_ready_discovery_task()
    state = default_state()
    state["active_task"] = {
        "role": "quant-research",
        "task_id": task["id"],
        "phase": "WAITING_CI",
        "base_main_sha": "b" * 40,
        "started_at": "2026-09-09T03:30:00Z",
    }
    decision = plan_decision(_config(), coordination, state, MAIN_SHA, NOW)
    assert decision.run is False
    assert decision.reason == "STALE_MAIN_WITH_ACTIVE_TASK"

def test_branch_isolation_rejects_main_and_wrong_role():
    assert safe_branch("data-market", "COORD-DATA-001") == "auto/data-market/coord-data-001"
    with pytest.raises(PolicyError):
        validate_branch("main", "data-market", "COORD-DATA-001")
    with pytest.raises(PolicyError):
        validate_branch("auto/quant-research/coord-data-001", "data-market", "COORD-DATA-001")


def test_attempted_direct_main_write_is_rejected():
    with pytest.raises(PolicyError):
        validate_action("push", "data-market", "main")
    with pytest.raises(PolicyError):
        validate_action("write_branch", "data-market", "main")


def test_attempted_self_merge_and_trading_are_rejected():
    for action in ("merge_own_pr", "merge_pr", "enable_auto_merge", "trade", "place_order", "connect_broker"):
        with pytest.raises(PolicyError):
            validate_action(action, "data-market")


def test_protected_paths_and_role_boundaries_are_not_writable():
    config = _config()
    assert path_allowed(config, "data-market", "market_data.py") is True
    assert path_allowed(config, "data-market", "db.py") is True
    assert path_allowed(config, "data-market", "point_in_time_universe.py") is True
    for path in (
        "AI_STATE.md",
        "AGENTS.md",
        "orchestration/specialist_coordination.json",
        "agents/autonomous_cloud_runner.py",
        ".github/workflows/security.yml",
        "live_promotions.json",
        ".env",
        "../outside.txt",
    ):
        assert path_allowed(config, "data-market", path) is False


def test_failed_ci_never_advances_to_lead_or_merge():
    state = default_state()
    state["active_task"] = {
        "phase": "WAITING_CI",
        "head_sha": "c" * 40,
        "role": "data-market",
        "task_id": "COORD-DATA-001",
    }
    updated = apply_ci_status(state, "failure", "c" * 40)
    assert updated["active_task"]["phase"] == "CI_FAILED"
    assert updated["active_task"]["ci_status"] == "failure"


def test_successful_ci_stops_at_waiting_lead():
    state = default_state()
    state["active_task"] = {
        "phase": "WAITING_CI",
        "head_sha": "c" * 40,
        "role": "data-market",
        "task_id": "COORD-DATA-001",
    }
    updated = apply_ci_status(state, "success", "c" * 40)
    assert updated["active_task"]["phase"] == "WAITING_LEAD"
    assert "MERGED" not in str(updated).upper()


def test_stale_ci_head_fails_closed():
    state = default_state()
    state["active_task"] = {
        "phase": "WAITING_CI",
        "head_sha": "c" * 40,
        "role": "data-market",
        "task_id": "COORD-DATA-001",
    }
    updated = apply_ci_status(state, "success", "d" * 40)
    assert updated["active_task"]["phase"] == "CI_FAILED"
    assert updated["active_task"]["ci_reason"] == "STALE_CI_HEAD"


def test_malformed_agent_output_fails_closed():
    with pytest.raises(PolicyError):
        validate_outcome_dict({"status": "MERGE", "summary": "x", "tests": [], "evidence": [], "risks": [], "changed_files": []})
    with pytest.raises(PolicyError):
        validate_outcome_dict({"status": "READY_FOR_PR", "summary": ""})



def test_completion_handoff_clears_discovery_lease_after_lead_marks_task_done():
    coordination = copy.deepcopy(_coord())
    task = next(row for row in coordination["tasks"] if row["id"] == "COORD-DISC-QUANT-004")
    assert task["status"] == "DONE"
    state = default_state()
    state["active_task"] = {
        "role": "quant-research",
        "task_id": task["id"],
        "phase": "WAITING_LEAD",
        "base_main_sha": MAIN_SHA,
        "started_at": "2026-09-08T20:00:00Z",
    }
    recovered = recover_state(state, coordination, NOW)
    assert recovered["active_task"] is None

    # The rejected strategy remains terminal. Phase 3 is owned by the manual
    # testing-security lane and cannot be claimed by the API cloud runner.
    next_ready = highest_ready_task(_config(), coordination)
    assert next_ready is None

def test_shutdown_restart_recovers_abandoned_running_lease_without_losing_usage_history():
    state = default_state()
    state["runs"].append({"finished_at": "2026-09-08T20:00:00Z", "actual_cost_usd": 0.02})
    state["active_task"] = {
        "role": "data-market",
        "task_id": "COORD-DATA-004",
        "phase": "RUNNING",
        "base_main_sha": MAIN_SHA,
        "started_at": "2026-09-09T01:00:00Z",
    }
    recovered = recover_state(state, _coord(), NOW)
    assert recovered["active_task"] is None
    assert recovered["runs"] == state["runs"]


def test_current_data_coordination_retires_rejected_candidates_and_advances():
    coordination = _coord()
    tasks = {task["id"]: task for task in coordination["tasks"]}
    assert tasks["COORD-DATA-002"]["status"] == "DONE"
    assert tasks["COORD-DATA-002"]["completion_evidence"]["candidate_id"] == "DATA-BASIS-001"
    assert tasks["COORD-DATA-003"]["status"] == "DONE"
    assert tasks["COORD-DATA-003"]["completion_evidence"]["status"] == "REJECTED_CURRENT_FINGERPRINT"
    assert tasks["COORD-DATA-003"]["completion_evidence"]["rejection_pr"] == 291
    assert tasks["COORD-DATA-004"]["status"] == "DONE"
    assert tasks["COORD-DATA-004"]["completion_evidence"]["candidate_id"] == "DATA-FUNDING-001"
    assert tasks["COORD-DATA-004"]["completion_evidence"]["status"] == "REJECTED_CURRENT_FINGERPRINT"
    assert tasks["COORD-DATA-004"]["completion_evidence"]["rejection_pr"] == 298
    assert tasks["COORD-DATA-004"]["completion_evidence"]["24h_incremental_vs_training_only_baseline_bps"] == 0.0
    assert tasks["COORD-DATA-005"]["status"] == "DONE"
    assert tasks["COORD-DATA-007"]["status"] == "BLOCKED"



def test_coordination_priority_routes_phase_three_outside_cloud_runner():
    coordination = _coord()
    assert highest_ready_task(_config(), coordination) is None
    phase_three = next(row for row in coordination["tasks"] if row["id"] == "COORD-ARCH-ADVERSARIAL-001")
    assert phase_three["status"] == "READY"
    assert phase_three["owner"] == "testing-security"
    current = next(row for row in coordination["tasks"] if row["id"] == "COORD-DISC-QUANT-004")
    assert current["status"] == "DONE"
    assert current["completion_evidence"]["decision"] == "REJECTED_PRE_OOS"

def test_legacy_swarm_is_manual_only_and_new_workflow_cannot_merge_main_or_trade():
    legacy = Path(".github/workflows/autonomous_agents.yml").read_text(encoding="utf-8")
    cloud = Path(".github/workflows/autonomous_cloud_specialist.yml").read_text(encoding="utf-8")
    assert "workflow_dispatch:" in legacy
    assert "schedule:" not in legacy
    assert "17 * * * *" not in legacy
    assert 'cron: "41 * * * *"' in cloud
    assert "max-parallel" not in cloud
    assert "gh pr merge" not in cloud
    assert "enable-auto-merge" not in cloud
    assert "git push origin main" not in cloud
    assert "place_order" not in cloud
    assert "trade_authority" not in cloud
    assert "gh workflow run security.yml" in cloud
    assert "OPENAI_API_KEY" in cloud

def test_terminal_rejection_does_not_reopen_hypothesis_freeze():
    coordination = copy.deepcopy(_coord())
    assert highest_ready_task(_config(), coordination) is None
    assert next(row for row in coordination["tasks"] if row["id"] == "COORD-DISC-DATA-004")["status"] == "DONE"
    rejected = next(row for row in coordination["tasks"] if row["id"] == "COORD-DISC-QUANT-004")
    assert rejected["status"] == "DONE"
    assert rejected["fingerprint_id"] == "DISC-BTC-LEADLAG-001-v1"


def test_quant_terra_reservation_fits_daily_budget():
    config = _config()
    reserve = reserved_cost_usd(config, "quant-research")
    assert reserve > reserved_cost_usd(config, "data-market")
    assert reserve * config["budget"]["provider_retry_safety_multiplier"] <= config["budget"]["runner_daily_api_budget_usd"]
