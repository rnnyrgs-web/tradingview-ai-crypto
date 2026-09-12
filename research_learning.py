"""Research-only learning diagnostics for genuinely resolved prediction outcomes.

The module turns immutable resolved forward rows into reusable diagnostics and
prioritized research questions. It never mutates strategy parameters, creates
trade authority, or promotes a strategy.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from math import isfinite

from signal_development import build_signal_quality_scorecard, objective_reference

MIN_GROUP_SAMPLES = 12
HORIZON_SPAN = {"24h": timedelta(hours=24), "7d": timedelta(days=7)}


def _score_band(value):
    try:
        score = float(value)
    except (TypeError, ValueError):
        return "unknown"
    if not isfinite(score):
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


def _resolved_rows(rows):
    return [row for row in (rows or []) if row.get("resolved_at") and isinstance(row.get("correct"), bool)]


def _timestamp(value):
    if isinstance(value, datetime):
        return value
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip().replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _independent_window_rows(rows):
    intervals = []
    for row in rows:
        span = HORIZON_SPAN.get(row.get("horizon"))
        due_at = _timestamp(row.get("due_at"))
        resolved_at = _timestamp(row.get("resolved_at"))
        if span is None or due_at is None or resolved_at is None or resolved_at < due_at:
            continue
        origin = due_at - span
        intervals.append((origin, due_at, row))
    intervals.sort(key=lambda item: (item[0], item[1]))
    selected = []
    covered_until = None
    for origin, due_at, row in intervals:
        if covered_until is not None and origin < covered_until:
            continue
        selected.append(row)
        covered_until = due_at
    return selected


def _independent_window_count(rows):
    return len(_independent_window_rows(rows))


def _finite_values(rows, field):
    values = []
    for row in rows:
        try:
            value = float(row.get(field))
        except (TypeError, ValueError):
            continue
        if isfinite(value):
            values.append(value)
    return values


def _group_metrics(rows, key_fn, minimum_samples=MIN_GROUP_SAMPLES):
    buckets = defaultdict(list)
    for row in rows:
        buckets[str(key_fn(row) or "unknown")].append(row)
    out = []
    for key, group in buckets.items():
        total = len(group)
        independent_rows = _independent_window_rows(group)
        independent_samples = len(independent_rows)
        correct = sum(1 for row in group if row.get("correct") is True)
        wrong = total - correct
        directional_returns = _finite_values(group, "directional_return_pct")
        after_cost_returns = _finite_values(independent_rows, "after_cost_return_pct")
        average_after_cost = (
            sum(after_cost_returns) / len(after_cost_returns) if after_cost_returns else None
        )
        economic_harm = (
            max(0.0, -average_after_cost) * len(after_cost_returns)
            if average_after_cost is not None
            else 0.0
        )
        out.append({
            "group": key,
            "samples": total,
            "independent_samples": independent_samples,
            "correct": correct,
            "wrong": wrong,
            "precision": round(correct / total, 4) if total else None,
            "wrong_rate": round(wrong / total, 4) if total else None,
            "average_directional_return_pct": round(sum(directional_returns) / len(directional_returns), 4) if directional_returns else None,
            "average_after_cost_return_pct": round(average_after_cost, 4) if average_after_cost is not None else None,
            "after_cost_independent_observations": len(after_cost_returns),
            "economic_harm_score_pct": round(economic_harm, 4),
            "ready_for_diagnostic": independent_samples >= int(minimum_samples),
            "raw_rows_are_independent": False,
            "economic_priority_uses_independent_rows": True,
        })
    return sorted(out, key=lambda row: (-row["independent_samples"], -row["samples"], row["group"]))


def _priority(metric, dimension):
    if not metric.get("ready_for_diagnostic") or metric.get("wrong_rate") is None:
        return None
    accuracy_score = round(float(metric["wrong_rate"]) * min(int(metric["independent_samples"]), 100), 4)
    economic_harm = float(metric.get("economic_harm_score_pct") or 0.0)
    horizon = metric["group"] if dimension == "horizon" and metric["group"] in HORIZON_SPAN else "both"
    question = (
        f"Why does {dimension}={metric['group']} show a {metric['wrong_rate']:.1%} wrong-signal rate across "
        f"{metric['independent_samples']} non-overlapping forecast windows, and can a predeclared restrictive filter "
        "or challenger improve genuine after-cost OOS/forward profitability?"
    )
    return {
        "dimension": dimension,
        "group": metric["group"],
        "samples": metric["samples"],
        "independent_samples": metric["independent_samples"],
        "wrong_rate": metric["wrong_rate"],
        "priority_score": accuracy_score,
        "average_after_cost_return_pct": metric.get("average_after_cost_return_pct"),
        "after_cost_independent_observations": metric.get("after_cost_independent_observations", 0),
        "economic_harm_score_pct": economic_harm,
        "research_question": question,
        "hypothesis": question,
        "predicted_mechanism": f"A repeatable economic-loss or error condition in {dimension}={metric['group']} may identify a restrictive abstention rule or independent challenger signal.",
        "target_horizon": horizon,
        "expected_signal_quality_effect": "Increase after-cost expectancy first; improve genuine BUY/SELL precision or WAIT quality second.",
        "evidence_needed": ["independent non-overlapping resolved forecasts", "chronological backtest", "untouched OOS", "genuine forward challenger evidence"],
        "falsification_criteria": ["no stable improvement after costs", "effect disappears under robustness or independent OOS", "benefit requires post-outcome threshold selection"],
        "chronological_oos_requirements": ["purged chronological train/validation", "untouched OOS not used for tuning", "genuine forward confirmation separated from historical/OOS"],
        "realistic_cost_treatment": ["fees, spread and slippage applied before expectancy claim"],
        "independent_sample_requirements": [f"at least {MIN_GROUP_SAMPLES} non-overlapping full-horizon windows before diagnostic readiness"],
        "status": "HYPOTHESIS_FROM_RESOLVED_ERROR",
        "result": None,
        "evidence_conclusion": "unresolved",
        "requires_new_validation": True,
        "trade_authority": False,
        "promotion_authority": False,
    }


def learning_diagnostics(rows, *, minimum_samples=MIN_GROUP_SAMPLES):
    """Build reusable profitability-first diagnostics from genuine resolved prediction rows."""
    resolved = _resolved_rows(rows)
    dimensions = {
        "horizon": _group_metrics(resolved, lambda r: r.get("horizon"), minimum_samples),
        "market_regime": _group_metrics(resolved, lambda r: r.get("market_regime"), minimum_samples),
        "direction": _group_metrics(resolved, lambda r: r.get("direction"), minimum_samples),
        "score_band": _group_metrics(resolved, lambda r: _score_band(r.get("score")), minimum_samples),
        "strategy_identity": _group_metrics(resolved, lambda r: r.get("strategy_identity"), minimum_samples),
    }
    priorities = []
    for dimension, metrics in dimensions.items():
        for metric in metrics:
            item = _priority(metric, dimension)
            if item:
                priorities.append(item)
    priorities.sort(
        key=lambda row: (
            -float(row.get("economic_harm_score_pct") or 0.0),
            -row["priority_score"],
            -row["independent_samples"],
            -row["samples"],
            row["dimension"],
            row["group"],
        )
    )
    total = len(resolved)
    correct = sum(1 for row in resolved if row.get("correct") is True)
    return {
        "ok": True,
        "research_only": True,
        "objective": objective_reference("learning-diagnostics", "learning_diagnostics"),
        "signal_quality_scorecard": build_signal_quality_scorecard(resolved),
        "trade_authority": False,
        "promotion_authority": False,
        "automatic_strategy_mutation": False,
        "resolved_samples": total,
        "baseline_precision": round(correct / total, 4) if total else None,
        "minimum_group_samples": int(minimum_samples),
        "sample_sufficiency_basis": "non_overlapping_full_horizon_windows_reconstructed_from_due_at",
        "raw_precision_descriptive_only": True,
        "economic_priority_basis": "independent_after_cost_expectancy_loss_first_then_wrong_signal_rate",
        "diagnostics": dimensions,
        "research_priorities": priorities[:20],
        "learning_policy": (
            "Resolved outcomes generate falsifiable research questions only. Economic-loss severity from independent non-overlapping full-horizon rows ranks diagnostics before wrong-signal rate, so accuracy cannot outrank known after-cost losses. Repeated scans and overlapping rows do not increase economic sample sufficiency. Production may not be tuned directly from these diagnostics; every proposed change must be predeclared and pass fresh chronological/OOS/forward validation."
        ),
    }
