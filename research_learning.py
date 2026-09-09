"""Research-only learning diagnostics for resolved prediction outcomes.

This module turns genuine resolved forward rows into reusable diagnostics and
prioritized research questions. It never changes strategy parameters, creates
trade authority, or promotes a strategy. Its purpose is to help both Python
research workers and AI development cycles learn from prior outcomes instead
of repeating the same mistakes blindly.
"""

from __future__ import annotations

from collections import defaultdict
from math import isfinite

MIN_GROUP_SAMPLES = 12


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
    return [row for row in (rows or []) if isinstance(row.get("correct"), bool)]


def _group_metrics(rows, key_fn, minimum_samples=MIN_GROUP_SAMPLES):
    buckets = defaultdict(list)
    for row in rows:
        buckets[str(key_fn(row) or "unknown")].append(row)

    out = []
    for key, group in buckets.items():
        total = len(group)
        correct = sum(1 for row in group if row.get("correct") is True)
        wrong = total - correct
        avg_return = None
        returns = []
        for row in group:
            try:
                value = float(row.get("directional_return_pct"))
            except (TypeError, ValueError):
                continue
            if isfinite(value):
                returns.append(value)
        if returns:
            avg_return = round(sum(returns) / len(returns), 4)
        out.append({
            "group": key,
            "samples": total,
            "correct": correct,
            "wrong": wrong,
            "precision": round(correct / total, 4) if total else None,
            "wrong_rate": round(wrong / total, 4) if total else None,
            "average_directional_return_pct": avg_return,
            "ready_for_diagnostic": total >= int(minimum_samples),
        })
    return sorted(out, key=lambda row: (-row["samples"], row["group"]))


def _priority(metric, dimension):
    if not metric.get("ready_for_diagnostic"):
        return None
    wrong_rate = metric.get("wrong_rate")
    if wrong_rate is None:
        return None
    # Information priority, not production authority. Large repeatedly-wrong
    # groups get investigated first; this does not optimize on a holdout.
    score = round(float(wrong_rate) * min(int(metric["samples"]), 100), 4)
    return {
        "dimension": dimension,
        "group": metric["group"],
        "samples": metric["samples"],
        "wrong_rate": metric["wrong_rate"],
        "priority_score": score,
        "research_question": (
            f"Why does {dimension}={metric['group']} show a {metric['wrong_rate']:.1%} wrong-signal rate, "
            "and can a predeclared restrictive filter or challenger improve after-cost OOS/forward results?"
        ),
        "requires_new_validation": True,
        "trade_authority": False,
        "promotion_authority": False,
    }


def learning_diagnostics(rows, *, minimum_samples=MIN_GROUP_SAMPLES):
    """Build reusable error diagnostics from genuine resolved prediction rows."""
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
    priorities.sort(key=lambda row: (-row["priority_score"], -row["samples"], row["dimension"], row["group"]))

    total = len(resolved)
    correct = sum(1 for row in resolved if row.get("correct") is True)
    return {
        "ok": True,
        "research_only": True,
        "trade_authority": False,
        "promotion_authority": False,
        "automatic_strategy_mutation": False,
        "resolved_samples": total,
        "baseline_precision": round(correct / total, 4) if total else None,
        "minimum_group_samples": int(minimum_samples),
        "diagnostics": dimensions,
        "research_priorities": priorities[:20],
        "learning_policy": (
            "Use resolved outcomes to generate falsifiable research questions and reusable lessons. "
            "Never tune production directly on these diagnostics; every proposed change must be predeclared and pass fresh chronological/OOS/forward validation."
        ),
    }
