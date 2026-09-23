from orchestration.research_velocity_controller import (
    WorkItem,
    acceleration_actions,
    bottleneck_score,
    closure_mode_actions,
    economic_evidence_status,
    select_top_bottleneck,
    velocity_metrics,
)


def test_scientific_integrity_outranks_cosmetic_work():
    leak = WorkItem(
        id="LEAK",
        kind="scientific_integrity_or_data_leakage",
        status="READY",
        expected_information_gain=0.8,
        expected_profitability_impact=0.8,
    )
    dashboard = WorkItem(
        id="DASH",
        kind="cosmetic_or_dashboard",
        status="READY",
        expected_information_gain=1.0,
        expected_profitability_impact=1.0,
    )
    assert bottleneck_score(leak) > bottleneck_score(dashboard)
    assert select_top_bottleneck([dashboard, leak]).item_id == "LEAK"


def test_stale_work_gets_acceleration_actions_without_weakening_validation():
    item = WorkItem(
        id="WAIT",
        kind="stale_waiting_pr_or_review",
        status="BLOCKED",
        hours_waiting=7,
        dependency_removable=True,
        independent_lane_available=True,
        parallelizable=True,
        paid_resource_binding=True,
    )
    actions = acceleration_actions(item)
    assert "diagnose_wait_reason" in actions
    assert "remove_or_bypass_dependency_safely" in actions
    assert "advance_independent_lane_now" in actions
    assert "parallelize_non_overlapping_support_work" in actions
    assert "evaluate_under_adaptive_spending_policy_and_flag_user_if_high_value" in actions


def test_duplicate_and_validation_risk_reduce_priority():
    clean = WorkItem(id="A", kind="research_design", status="READY")
    risky = WorkItem(
        id="B",
        kind="research_design",
        status="READY",
        duplicate_risk=1.0,
        validation_risk=1.0,
    )
    assert bottleneck_score(clean) > bottleneck_score(risky)


def test_completed_work_is_not_selected():
    done = WorkItem(id="DONE", kind="broken_ci_or_runtime", status="DONE")
    ready = WorkItem(id="READY", kind="research_design", status="READY")
    assert select_top_bottleneck([done, ready]).item_id == "READY"


def test_wip_cap_redirects_workers_to_closure_instead_of_new_branches():
    assert closure_mode_actions(active_implementation_prs=4, lane_wip_cap=5) == ()
    actions = closure_mode_actions(active_implementation_prs=5, lane_wip_cap=5)
    assert "freeze_new_implementation_branches" in actions
    assert "redirect_to_review_repair_ci_re_review_integration" in actions
    assert "reconcile_canonical_state_after_integration" in actions


def test_economic_evidence_sla_never_forces_illegal_screen():
    within = economic_evidence_status(
        hours_since_last_economic_screen=12,
        legal_screen_available=False,
        binding_blocker="REVIEW",
    )
    assert within["status"] == "WITHIN_SLA"

    due = economic_evidence_status(
        hours_since_last_economic_screen=25,
        legal_screen_available=True,
    )
    assert due["status"] == "ECONOMIC_SCREEN_DUE"

    blocked = economic_evidence_status(
        hours_since_last_economic_screen=25,
        legal_screen_available=False,
        binding_blocker="INDEPENDENT_REVIEW_PIPELINE",
    )
    assert blocked["status"] == "NO_ECONOMIC_RESULT"
    assert blocked["binding_blocker"] == "INDEPENDENT_REVIEW_PIPELINE"


def test_velocity_metrics_are_safe_at_zero_and_cost_aware():
    zero = velocity_metrics(
        experiments_completed=0,
        experiments_cheaply_rejected=0,
        gate_passes=0,
        duplicate_work_count=0,
        blocked_hours=0,
        pr_wait_hours=0,
        total_variable_cost_usd=30,
    )
    assert zero["cost_per_completed_experiment_usd"] == 0.0

    metrics = velocity_metrics(
        experiments_completed=10,
        experiments_cheaply_rejected=7,
        gate_passes=2,
        duplicate_work_count=1,
        blocked_hours=5,
        pr_wait_hours=3,
        total_variable_cost_usd=50,
        useful_falsifications=8,
        evidence_stage_advances=2,
        hours_since_last_economic_screen=9,
        active_implementation_prs=5,
        prs_waiting_over_24h=3,
        review_blocked_hours=2,
        data_blocked_hours=1,
        ci_blocked_hours=1,
        compute_blocked_hours=1,
        hypothesis_to_first_result_hours=(4, 8, 12),
    )
    assert metrics["cheap_rejection_rate"] == 0.7
    assert metrics["major_evidence_gate_pass_rate"] == 0.2
    assert metrics["cost_per_completed_experiment_usd"] == 5.0
    assert metrics["useful_falsifications_per_7d"] == 8.0
    assert metrics["evidence_stage_advances_per_7d"] == 2.0
    assert metrics["median_hypothesis_to_first_economic_result_hours"] == 8.0
    assert metrics["prs_waiting_over_24h"] == 3.0
