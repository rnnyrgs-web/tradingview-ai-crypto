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
COST_STRESS_MULTIPLIERS = (1.0, 1.5, 2.0, 3.0)
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


def _independent_by_horizon(rows):
    out = {}
    for horizon in ("24h", "7d"):
        out[horizon] = _independent_rows(
            [row for row in _resolved(rows) if row.get("horizon") == horizon],
            horizon,
        )
    return out


def _economic_metrics(rows, *, cost_pct):
    raw_returns = []
    correct = 0
    for row in rows:
        if row.get("correct") is True:
            correct += 1
        directional_return = _finite(row.get("directional_return_pct"))
        if directional_return is not None:
            raw_returns.append(directional_return)
    total = len(rows)
    complete = bool(total and len(raw_returns) == total)
    base_after_cost = [value - float(cost_pct) for value in raw_returns] if complete else []
    wins = sum(1 for value in base_after_cost if value > 0.0)
    losses = [value for value in base_after_cost if value <= 0.0]
    positive = [value for value in base_after_cost if value > 0.0]
    stress = {}
    if complete:
        for multiplier in COST_STRESS_MULTIPLIERS:
            stressed = [value - float(cost_pct) * multiplier for value in raw_returns]
            stress[f"{multiplier:g}x"] = round(sum(stressed) / total, 4)
    return {
        "samples": total,
        "directional_precision": round(correct / total, 4) if total else None,
        "after_cost_expectancy_pct": stress.get("1x") if complete else None,
        "after_cost_win_rate": round(wins / total, 4) if complete else None,
        "average_after_cost_win_pct": round(sum(positive) / len(positive), 4) if positive else None,
        "average_after_cost_loss_pct": round(sum(losses) / len(losses), 4) if losses else None,
        "cost_stress_expectancy_pct": stress,
        "economic_evidence_complete": complete,
    }


def build_meta_wait_diagnostics(rows, *, cost_pct=DEFAULT_ROUND_TRIP_COST_PCT, minimum_samples=MIN_GROUP_SAMPLES):
    """Return timestamp-safe, independent economic error groups for research discovery.

    Only non-overlapping full-horizon resolved rows contribute to diagnostics.
    Horizons are never pooled: 24h and 7d economic behavior can differ materially.
    The output proposes restrictive WAIT hypotheses; it does not decide or execute
    any production action.
    """
    by_horizon = _independent_by_horizon(rows)
    dimensions = ("score_band", "market_regime", "direction", "strategy_identity")
    groups = []
    for horizon, independent in by_horizon.items():
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
                priority = round(metrics["samples"] * (0.6 * error_rate + 0.4 * min(economic_harm, 1.0)), 4)
                groups.append({
                    "horizon": horizon,
                    "dimension": dimension,
                    "group": group,
                    **metrics,
                    "ready_for_research": ready,
                    "economic_harm_pct": round(economic_harm, 4),
                    "information_priority": priority if ready else 0.0,
                    "hypothesis": (
                        f"Predeclared restrictive WAIT for {horizon} {dimension}={group} may improve independent "
                        "after-cost precision/expectancy if this condition remains weak on validation."
                    ),
                    "requires_fresh_validation": True,
                    "untouched_oos_reuse_allowed": False,
                    "trade_authority": False,
                    "promotion_authority": False,
                })
    groups.sort(key=lambda row: (-float(row["information_priority"]), -int(row["samples"]), row["horizon"], row["dimension"], row["group"]))
    independent_total = sum(len(items) for items in by_horizon.values())
    return {
        "ok": True,
        "research_only": True,
        "objective": objective_reference("meta-wait-economic-diagnostics", "learning_diagnostics"),
        "round_trip_cost_pct": float(cost_pct),
        "cost_stress_multipliers": list(COST_STRESS_MULTIPLIERS),
        "independent_samples": independent_total,
        "independent_samples_by_horizon": {horizon: len(items) for horizon, items in by_horizon.items()},
        "sample_policy": "non_overlapping_full_horizon_resolved_rows_separate_by_horizon",
        "meta_label": "directional_return_pct_minus_fixed_round_trip_cost_gt_0",
        "groups": groups,
        "research_priorities": [row for row in groups if row["ready_for_research"]][:20],
        "trade_authority": False,
        "promotion_authority": False,
        "strategy_mutation_authority": False,
        "automatic_execution_authority": False,
    }
