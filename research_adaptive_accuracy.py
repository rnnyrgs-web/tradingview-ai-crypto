"""Adaptive research-only evaluator for predeclared restrictive accuracy experiments.

The evaluator turns the quant-science factory's highest-value dispatchable hypothesis
into a deterministic chronological experiment. Hypothesis discovery uses development
rows only. Untouched OOS outcomes are not inspected unless the frozen hypothesis
passes its validation gate. Results are evidence only and never mutate production.
"""

from __future__ import annotations

import hashlib
from math import isfinite
from statistics import NormalDist

from calibration import wilson_lower_bound
from research_heavy_experiment_scheduler import build_heavy_dispatch_plan
from research_learning import learning_diagnostics
from research_quant_science_factory import build_quant_science_queue
from selective_precision import _independent_rows

DEFAULT_ROUND_TRIP_COST_PCT = 0.12
MIN_VALIDATION_SAMPLES = 8
MIN_ACTIONABLE_COVERAGE = 0.25
MATERIAL_SAMPLE_GROWTH_MIN = 4
MATERIAL_SAMPLE_GROWTH_RATIO = 1.25
FAMILYWISE_ALPHA = 0.05


def _finite(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if isfinite(number) else None


def _score_band(value):
    score = _finite(value)
    if score is None:
        return "unknown"
    if score >= 90:
        return "90+"
    if score >= 80:
        return "80-89"
    if score >= 70:
        return "70-79"
    if score >= 60:
        return "60-69"
    return "<60"


def _strategy_group(row):
    identity = row.get("strategy_identity")
    return str(identity if identity is not None else "unknown")


def _group_value(row, dimension):
    if dimension == "score_band":
        return _score_band(row.get("score"))
    if dimension == "market_regime":
        return str(row.get("market_regime") or "unknown")
    if dimension == "direction":
        return str(row.get("direction") or "unknown")
    if dimension == "strategy_identity":
        return _strategy_group(row)
    if dimension == "horizon":
        return str(row.get("horizon") or "unknown")
    return "unknown"


def _resolved(rows):
    return [row for row in (rows or []) if row.get("resolved_at") and isinstance(row.get("correct"), bool)]


def _chronological_splits(rows):
    """Create deterministic 60/20/20 splits using independent rows per horizon.

    Partitioning itself is outcome-blind. The OOS rows are returned as sealed inputs;
    callers must not score them until validation has passed.
    """
    development, validation, untouched_oos = [], [], []
    for horizon in ("24h", "7d"):
        independent = _independent_rows([row for row in _resolved(rows) if row.get("horizon") == horizon], horizon)
        n = len(independent)
        if n == 0:
            continue
        dev_end = max(1, int(n * 0.60))
        val_end = max(dev_end, int(n * 0.80))
        if n >= 3:
            val_end = max(dev_end + 1, val_end)
            val_end = min(val_end, n - 1)
        development.extend(independent[:dev_end])
        validation.extend(independent[dev_end:val_end])
        untouched_oos.extend(independent[val_end:])
    return development, validation, untouched_oos


def _lesson_fingerprint(dimension, group):
    return hashlib.sha256(f"{dimension}|{group}".encode("utf-8")).hexdigest()[:24]


def _prior_conclusive_lesson(memory, dimension, group):
    fingerprint = _lesson_fingerprint(dimension, group)
    for lesson in reversed((memory or {}).get("lessons") or []):
        if lesson.get("fingerprint") != fingerprint:
            continue
        outcome = str(lesson.get("outcome") or "")
        if outcome in {"validation_failed", "oos_evaluated"}:
            return lesson
    return None


def _materially_more_evidence(current_samples, prior_lesson):
    if not prior_lesson:
        return True
    summary = prior_lesson.get("evidence_summary") or {}
    try:
        previous = int(summary.get("independent_samples_at_test") or 0)
    except (TypeError, ValueError):
        previous = 0
    current = max(0, int(current_samples or 0))
    if previous <= 0:
        return True
    return current >= max(previous + MATERIAL_SAMPLE_GROWTH_MIN, int(previous * MATERIAL_SAMPLE_GROWTH_RATIO))


def _effective_horizon(experiment, development_rows):
    target = str(experiment.get("target_horizon") or "both")
    if target in {"24h", "7d"}:
        return target
    dimension = str(experiment.get("dimension") or "unknown")
    group = str(experiment.get("group") or "unknown")
    counts = {}
    for horizon in ("24h", "7d"):
        counts[horizon] = sum(
            1 for row in development_rows
            if row.get("horizon") == horizon and _group_value(row, dimension) == group
        )
    return sorted(counts, key=lambda horizon: (-counts[horizon], horizon))[0]


def _nonnegative_int(value):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return 0
    return max(0, parsed)


def _multiple_testing_policy(memory):
    """Spend a bounded global alpha budget across an unbounded sequence of tests.

    alpha_i = alpha / (i * (i + 1)) and sum_i alpha_i <= alpha. This makes
    later OOS-opening decisions progressively harder rather than letting a huge
    hypothesis factory accumulate false discoveries by repeated testing.
    """
    prior_trials = _nonnegative_int((memory or {}).get("conclusive_trial_count"))
    trial_index = prior_trials + 1
    alpha_this_trial = FAMILYWISE_ALPHA / (trial_index * (trial_index + 1))
    z = NormalDist().inv_cdf(1.0 - alpha_this_trial / 2.0)
    return {
        "method": "sequential_alpha_spending_bonferroni_wilson",
        "familywise_alpha": FAMILYWISE_ALPHA,
        "prior_conclusive_trials": prior_trials,
        "trial_index": trial_index,
        "alpha_this_trial": round(alpha_this_trial, 10),
        "validation_confidence_z": round(z, 6),
        "requires_adjusted_lower_above_baseline_precision": True,
        "oos_sealed_pending_gate": True,
    }


def _metrics(rows, *, cost_pct, adjusted_z=1.96):
    total = len(rows)
    correct = sum(1 for row in rows if row.get("correct") is True)
    returns = []
    for row in rows:
        value = _finite(row.get("directional_return_pct"))
        if value is not None:
            returns.append(value - float(cost_pct))
    return {
        "samples": total,
        "correct": correct,
        "precision": round(correct / total, 4) if total else None,
        "precision_95pct_lower": round(wilson_lower_bound(correct, total), 4) if total else None,
        "precision_multiple_testing_lower": round(wilson_lower_bound(correct, total, z=float(adjusted_z)), 4) if total else None,
        "multiple_testing_z": round(float(adjusted_z), 6),
        "after_cost_expectancy_pct": round(sum(returns) / len(returns), 4) if len(returns) == total and total else None,
        "expectancy_sample_complete": bool(total and len(returns) == total),
    }


def _evaluate_frozen_filter(experiment, rows, horizon, *, cost_pct, adjusted_z=1.96):
    horizon_rows = [row for row in rows if row.get("horizon") == horizon]
    dimension = str(experiment.get("dimension") or "unknown")
    group = str(experiment.get("group") or "unknown")
    retained = [row for row in horizon_rows if _group_value(row, dimension) != group]
    baseline = _metrics(horizon_rows, cost_pct=cost_pct, adjusted_z=adjusted_z)
    filtered = _metrics(retained, cost_pct=cost_pct, adjusted_z=adjusted_z)
    coverage = round(len(retained) / len(horizon_rows), 4) if horizon_rows else 0.0
    lift = None
    if baseline["precision"] is not None and filtered["precision"] is not None:
        lift = round(filtered["precision"] - baseline["precision"], 4)
    return {
        "baseline": baseline,
        "filtered": filtered,
        "actionable_coverage": coverage,
        "precision_lift": lift,
        "abstained_samples": len(horizon_rows) - len(retained),
    }


def _passes_validation(evaluation, science_design):
    minimum_effect = (science_design or {}).get("minimum_effect_to_continue") or {}
    min_lift = float(minimum_effect.get("precision_absolute_improvement") or 0.02)
    min_samples = int((science_design or {}).get("minimum_evaluation_samples") or MIN_VALIDATION_SAMPLES)
    min_coverage = float((science_design or {}).get("minimum_actionable_coverage") or MIN_ACTIONABLE_COVERAGE)
    baseline = evaluation.get("baseline") or {}
    filtered = evaluation.get("filtered") or {}
    lift = evaluation.get("precision_lift")
    expectancy = filtered.get("after_cost_expectancy_pct")
    adjusted_lower = filtered.get("precision_multiple_testing_lower")
    baseline_precision = baseline.get("precision")
    confidence_pass = (
        adjusted_lower is not None
        and baseline_precision is not None
        and float(adjusted_lower) > float(baseline_precision)
    )
    return (
        int(filtered.get("samples") or 0) >= min_samples
        and lift is not None and float(lift) >= min_lift
        and float(evaluation.get("actionable_coverage") or 0.0) >= min_coverage
        and filtered.get("expectancy_sample_complete") is True
        and expectancy is not None and float(expectancy) > 0.0
        and confidence_pass
    )


def build_adaptive_accuracy_report(rows, memory=None, *, cost_pct=DEFAULT_ROUND_TRIP_COST_PCT):
    development, validation, untouched_oos = _chronological_splits(rows)
    diagnostics = learning_diagnostics(development)
    queue = build_quant_science_queue(diagnostics, memory)
    plan = build_heavy_dispatch_plan(queue)
    selected = (plan.get("selected") or [])[:1]
    multiple_testing = _multiple_testing_policy(memory)
    report = {
        "ok": True,
        "research_only": True,
        "trade_authority": False,
        "promotion_authority": False,
        "strategy_mutation_authority": False,
        "automatic_execution_authority": False,
        "round_trip_cost_pct": float(cost_pct),
        "split_policy": "60% development / 20% validation / 20% untouched OOS within each horizon using non-overlapping full-horizon resolved rows",
        "multiple_testing_policy": multiple_testing,
        "development_samples": len(development),
        "validation_samples_sealed": len(validation),
        "untouched_oos_samples_sealed": len(untouched_oos),
        "quant_science_queue": queue,
        "heavy_dispatch_plan": plan,
        "experiment": None,
        "oos_opened": False,
        "evidence_conclusion": "no_dispatchable_hypothesis" if not selected else "pending_validation",
        "memory_lesson": None,
    }
    if not selected:
        return report

    experiment_id = selected[0]["experiment_id"]
    experiment = next((row for row in queue.get("experiments") or [] if row.get("experiment_id") == experiment_id), None)
    if not experiment:
        report["evidence_conclusion"] = "dispatch_plan_missing_experiment"
        return report

    dimension = str(experiment.get("dimension") or "unknown")
    group = str(experiment.get("group") or "unknown")
    prior = _prior_conclusive_lesson(memory, dimension, group)
    if prior and not _materially_more_evidence(experiment.get("source_independent_samples"), prior):
        report["experiment"] = {"experiment_id": experiment_id, "dimension": dimension, "group": group, "status": "DEFERRED_REPEAT_NO_NEW_EVIDENCE"}
        report["evidence_conclusion"] = "deferred_repeat_no_material_new_evidence"
        return report

    horizon = _effective_horizon(experiment, development)
    adjusted_z = float(multiple_testing["validation_confidence_z"])
    validation_eval = _evaluate_frozen_filter(experiment, validation, horizon, cost_pct=cost_pct, adjusted_z=adjusted_z)
    validation_passed = _passes_validation(validation_eval, experiment.get("science_design") or {})
    result = {
        "experiment_id": experiment_id,
        "dimension": dimension,
        "group": group,
        "effective_horizon": horizon,
        "hypothesis": experiment.get("hypothesis"),
        "science_design": experiment.get("science_design"),
        "multiple_testing_policy": multiple_testing,
        "validation": validation_eval,
        "validation_passed": validation_passed,
        "untouched_oos": None,
        "status": "VALIDATION_PASSED_OOS_OPENED" if validation_passed else "VALIDATION_FAILED_OOS_CLOSED",
    }
    fingerprint = _lesson_fingerprint(dimension, group)
    if not validation_passed:
        report["experiment"] = result
        report["evidence_conclusion"] = "validation_failed"
        report["memory_lesson"] = {
            "fingerprint": fingerprint,
            "hypothesis": experiment.get("hypothesis"),
            "outcome": "validation_failed",
            "evidence_summary": {
                "experiment_id": experiment_id,
                "effective_horizon": horizon,
                "independent_samples_at_test": experiment.get("source_independent_samples"),
                "multiple_testing_policy": multiple_testing,
                "validation": validation_eval,
            },
            "recommended_next_test": "Do not repeat until materially more independent evidence exists or the hypothesis mechanism materially changes.",
            "reason_not_to_repeat": "Predeclared validation and sequential multiple-testing gate failed; untouched OOS remained sealed.",
        }
        return report

    # Only after validation passes may untouched OOS correctness/returns be inspected.
    oos_eval = _evaluate_frozen_filter(experiment, untouched_oos, horizon, cost_pct=cost_pct, adjusted_z=adjusted_z)
    result["untouched_oos"] = oos_eval
    report["experiment"] = result
    report["oos_opened"] = True
    report["evidence_conclusion"] = "oos_evaluated_research_only"
    report["memory_lesson"] = {
        "fingerprint": fingerprint,
        "hypothesis": experiment.get("hypothesis"),
        "outcome": "oos_evaluated",
        "evidence_summary": {
            "experiment_id": experiment_id,
            "effective_horizon": horizon,
            "independent_samples_at_test": experiment.get("source_independent_samples"),
            "multiple_testing_policy": multiple_testing,
            "validation": validation_eval,
            "untouched_oos": oos_eval,
        },
        "recommended_next_test": "If OOS is favorable, freeze the exact hypothesis/fingerprint and accumulate separate genuine forward shadow evidence; otherwise retire it.",
        "reason_not_to_repeat": "Untouched OOS has been consumed for this exact hypothesis and cannot be reused as fresh confirmation.",
    }
    return report
