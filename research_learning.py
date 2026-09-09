"""Research-only learning diagnostics for genuinely resolved prediction outcomes.

The module turns immutable resolved forward rows into reusable diagnostics and
prioritized research questions. It never mutates strategy parameters, creates
trade authority, or promotes a strategy.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from math import isfinite

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


def _independent_window_count(rows):
    """Count conservative non-overlapping full-horizon windows from ledger chronology.

    Production prediction_ledger has no forecast_at/created_at column. due_at is
    immutable and written as forecast origin + horizon, so origin is reconstructed
    as due_at - the row's declared 24h/7d span. Rows that are unresolved before
    due time, malformed, or have an unknown horizon cannot contribute.
    """
    intervals = []
    for row in rows:
        span = HORIZON_SPAN.get(row.get("horizon"))
        due_at = _timestamp(row.get("due_at"))
        resolved_at = _timestamp(row.get("resolved_at"))
        if span is None or due_at is None or resolved_at is None or resolved_at < due_at:
            continue
        origin = due_at - span
        intervals.append((origin, due_at))
    intervals.sort(key=lambda item: (item[0], item[1]))
    count = 0
    covered_until = None
    for origin, due_at in intervals:
        if covered_until is not None and origin < covered_until:
            continue
        count += 1
        covered_until = due_at
    return count


def _group_metrics(rows, key_fn, minimum_samples=MIN_GROUP_SAMPLES):
    buckets = defaultdict(list)
    for row in rows:
        buckets[str(key_fn(row) or "unknown")].append(row)
    out = []
    for key, group in buckets.items():
        total = len(group)
        independent_samples = _independent_window_count(group)
        correct = sum(1 for row in group if row.get("correct") is True)
        wrong = total - correct
        returns = []
        for row in group:
            try:
                value = float(row.get("directional_return_pct"))
            except (TypeError, ValueError):
                continue
            if isfinite(value):
                returns.append(value)
        out.append({
            "group": key,
            "samples": total,
            "independent_samples": independent_samples,
            "correct": correct,
            "wrong": wrong,
            "precision": round(correct / total, 4) if total else None,
            "wrong_rate": round(wrong / total, 4) if total else None,
            "average_directional_return_pct": round(sum(returns) / len(returns), 4) if returns else None,
            "ready_for_diagnostic": independent_samples >= int(minimum_samples),
            "raw_rows_are_independent": False,
        })
    return sorted(out, key=lambda row: (-row["independent_samples"], -row["samples"], row["group"]))


def _priority(metric, dimension):
    if not metric.get("ready_for_diagnostic") or metric.get("wrong_rate") is None:
        return None
    score = round(float(metric["wrong_rate"]) * min(int(metric["independent_samples"]), 100), 4)
    return {
        "dimension": dimension,
        "group": metric["group"],
        "samples": metric["samples"],
        "independent_samples": metric["independent_samples"],
        "wrong_rate": metric["wrong_rate"],
        "priority_score": score,
        "research_question": (
            f"Why does {dimension}={metric['group']} show a {metric['wrong_rate']:.1%} wrong-signal rate across "
            f"{metric['independent_samples']} non-overlapping forecast windows, and can a predeclared restrictive filter "
            "or challenger improve after-cost OOS/forward results?"
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
    priorities.sort(
        key=lambda row: (
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
        "trade_authority": False,
        "promotion_authority": False,
        "automatic_strategy_mutation": False,
        "resolved_samples": total,
        "baseline_precision": round(correct / total, 4) if total else None,
        "minimum_group_samples": int(minimum_samples),
        "sample_sufficiency_basis": "non_overlapping_full_horizon_windows_reconstructed_from_due_at",
        "raw_precision_descriptive_only": True,
        "diagnostics": dimensions,
        "research_priorities": priorities[:20],
        "learning_policy": (
            "Resolved outcomes generate falsifiable research questions only. Repeated scans and cross-sectional rows inside an overlapping full-horizon interval "
            "do not increase sample sufficiency. Production may not be tuned directly from these diagnostics; every proposed change must be predeclared and pass "
            "fresh chronological/OOS/forward validation."
        ),
    }
