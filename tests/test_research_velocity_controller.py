from orchestration.research_velocity_controller import (
    WorkItem,
    acceleration_actions,
    bottleneck_score,
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
    )
    assert metrics["cheap_rejection_rate"] == 0.7
    assert metrics["major_evidence_gate_pass_rate"] == 0.2
    assert metrics["cost_per_completed_experiment_usd"] == 5.0
