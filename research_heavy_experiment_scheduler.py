"""Bounded research-only scheduler for deterministic heavy experiment candidates.

The scheduler only ranks and admits already-predeclared experiment specs. It never
mutates strategies, promotes a model, places orders, or raises heavy concurrency.
"""

from __future__ import annotations

from math import isfinite

from signal_development import objective_reference, priority_score, validate_task_contract

MAX_HEAVY_EXPERIMENT_SLOTS = 1


def _finite(value, default=0.0):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return float(default)
    return number if isfinite(number) else float(default)


def _eligible(experiment: dict) -> bool:
    if not isinstance(experiment, dict):
        return False
    if experiment.get("compute_class") != "heavy_candidate":
        return False
    if experiment.get("status") != "QUEUED_RESEARCH_ONLY":
        return False
    if not experiment.get("experiment_id") or not experiment.get("required_validation"):
        return False
    try:
        validate_task_contract(experiment)
    except RuntimeError:
        return False
    forbidden = ("automatic_execution_authority", "strategy_mutation_authority", "trade_authority", "promotion_authority")
    return all(experiment.get(flag) is False for flag in forbidden)


def _signal_priority(row: dict) -> float:
    factors = row.get("priority_factors") or {}
    return priority_score(
        expected_genuine_signal_quality_impact=factors.get("expected_genuine_signal_quality_impact", 0),
        expected_information_falsification_value=factors.get("expected_information_falsification_value", 0),
        probability_actionable_evidence=factors.get("probability_actionable_evidence", 0),
        compute_api_cost_units=factors.get("compute_api_cost_units", 1),
    )


def build_heavy_dispatch_plan(experiment_queue: dict, *, running_experiment_ids=None, max_slots: int = MAX_HEAVY_EXPERIMENT_SLOTS) -> dict:
    """Choose highest expected genuine signal-value experiments for scarce heavy compute."""
    running = {str(value) for value in (running_experiment_ids or []) if value}
    slots = max(0, min(int(max_slots), MAX_HEAVY_EXPERIMENT_SLOTS))
    rows = experiment_queue.get("experiments") if isinstance(experiment_queue, dict) else []
    candidates = [row for row in (rows or []) if _eligible(row) and str(row.get("experiment_id")) not in running]
    candidates.sort(key=lambda row: (-_signal_priority(row), -int(row.get("source_independent_samples") or 0), str(row.get("experiment_id"))))
    selected = []
    for row in candidates[:slots]:
        selected.append({
            "experiment_id": str(row["experiment_id"]),
            "signal_priority_score": _signal_priority(row),
            "priority_factors": dict(row.get("priority_factors") or {}),
            "information_priority": _finite(row.get("information_priority")),
            "source_samples": int(row.get("source_samples") or 0),
            "source_independent_samples": int(row.get("source_independent_samples") or 0),
            "dimension": str(row.get("dimension") or "unknown"),
            "group": str(row.get("group") or "unknown"),
            "target_horizon": row.get("target_horizon"),
            "hypothesis": row.get("hypothesis"),
            "falsification_criteria": list(row.get("falsification_criteria") or []),
            "status": "ADMITTED_FOR_HEAVY_RESEARCH",
            "required_validation": list(row.get("required_validation") or []),
            "trade_authority": False,
            "promotion_authority": False,
            "strategy_mutation_authority": False,
        })
    return {
        "ok": True,
        "research_only": True,
        "objective": objective_reference("heavy-experiment-scheduler", "heavy_experiment_scheduler"),
        "heavy_slot_limit": slots,
        "running_experiment_count": len(running),
        "eligible_candidate_count": len(candidates),
        "selected_count": len(selected),
        "selected": selected,
        "priority_policy": "expected genuine signal-quality impact x information/falsification value x probability of actionable evidence / compute/API cost",
        "trade_authority": False,
        "promotion_authority": False,
        "strategy_mutation_authority": False,
        "raises_heavy_concurrency": False,
    }
