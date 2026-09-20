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
    assert state["policy"]["priority_basis"] == "expected_incremental_after_cost_profitability_impact_then_forward_signal_quality"
    assert state["policy"]["specialists_write_main"] is False
    assert state["policy"]["specialists_merge_own_prs"] is False
    assert state["policy"]["automatic_merge"] is False
    assert state["policy"]["broker_connected"] is False
    assert state["policy"]["monthly_infrastructure_ceiling_usd"] == 30
    assert state["policy"]["insufficient_evidence"] == "WAIT_RESEARCH_ONLY"



def test_phase_three_has_exactly_one_active_owned_milestone():
    state = load_state()

    active_by_role = {}
    for role in REQUIRED_ROLES:
        active = [
            row for row in role_queue(state, role)
            if row["status"] in {"READY", "IN_PROGRESS", "PR_OPEN"}
        ]
        if active:
            active_by_role[role] = active

    assert set(active_by_role) == {"testing-security"}
    assert [row["id"] for row in active_by_role["testing-security"]] == [
        "COORD-ARCH-ADVERSARIAL-001"
    ]
    completed = next(row for row in state["tasks"] if row["id"] == "COORD-MI-CAUSAL-001")
    assert completed["status"] == "DONE"
    assert completed["pr"] == 454
    assert completed["completion_evidence"]["phase_2_complete"] is False
    assert completed["completion_evidence"]["broker_or_live_authority"] is False
    assert next_task(state, "quant-research") is None
    assert next_task(state, "data-market") is None
    assert next_task(state, "testing-security")["issue"] == 462
    assert next_task(state, "testing-security")["branch"] == "agent/testing-security"

def test_completed_data_provenance_work_is_not_reassigned():
    state = load_state()
    completed = next(row for row in state["tasks"] if row["id"] == "COORD-DATA-001")
    assert completed["status"] == "DONE"
    assert completed["completion_evidence"]["commit"] == "f1749e3d794faaac2e4ed30aba9c8a081a75fd06"
    assert "tests/test_preforecast_market_provenance.py" in completed["completion_evidence"]["tests"]

    selected = next(row for row in state["tasks"] if row["id"] == "COORD-DATA-002")
    assert selected["status"] == "DONE"
    assert selected["completion_evidence"]["candidate_id"] == "DATA-BASIS-001"
    assert selected["next_task"] == "COORD-DATA-003"

    rejected_basis = next(row for row in state["tasks"] if row["id"] == "COORD-DATA-003")
    assert rejected_basis["status"] == "DONE"
    assert rejected_basis["completion_evidence"]["status"] == "REJECTED_CURRENT_FINGERPRINT"
    assert rejected_basis["completion_evidence"]["rejection_pr"] == 291
    assert rejected_basis["next_task"] == "COORD-DATA-004"

    rejected_funding = next(row for row in state["tasks"] if row["id"] == "COORD-DATA-004")
    assert rejected_funding["status"] == "DONE"
    assert rejected_funding["completion_evidence"]["candidate_id"] == "DATA-FUNDING-001"
    assert rejected_funding["completion_evidence"]["status"] == "REJECTED_CURRENT_FINGERPRINT"
    assert rejected_funding["completion_evidence"]["rejection_pr"] == 298
    assert rejected_funding["completion_evidence"]["24h_incremental_vs_training_only_baseline_bps"] == 0.0
    assert rejected_funding["next_task"] == "COORD-DATA-005"

    breadth = next(row for row in state["tasks"] if row["id"] == "COORD-DATA-005")
    assert breadth["status"] == "DONE"
    assert breadth["completion_evidence"]["candidate_id"] == "DATA-BREADTH-001"
    assert breadth["completion_evidence"]["selection_pr"] == 300
    assert breadth["completion_evidence"]["evaluator_pr"] == 301
    assert breadth["completion_evidence"]["status"] == "EVALUATOR_INTEGRATED_POINT_IN_TIME_HISTORY_BLOCKED"
    assert breadth["next_task"] == "COORD-DATA-006"

    capture = next(row for row in state["tasks"] if row["id"] == "COORD-DATA-006")
    assert capture["status"] == "DONE"
    assert capture["completion_evidence"]["integration_pr"] == 306
    assert capture["completion_evidence"]["status"] == "PROSPECTIVE_PIT_CAPTURE_VERIFIED_LIVE"
    assert capture["completion_evidence"]["member_count"] == 79
    assert capture["completion_evidence"]["historical_backfill"] is False
    assert capture["completion_evidence"]["future_data_used"] is False
    assert capture["completion_evidence"]["trade_authority_added"] is False
    assert capture["next_task"] == "COORD-DATA-007"

    next_data_task = next(row for row in state["tasks"] if row["id"] == "COORD-DATA-007")
    assert next_data_task["status"] == "BLOCKED"
    assert next_task(state, "data-market") is None
    rejected = next(row for row in state["tasks"] if row["id"] == "COORD-DISC-QUANT-004")
    assert rejected["status"] == "DONE"
    assert rejected["fingerprint_id"] == "DISC-BTC-LEADLAG-001-v1"
    assert rejected["completion_evidence"]["decision"] == "REJECTED_PRE_OOS"
    assert rejected["completion_evidence"]["untouched_oos_opened"] is False
    assert next_task(state, "quant-research") is None
    assert next_task(state, "testing-security")["id"] == "COORD-ARCH-ADVERSARIAL-001"
    assert "matured prospective point-in-time cohorts" in next_data_task["title"]
    requirements = " ".join(next_data_task["evidence_required"]).lower()
    assert "minimum eight independent" in requirements
    assert "1x/2x/3x realistic execution-cost stress" in requirements
    assert "no threshold mining" in requirements
    assert next_data_task["blockers"]


def test_duplicate_active_ownership_is_rejected():
    state = load_state()
    bad = copy.deepcopy(state)
    legacy = next(row for row in bad["tasks"] if row["id"] == "COORD-QUANT-002")
    legacy["status"] = "READY"
    legacy["work_mode"] = "CHEAP_SCREEN"
    legacy["blockers"] = []
    current = copy.deepcopy(next(row for row in bad["tasks"] if row["id"] == "COORD-DISC-QUANT-004"))
    current.update(
        {
            "id": "COORD-DISC-QUANT-TEST",
            "status": "READY",
            "fingerprint_id": "DISC-TEST-GENUINELY-NEW-v1",
            "pr": None,
        }
    )
    current.pop("completion_evidence", None)
    bad["tasks"].append(current)
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



def test_compact_snapshot_keeps_role_next_work_aligned_to_discovery():
    state = load_state()
    snapshot = compact_snapshot(state)
    assert set(snapshot["roles"]) == REQUIRED_ROLES

    for role in REQUIRED_ROLES:
        expected = next_task(state, role)
        actual = snapshot["roles"][role]["next"]
        if expected is None:
            assert actual is None
        else:
            assert actual is not None
            assert actual["id"] == expected["id"]
            assert actual.get("fingerprint_id") == expected.get("fingerprint_id")
