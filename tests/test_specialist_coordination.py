import copy

import pytest

from orchestration.specialist_coordination import (
    REQUIRED_ROLES,
    compact_snapshot,
    load_state,
    next_task,
    role_queue,
    validate_state,
)


def test_coordination_state_has_exact_specialist_roster_and_safe_policy():
    state = load_state()
    assert set(state["roles"]) == REQUIRED_ROLES
    assert state["policy"]["priority_basis"] == "expected_genuine_forward_signal_quality_impact"
    assert state["policy"]["specialists_write_main"] is False
    assert state["policy"]["specialists_merge_own_prs"] is False
    assert state["policy"]["automatic_merge"] is False
    assert state["policy"]["broker_connected"] is False
    assert state["policy"]["monthly_infrastructure_ceiling_usd"] == 30
    assert state["policy"]["insufficient_evidence"] == "WAIT_RESEARCH_ONLY"


def test_each_specialist_has_one_obvious_active_task_and_handoff():
    state = load_state()
    for role in REQUIRED_ROLES:
        active = [
            row for row in role_queue(state, role)
            if row["status"] in {"READY", "IN_PROGRESS", "PR_OPEN"}
        ]
        assert len(active) == 1, (role, active)
        task = next_task(state, role)
        assert task == active[0]
        assert task["evidence_required"]
        assert task["branch"] == state["roles"][role]["branch"]
        assert task["next_task"] is not None


def test_duplicate_active_ownership_is_rejected():
    state = load_state()
    bad = copy.deepcopy(state)
    queued = next(row for row in bad["tasks"] if row["owner"] == "quant-research" and row["status"] == "QUEUED")
    queued["status"] = "READY"
    with pytest.raises(RuntimeError, match="duplicate active ownership"):
        validate_state(bad)


def test_unknown_coordination_dependency_is_rejected():
    state = load_state()
    bad = copy.deepcopy(state)
    bad["tasks"][0]["dependencies"] = ["COORD-MISSING-999"]
    with pytest.raises(RuntimeError, match="unknown task dependency"):
        validate_state(bad)


def test_blocked_task_requires_explicit_blocker():
    state = load_state()
    bad = copy.deepcopy(state)
    blocked = next(row for row in bad["tasks"] if row["status"] == "BLOCKED")
    blocked["blockers"] = []
    with pytest.raises(RuntimeError, match="BLOCKED task missing blocker"):
        validate_state(bad)


def test_pr_open_requires_pr_reference():
    state = load_state()
    bad = copy.deepcopy(state)
    task = bad["tasks"][0]
    task["status"] = "PR_OPEN"
    task["pr"] = None
    with pytest.raises(RuntimeError, match="PR_OPEN task missing pr"):
        validate_state(bad)


def test_safety_policy_cannot_silently_enable_merge_main_broker_or_extra_cost():
    state = load_state()
    mutations = (
        ("specialists_write_main", True, "specialists must not write main"),
        ("specialists_merge_own_prs", True, "specialists must not merge their own PRs"),
        ("automatic_merge", True, "automatic merge must remain disabled"),
        ("broker_connected", True, "broker must remain disconnected"),
        ("monthly_infrastructure_ceiling_usd", 31, "monthly infrastructure ceiling"),
    )
    for key, value, message in mutations:
        bad = copy.deepcopy(state)
        bad["policy"][key] = value
        with pytest.raises(RuntimeError, match=message):
            validate_state(bad)


def test_compact_snapshot_keeps_role_next_work_small():
    state = load_state()
    snapshot = compact_snapshot(state)
    assert set(snapshot["roles"]) == REQUIRED_ROLES
    assert all(snapshot["roles"][role]["next"] for role in REQUIRED_ROLES)
