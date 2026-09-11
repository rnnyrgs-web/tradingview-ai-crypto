"""Stage-2 profitability robustness diagnostics for frozen DATA-BASIS-001.

This module does not tune the feature or open untouched OOS. It reuses the frozen
chronological stage-1 split and asks a stricter economic question: does the basis
rule add after-cost value versus a training-only constant market direction, and
does its OOS expectancy survive fixed conservative cost stress and simple
subperiod checks? These diagnostics are rejection-oriented and research-only.
"""

from __future__ import annotations

from config import BACKTEST_COST_BPS
from basis_falsification_research import (
    DEFAULT_MIN_OOS_SAMPLES,
    PRIMARY_HORIZONS,
    _timestamp_exact_examples,
    _training_direction,
)

COST_STRESS_MULTIPLIERS = (1.0, 2.0, 3.0)


def _constant_training_direction(train):
    if not train:
        return None
    mean_return = sum(row["future_return_bps"] for row in train) / len(train)
    if mean_return == 0:
        return None
    return 1 if mean_return > 0 else -1


def _avg(values):
    return sum(values) / len(values) if values else None


def evaluate_basis_profitability_robustness(
    dataset,
    horizon_hours,
    cost_bps=BACKTEST_COST_BPS,
    train_fraction=0.6,
    min_oos_samples=DEFAULT_MIN_OOS_SAMPLES,
):
    """Falsify incremental economic value without OOS tuning.

    The basis association sign and the constant-direction comparator are both
    learned from the same chronological training segment and frozen before OOS.
    The fixed 1x/2x/3x cost grid is a stress test, not a parameter search.
    """
    if not dataset.get("research_only") or dataset.get("candidate_id") != "DATA-BASIS-001":
        return {"research_only": True, "available": False, "reason": "invalid_research_dataset"}
    if not dataset.get("available"):
        return {"research_only": True, "available": False, "reason": dataset.get("reason") or "dataset_unavailable"}

    examples = _timestamp_exact_examples(dataset, horizon_hours)
    if len(examples) < 4:
        return {"research_only": True, "available": False, "reason": "insufficient_non_overlapping_exact_horizon_samples"}

    split = int(len(examples) * float(train_fraction))
    split = max(2, min(split, len(examples) - 2))
    train = examples[:split]
    oos = examples[split:]
    if len(oos) < int(min_oos_samples):
        return {
            "research_only": True,
            "available": False,
            "reason": "insufficient_oos_samples_before_robustness",
            "oos_samples": len(oos),
            "minimum_oos_samples": int(min_oos_samples),
        }

    basis_direction = _training_direction(train)
    baseline_direction = _constant_training_direction(train)
    if basis_direction is None or baseline_direction is None:
        return {"research_only": True, "available": False, "reason": "training_direction_unavailable"}

    scored = []
    for row in oos:
        signed_feature = basis_direction * row["basis_bps"]
        if signed_feature == 0:
            continue
        basis_signal = 1 if signed_feature > 0 else -1
        basis_gross = basis_signal * row["future_return_bps"]
        baseline_gross = baseline_direction * row["future_return_bps"]
        scored.append({"basis_gross_bps": basis_gross, "baseline_gross_bps": baseline_gross})

    if len(scored) < int(min_oos_samples):
        return {
            "research_only": True,
            "available": False,
            "reason": "insufficient_oos_nonzero_feature_samples",
            "oos_samples": len(scored),
            "minimum_oos_samples": int(min_oos_samples),
        }

    base_cost = float(cost_bps)
    basis_gross = [row["basis_gross_bps"] for row in scored]
    baseline_gross = [row["baseline_gross_bps"] for row in scored]
    basis_base_net = [value - base_cost for value in basis_gross]
    baseline_base_net = [value - base_cost for value in baseline_gross]

    stress = {}
    for multiplier in COST_STRESS_MULTIPLIERS:
        stressed_cost = base_cost * multiplier
        net = [value - stressed_cost for value in basis_gross]
        stress[f"{multiplier:g}x"] = {
            "cost_bps_round_trip": stressed_cost,
            "avg_net_bps": _avg(net),
            "positive_after_cost": _avg(net) > 0,
        }

    half = len(scored) // 2
    first = basis_base_net[:half]
    second = basis_base_net[half:]
    segment_minimum_met = len(first) >= 4 and len(second) >= 4

    training_checkpoints = []
    for fraction in (0.5, 0.75, 1.0):
        n = max(2, int(len(train) * fraction))
        direction = _training_direction(train[:n])
        training_checkpoints.append(direction)

    basis_avg_net = _avg(basis_base_net)
    baseline_avg_net = _avg(baseline_base_net)
    basis_hit = sum(value > 0 for value in basis_gross) / len(basis_gross)
    baseline_hit = sum(value > 0 for value in baseline_gross) / len(baseline_gross)

    return {
        "research_only": True,
        "available": True,
        "candidate_id": "DATA-BASIS-001",
        "horizon_hours": int(horizon_hours),
        "chronological": True,
        "non_overlapping": True,
        "threshold_tuning": False,
        "untouched_oos_opened": False,
        "oos_samples": len(scored),
        "training_only_basis_direction": basis_direction,
        "training_only_constant_direction": baseline_direction,
        "training_direction_checkpoints": training_checkpoints,
        "training_direction_stable": all(d == basis_direction for d in training_checkpoints),
        "basis_oos_hit_rate": basis_hit,
        "constant_baseline_oos_hit_rate": baseline_hit,
        "basis_oos_avg_net_bps": basis_avg_net,
        "constant_baseline_oos_avg_net_bps": baseline_avg_net,
        "incremental_vs_constant_avg_net_bps": basis_avg_net - baseline_avg_net,
        "beats_training_only_constant_baseline": basis_avg_net > baseline_avg_net,
        "cost_stress": stress,
        "oos_half_minimum_met": segment_minimum_met,
        "first_half_avg_net_bps": _avg(first) if segment_minimum_met else None,
        "second_half_avg_net_bps": _avg(second) if segment_minimum_met else None,
        "both_oos_halves_positive": (_avg(first) > 0 and _avg(second) > 0) if segment_minimum_met else None,
        "promotion_authority": False,
        "production_authority": False,
        "note": "Stage-2 rejection diagnostic only; untouched OOS, multiple-testing, regime/liquidity and genuine-forward gates remain closed.",
    }


def evaluate_primary_profitability_robustness(dataset, cost_bps=BACKTEST_COST_BPS):
    return {
        "research_only": True,
        "candidate_id": "DATA-BASIS-001",
        "results": {
            str(hours): evaluate_basis_profitability_robustness(dataset, hours, cost_bps=cost_bps)
            for hours in PRIMARY_HORIZONS
        },
        "promotion_authority": False,
        "production_authority": False,
    }
