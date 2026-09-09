"""Research-only regime x strategy routing diagnostics from resolved forecasts.

The router is deliberately restrictive and evidence-first. It studies genuine
resolved prediction-ledger outcomes using non-overlapping full-horizon rows,
freezes chronology into development/validation/untouched-OOS partitions, and
uses only development + validation outcomes to identify regime/strategy pairs
worth either prospective shadow routing research or restrictive WAIT research.

Untouched OOS outcomes are never scored here. This module has no production,
strategy-mutation, promotion, or trade authority.
"""

from __future__ import annotations

from collections import defaultdict
from math import isfinite

from selective_precision import _independent_rows
from signal_development import objective_reference

DEFAULT_ROUND_TRIP_COST_PCT = 0.12
MIN_DEVELOPMENT_SAMPLES = 6
MIN_VALIDATION_SAMPLES = 4


def _finite(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if isfinite(number) else None


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


def _split(rows):
    """Deterministic 60/20/20 chronological split; caller must keep OOS sealed."""
    n = len(rows)
    if not n:
        return [], [], []
    dev_end = max(1, int(n * 0.60))
    val_end = max(dev_end, int(n * 0.80))
    if n >= 3:
        val_end = min(n - 1, max(dev_end + 1, val_end))
    return rows[:dev_end], rows[dev_end:val_end], rows[val_end:]


def _pair(row):
    return (
        str(row.get("market_regime") or "unknown"),
        str(row.get("strategy_identity") or "unknown"),
    )


def _metrics(rows, *, cost_pct):
    after_cost = []
    correct = 0
    for row in rows:
        if row.get("correct") is True:
            correct += 1
        value = _finite(row.get("directional_return_pct"))
        if value is not None:
            after_cost.append(value - float(cost_pct))
    total = len(rows)
    complete = bool(total and len(after_cost) == total)
    return {
        "samples": total,
        "directional_precision": round(correct / total, 4) if total else None,
        "after_cost_expectancy_pct": round(sum(after_cost) / total, 4) if complete else None,
        "after_cost_win_rate": round(sum(1 for value in after_cost if value > 0.0) / total, 4) if complete else None,
        "economic_evidence_complete": complete,
    }


def _baseline(rows, *, cost_pct):
    return _metrics(rows, cost_pct=cost_pct)


def _candidate_status(dev, val, baseline_val):
    if not dev["economic_evidence_complete"] or not val["economic_evidence_complete"]:
        return "INSUFFICIENT_ECONOMIC_EVIDENCE"
    if dev["samples"] < MIN_DEVELOPMENT_SAMPLES or val["samples"] < MIN_VALIDATION_SAMPLES:
        return "INSUFFICIENT_INDEPENDENT_SAMPLES"
    dev_exp = float(dev["after_cost_expectancy_pct"])
    val_exp = float(val["after_cost_expectancy_pct"])
    val_precision = val["directional_precision"]
    baseline_precision = baseline_val.get("directional_precision")
    if dev_exp > 0.0 and val_exp > 0.0 and val_precision is not None and baseline_precision is not None and float(val_precision) >= float(baseline_precision):
        return "PROSPECTIVE_SHADOW_ROUTER_CANDIDATE"
    if dev_exp <= 0.0 and val_exp <= 0.0:
        return "RESTRICTIVE_WAIT_CANDIDATE"
    return "NO_STABLE_ROUTING_EVIDENCE"


def build_regime_strategy_router(rows, *, cost_pct=DEFAULT_ROUND_TRIP_COST_PCT):
    """Build development/validation regime-strategy diagnostics with sealed OOS."""
    by_horizon = _independent_by_horizon(rows)
    horizons = {}
    total_oos_sealed = 0
    for horizon, independent in by_horizon.items():
        development, validation, untouched_oos = _split(independent)
        total_oos_sealed += len(untouched_oos)
        development_buckets = defaultdict(list)
        validation_buckets = defaultdict(list)
        pairs = set()
        for row in development:
            key = _pair(row)
            development_buckets[key].append(row)
            pairs.add(key)
        for row in validation:
            key = _pair(row)
            validation_buckets[key].append(row)
            pairs.add(key)

        validation_baseline = _baseline(validation, cost_pct=cost_pct)
        pair_reports = []
        for regime, strategy_identity in sorted(pairs):
            dev_metrics = _metrics(development_buckets[(regime, strategy_identity)], cost_pct=cost_pct)
            val_metrics = _metrics(validation_buckets[(regime, strategy_identity)], cost_pct=cost_pct)
            status = _candidate_status(dev_metrics, val_metrics, validation_baseline)
            pair_reports.append({
                "market_regime": regime,
                "strategy_identity": strategy_identity,
                "development": dev_metrics,
                "validation": val_metrics,
                "candidate_status": status,
                "requires_untouched_oos": status in {"PROSPECTIVE_SHADOW_ROUTER_CANDIDATE", "RESTRICTIVE_WAIT_CANDIDATE"},
                "requires_sequential_multiple_testing": True,
                "requires_genuine_forward_replication": True,
                "trade_authority": False,
                "promotion_authority": False,
            })
        pair_reports.sort(key=lambda row: (
            0 if row["candidate_status"] == "RESTRICTIVE_WAIT_CANDIDATE" else 1 if row["candidate_status"] == "PROSPECTIVE_SHADOW_ROUTER_CANDIDATE" else 2,
            -int(row["validation"]["samples"]),
            row["market_regime"],
            row["strategy_identity"],
        ))
        horizons[horizon] = {
            "independent_samples": len(independent),
            "development_samples": len(development),
            "validation_samples": len(validation),
            "untouched_oos_samples_sealed": len(untouched_oos),
            "validation_baseline": validation_baseline,
            "pairs": pair_reports,
        }

    return {
        "ok": True,
        "research_only": True,
        "objective": objective_reference("regime-strategy-router", "learning_diagnostics"),
        "round_trip_cost_pct": float(cost_pct),
        "split_policy": "60% development / 20% validation / 20% untouched OOS per horizon after non-overlapping full-horizon selection",
        "untouched_oos_outcomes_scored": False,
        "untouched_oos_samples_sealed": total_oos_sealed,
        "horizons": horizons,
        "research_policy": "Candidate status is discovery evidence only. Untouched OOS remains sealed here; any candidate must enter canonical sequential multiple-testing, untouched-OOS, robustness, point-in-time, execution-cost and genuine-forward gates before any promotion path exists.",
        "trade_authority": False,
        "promotion_authority": False,
        "strategy_mutation_authority": False,
        "automatic_execution_authority": False,
    }
