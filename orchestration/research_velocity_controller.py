"""Research velocity / bottleneck controller.

Pure deterministic helpers for ranking the current bottleneck and producing
acceleration actions. This module does not authorize trading, merges, OOS
opening, paid purchases, or validation-gate changes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence


CRITICAL_TYPES = {
    "scientific_integrity_or_data_leakage": 1.00,
    "missing_or_untrusted_data_contract": 0.95,
    "broken_ci_or_runtime": 0.90,
    "stale_waiting_pr_or_review": 0.78,
    "compute_queue": 0.65,
    "implementation_capacity": 0.60,
    "research_design": 0.58,
    "observability": 0.45,
    "cosmetic_or_dashboard": 0.10,
}


@dataclass(frozen=True)
class WorkItem:
    id: str
    kind: str
    status: str
    expected_information_gain: float = 0.5
    expected_profitability_impact: float = 0.5
    hours_waiting: float = 0.0
    duplicate_risk: float = 0.0
    dependency_removable: bool = False
    independent_lane_available: bool = False
    parallelizable: bool = False
    paid_resource_binding: bool = False
    validation_risk: float = 0.0


@dataclass(frozen=True)
class BottleneckDecision:
    item_id: str
    score: float
    rationale: tuple[str, ...]
    actions: tuple[str, ...]


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def bottleneck_score(item: WorkItem) -> float:
    """Rank urgency/value without rewarding scientific shortcuts."""
    type_weight = CRITICAL_TYPES.get(item.kind, 0.35)
    info = _clamp01(item.expected_information_gain)
    profit = _clamp01(item.expected_profitability_impact)
    duplicate = _clamp01(item.duplicate_risk)
    risk = _clamp01(item.validation_risk)

    wait_multiplier = 1.0
    if item.hours_waiting >= 6:
        wait_multiplier = 1.35
    elif item.hours_waiting >= 2:
        wait_multiplier = 1.15

    unblock_bonus = 0.10 if item.dependency_removable else 0.0
    independence_bonus = 0.07 if item.independent_lane_available else 0.0

    base = type_weight * (0.50 * info + 0.50 * profit)
    score = (base + unblock_bonus + independence_bonus) * wait_multiplier
    score *= 1.0 - 0.75 * duplicate
    score *= 1.0 - 0.65 * risk
    return round(max(score, 0.0), 6)


def acceleration_actions(item: WorkItem) -> tuple[str, ...]:
    actions: list[str] = []
    if item.hours_waiting >= 2:
        actions.append("diagnose_wait_reason")
    if item.dependency_removable:
        actions.append("remove_or_bypass_dependency_safely")
    if item.independent_lane_available:
        actions.append("advance_independent_lane_now")
    if item.parallelizable and item.duplicate_risk < 0.5:
        actions.append("parallelize_non_overlapping_support_work")
    if item.kind == "broken_ci_or_runtime":
        actions.append("repair_ci_or_runtime_before_new_feature_work")
    if item.kind == "missing_or_untrusted_data_contract":
        actions.append("freeze_exact_missing_data_contract_and_resolve_it")
    if item.kind == "scientific_integrity_or_data_leakage":
        actions.append("stop_affected_evidence_path_and_add_regression")
    if item.kind == "compute_queue":
        actions.append("profile_queue_and_use_burst_compute_only_if_compute_is_binding")
    if item.paid_resource_binding:
        actions.append("evaluate_under_adaptive_spending_policy_and_flag_user_if_high_value")
    if not actions:
        actions.append("execute_highest_information_bounded_milestone")
    return tuple(actions)


def select_top_bottleneck(items: Sequence[WorkItem]) -> BottleneckDecision | None:
    eligible = [
        item for item in items
        if item.status.upper() not in {"DONE", "COMPLETED", "REJECTED", "SUPERSEDED"}
    ]
    if not eligible:
        return None

    top = max(eligible, key=lambda item: (bottleneck_score(item), item.id))
    rationale = [
        f"kind={top.kind}",
        f"hours_waiting={top.hours_waiting:g}",
        f"information_gain={_clamp01(top.expected_information_gain):.2f}",
        f"profitability_impact={_clamp01(top.expected_profitability_impact):.2f}",
    ]
    if top.duplicate_risk:
        rationale.append(f"duplicate_risk={_clamp01(top.duplicate_risk):.2f}")
    if top.validation_risk:
        rationale.append(f"validation_risk={_clamp01(top.validation_risk):.2f}")
    return BottleneckDecision(
        item_id=top.id,
        score=bottleneck_score(top),
        rationale=tuple(rationale),
        actions=acceleration_actions(top),
    )


def velocity_metrics(
    *,
    experiments_completed: int,
    experiments_cheaply_rejected: int,
    gate_passes: int,
    duplicate_work_count: int,
    blocked_hours: float,
    pr_wait_hours: float,
    total_variable_cost_usd: float,
) -> Mapping[str, float]:
    completed = max(int(experiments_completed), 0)
    rejected = max(int(experiments_cheaply_rejected), 0)
    passes = max(int(gate_passes), 0)
    cost = max(float(total_variable_cost_usd), 0.0)

    return {
        "experiments_completed_per_7d": float(completed),
        "cheap_rejection_rate": round(rejected / completed, 6) if completed else 0.0,
        "major_evidence_gate_pass_rate": round(passes / completed, 6) if completed else 0.0,
        "duplicate_work_count": float(max(duplicate_work_count, 0)),
        "blocked_hours": round(max(float(blocked_hours), 0.0), 3),
        "pr_wait_hours": round(max(float(pr_wait_hours), 0.0), 3),
        "cost_per_completed_experiment_usd": round(cost / completed, 4) if completed else 0.0,
    }
