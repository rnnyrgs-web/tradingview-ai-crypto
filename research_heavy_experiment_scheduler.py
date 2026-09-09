"""Bounded research-only scheduler for deterministic heavy experiment candidates.

The scheduler only ranks and admits already-predeclared experiment specs. It never
mutates strategies, promotes a model, places orders, or raises heavy concurrency.
"""

from __future__ import annotations

from math import isfinite

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
    if not experiment.get("experiment_id"):
        return False
    if not experiment.get("required_validation"):
        return False
    forbidden = (
        "automatic_execution_authority",
        "strategy_mutation_authority",
        "trade_authority",
        "promotion_authority",
    )
    return all(experiment.get(flag) is False for flag in forbidden)


def build_heavy_dispatch_plan(
    experiment_queue: dict,
    *,
    running_experiment_ids=None,
    max_slots: int = MAX_HEAVY_EXPERIMENT_SLOTS,
) -> dict:
    """Choose the highest-information research experiments for scarce heavy compute.

    This is an admission/priority plan only. A separate executor must still validate
    the immutable experiment contract before launching any backtest process.
    """
    running = {str(value) for value in (running_experiment_ids or []) if value}
    slots = max(0, min(int(max_slots), MAX_HEAVY_EXPERIMENT_SLOTS))
    rows = experiment_queue.get("experiments") if isinstance(experiment_queue, dict) else []
    candidates = [row for row in (rows or []) if _eligible(row) and str(row.get("experiment_id")) not in running]
    candidates.sort(
        key=lambda row: (
            -_finite(row.get("information_priority")),
            -int(row.get("source_samples") or 0),
            str(row.get("experiment_id")),
        )
    )
    selected = []
    for row in candidates[:slots]:
        selected.append(
            {
                "experiment_id": str(row["experiment_id"]),
                "information_priority": _finite(row.get("information_priority")),
                "source_samples": int(row.get("source_samples") or 0),
                "dimension": str(row.get("dimension") or "unknown"),
                "group": str(row.get("group") or "unknown"),
                "status": "ADMITTED_FOR_HEAVY_RESEARCH",
                "required_validation": list(row.get("required_validation") or []),
                "trade_authority": False,
                "promotion_authority": False,
                "strategy_mutation_authority": False,
            }
        )
    return {
        "ok": True,
        "research_only": True,
        "heavy_slot_limit": slots,
        "running_experiment_count": len(running),
        "eligible_candidate_count": len(candidates),
        "selected_count": len(selected),
        "selected": selected,
        "trade_authority": False,
        "promotion_authority": False,
        "strategy_mutation_authority": False,
        "raises_heavy_concurrency": False,
    }
