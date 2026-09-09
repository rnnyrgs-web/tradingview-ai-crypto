"""Research-only economic meta-label / WAIT diagnostics.

This module asks a deliberately narrower question than the primary directional
signal: given a BUY/SELL forecast, did the forecast deliver positive directional
return after a fixed conservative round-trip cost, and are there pre-forecast
conditions associated with economically weak outcomes that deserve a restrictive
WAIT challenger experiment?

It never trains on untouched OOS, mutates production, or creates trade authority.
Candidate discovery is intended for development evidence only; canonical adaptive
validation remains responsible for validation/OOS opening and multiple-testing.
"""

from __future__ import annotations

from collections import defaultdict
from math import isfinite

from selective_precision import _independent_rows
from signal_development import objective_reference

DEFAULT_ROUND_TRIP_COST_PCT = 0.12
MIN_GROUP_SAMPLES = 12


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


def _group_value(row, dimension):
    if dimension == "score_band":
        return _score_band(row.get("score"))
    if dimension == "market_regime":
        return str(row.get("market_regime") or "unknown")
    if dimension == "direction":
        return str(row.get("direction") or "unknown")
    if dimension == "strategy_identity":
        return str(row.get("strategy_identity") or "unknown")
    return "unknown"


def _resolved(rows):
    return [
        row for row in (rows or [])
        if row.get("resolved_at") and isinstance(row.get("correct"), bool)
    ]


def _independent(rows):
    selected = []
    for horizon in ("24h", "7d"):
        selected.extend(_independent_rows(
            [row for row in _resolved(rows) if row.get("horizon") == horizon],
            horizon,
        ))
    return selected


def _economic_metrics(rows, *, cost_pct):
    after_cost = []
    correct = 0
    for row in rows:
        if row.get("correct") is True:
            correct += 1
        directional_return = _finite(row.get("directional_return_pct"))
        if directional_return is not None:
            after_cost.append(directional_return - float(cost_pct))
    total = len(rows)
    complete = bool(total and len(after_cost) == total)
    wins = sum(1 for value in after_cost if value > 0.0)
    losses = [value for value in after_cost if value <= 0.0]
    positive = [value for value in after_cost if value > 0.0]
    return {
        "samples": total,
        "directional_precision": round(correct / total, 4) if total else None,
        "after_cost_expectancy_pct": round(sum(after_cost) / total, 4) if complete else None,
        "after_cost_win_rate": round(wins / total, 4) if complete else None,
        "average_after_cost_win_pct": round(sum(positive) / len(positive), 4) if positive else None,
        "average_after_cost_loss_pct": round(sum(losses) / len(losses), 4) if losses else None,
        "economic_evidence_complete": complete,
    }


def build_meta_wait_diagnostics(rows, *, cost_pct=DEFAULT_ROUND_TRIP_COST_PCT, minimum_samples=MIN_GROUP_SAMPLES):
    """Return timestamp-safe, independent economic error groups for research discovery.

    Only non-overlapping full-horizon resolved rows contribute to diagnostics.
    The output proposes restrictive WAIT hypotheses; it does not decide or execute
    any production action.
    """
    independent = _independent(rows)
    dimensions = ("score_band", "market_regime", "direction", "strategy_identity")
    groups = []
    for dimension in dimensions:
        buckets = defaultdict(list)
        for row in independent:
            buckets[_group_value(row, dimension)].append(row)
        for group, bucket in buckets.items():
            metrics = _economic_metrics(bucket, cost_pct=cost_pct)
            ready = metrics["samples"] >= int(minimum_samples) and metrics["economic_evidence_complete"]
            expectancy = metrics["after_cost_expectancy_pct"]
            economic_harm = max(0.0, -float(expectancy)) if expectancy is not None else 0.0
            error_rate = 1.0 - float(metrics["directional_precision"] or 0.0)
            # Ranking only affects which research question is tested first. It has
            # no production authority and uses fixed, predeclared economics.
            priority = round(metrics["samples"] * (0.6 * error_rate + 0.4 * min(economic_harm, 1.0)), 4)
            groups.append({
                "dimension": dimension,
                "group": group,
                **metrics,
                "ready_for_research": ready,
                "economic_harm_pct": round(economic_harm, 4),
                "information_priority": priority if ready else 0.0,
                "hypothesis": (
                    f"Predeclared restrictive WAIT for {dimension}={group} may improve independent "
                    "after-cost precision/expectancy if this condition remains weak on validation."
                ),
                "requires_fresh_validation": True,
                "untouched_oos_reuse_allowed": False,
                "trade_authority": False,
                "promotion_authority": False,
            })
    groups.sort(key=lambda row: (-float(row["information_priority"]), -int(row["samples"]), row["dimension"], row["group"]))
    return {
        "ok": True,
        "research_only": True,
        "objective": objective_reference("meta-wait-economic-diagnostics", "learning_diagnostics"),
        "round_trip_cost_pct": float(cost_pct),
        "independent_samples": len(independent),
        "sample_policy": "non_overlapping_full_horizon_resolved_rows_only",
        "meta_label": "directional_return_pct_minus_fixed_round_trip_cost_gt_0",
        "groups": groups,
        "research_priorities": [row for row in groups if row["ready_for_research"]][:20],
        "trade_authority": False,
        "promotion_authority": False,
        "strategy_mutation_authority": False,
        "automatic_execution_authority": False,
    }
