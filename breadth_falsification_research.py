"""Chronological rejection-oriented falsifier for frozen DATA-BREADTH-001.

The feature is exactly the predeclared point-in-time cross-sectional 24h breadth
scalar. Historical universe membership must come from the repository's strict
point-in-time manifest and all forecast-cohort labels require exact timestamps.
No survivor substitution, nearest-neighbor matching, threshold search, or OOS
parameter tuning is permitted.
"""

from __future__ import annotations

import math

from config import BACKTEST_COST_BPS
from point_in_time_universe import filter_histories

HOUR_MS = 60 * 60 * 1000
WINDOW_MS = 24 * HOUR_MS
PRIMARY_HORIZONS = (24, 24 * 7)
DEFAULT_MIN_OOS_SAMPLES = 8
DEFAULT_MIN_ELIGIBLE_ASSETS = 15
COST_STRESS_MULTIPLIERS = (1.0, 2.0, 3.0)


def _snapshot_symbols_at(manifest, timestamp):
    if not isinstance(manifest, dict) or not manifest.get("valid"):
        return None
    ts = int(timestamp)
    for snapshot in manifest.get("snapshots") or []:
        start = int(snapshot["effective_from"].timestamp() * 1000)
        end = snapshot.get("effective_to")
        end_ms = int(end.timestamp() * 1000) if end is not None else None
        if ts < start:
            break
        if ts >= start and (end_ms is None or ts < end_ms):
            return sorted(str(symbol).upper() for symbol in snapshot["symbols"])
    return None


def _close_maps(histories):
    maps = {}
    timestamps = set()
    for symbol, rows in (histories or {}).items():
        by_ts = {}
        for row in rows or []:
            try:
                ts = int(row["ts"])
                close = float(row["close"])
            except (KeyError, TypeError, ValueError):
                return None, None
            if ts <= 0 or not math.isfinite(close) or close <= 0 or ts in by_ts:
                return None, None
            by_ts[ts] = close
            timestamps.add(ts)
        if by_ts:
            maps[str(symbol).upper()] = by_ts
    return maps, sorted(timestamps)


def _causal_examples(histories, manifest, horizon_hours, min_eligible_assets):
    filtered, gate = filter_histories(manifest, histories)
    if not gate.get("survivorship_safe"):
        return None, gate
    closes, timestamps = _close_maps(filtered)
    if closes is None:
        return None, {**gate, "reason": "malformed_or_duplicate_history_rows", "survivorship_safe": False}

    horizon_ms = int(horizon_hours) * HOUR_MS
    examples = []
    next_allowed_ts = None
    for ts in timestamps:
        if next_allowed_ts is not None and ts < next_allowed_ts:
            continue
        cohort = _snapshot_symbols_at(manifest, ts)
        if not cohort or len(cohort) < int(min_eligible_assets):
            continue

        trailing_returns = []
        label_returns = []
        label_complete = True
        for symbol in cohort:
            series = closes.get(symbol)
            if not series:
                label_complete = False
                break
            current = series.get(ts)
            future = series.get(ts + horizon_ms)
            if current is None or future is None:
                label_complete = False
                break
            label_returns.append(future / current - 1.0)
            prior = series.get(ts - WINDOW_MS)
            if prior is not None:
                trailing_returns.append(current / prior - 1.0)

        if not label_complete or len(label_returns) != len(cohort):
            continue
        if len(trailing_returns) < int(min_eligible_assets):
            continue

        positive = sum(1 for value in trailing_returns if value > 0)
        breadth = 2.0 * (positive / len(trailing_returns)) - 1.0
        future_return_bps = (sum(label_returns) / len(label_returns)) * 10000.0
        examples.append({
            "forecast_ts": ts,
            "outcome_ts": ts + horizon_ms,
            "breadth": breadth,
            "eligible_assets": len(cohort),
            "valid_trailing_assets": len(trailing_returns),
            "future_return_bps": future_return_bps,
        })
        next_allowed_ts = ts + horizon_ms
    return examples, gate


def _association_direction(examples):
    if len(examples) < 2:
        return None
    mean_x = sum(row["breadth"] for row in examples) / len(examples)
    mean_y = sum(row["future_return_bps"] for row in examples) / len(examples)
    covariance = sum(
        (row["breadth"] - mean_x) * (row["future_return_bps"] - mean_y)
        for row in examples
    )
    if covariance == 0:
        return None
    return 1 if covariance > 0 else -1


def _constant_direction(examples):
    if not examples:
        return None
    mean_return = sum(row["future_return_bps"] for row in examples) / len(examples)
    if mean_return == 0:
        return None
    return 1 if mean_return > 0 else -1


def _avg(values):
    return sum(values) / len(values) if values else None


def _stddev(values):
    if len(values) < 2:
        return None
    mean = _avg(values)
    return math.sqrt(sum((value - mean) ** 2 for value in values) / (len(values) - 1))


def _economic_metrics(net_values):
    wins = [value for value in net_values if value > 0]
    losses = [value for value in net_values if value < 0]
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else (float("inf") if gross_profit > 0 else None)
    avg_win = _avg(wins)
    avg_loss = abs(_avg(losses)) if losses else None
    payoff = avg_win / avg_loss if avg_win is not None and avg_loss not in (None, 0) else None

    equity = peak = max_drawdown = 0.0
    for value in net_values:
        equity += value
        peak = max(peak, equity)
        max_drawdown = max(max_drawdown, peak - equity)
    std = _stddev(net_values)
    mean = _avg(net_values)
    return {
        "avg_net_bps": mean,
        "cumulative_net_bps": sum(net_values),
        "profit_factor": profit_factor,
        "payoff_ratio": payoff,
        "win_rate": len(wins) / len(net_values) if net_values else None,
        "max_drawdown_bps": max_drawdown,
        "net_bps_stddev": std,
        "mean_to_std": mean / std if mean is not None and std not in (None, 0) else None,
    }


def evaluate_breadth_horizon(dataset, horizon_hours, cost_bps=BACKTEST_COST_BPS,
                             train_fraction=0.6,
                             min_oos_samples=DEFAULT_MIN_OOS_SAMPLES,
                             min_eligible_assets=DEFAULT_MIN_ELIGIBLE_ASSETS):
    if not dataset.get("research_only") or dataset.get("candidate_id") != "DATA-BREADTH-001":
        return {"research_only": True, "available": False, "reason": "invalid_research_dataset"}
    if not dataset.get("available"):
        return {"research_only": True, "available": False, "reason": dataset.get("reason") or "dataset_unavailable"}

    manifest = dataset.get("universe_manifest") or {}
    histories = dataset.get("histories") or {}
    examples, gate = _causal_examples(histories, manifest, horizon_hours, min_eligible_assets)
    if examples is None:
        return {
            "research_only": True,
            "available": False,
            "reason": gate.get("reason") or "point_in_time_universe_not_defensible",
            "point_in_time_universe": gate,
        }
    if len(examples) < 4:
        return {
            "research_only": True,
            "available": False,
            "reason": "insufficient_non_overlapping_causal_samples",
            "sample_count": len(examples),
            "point_in_time_universe": gate,
        }

    split = int(len(examples) * float(train_fraction))
    split = max(2, min(split, len(examples) - 2))
    train, oos = examples[:split], examples[split:]
    if len(oos) < int(min_oos_samples):
        return {
            "research_only": True,
            "available": False,
            "reason": "insufficient_oos_samples_before_scoring",
            "sample_count": len(examples),
            "train_samples": len(train),
            "oos_samples": len(oos),
            "minimum_oos_samples": int(min_oos_samples),
            "point_in_time_universe": gate,
        }

    direction = _association_direction(train)
    baseline_direction = _constant_direction(train)
    if direction is None or baseline_direction is None:
        return {
            "research_only": True,
            "available": False,
            "reason": "no_training_only_direction",
            "sample_count": len(examples),
            "train_samples": len(train),
            "oos_samples": len(oos),
            "point_in_time_universe": gate,
        }

    scored = []
    for row in oos:
        signed_feature = direction * row["breadth"]
        if signed_feature == 0:
            continue
        signal = 1 if signed_feature > 0 else -1
        scored.append({
            **row,
            "gross_bps": signal * row["future_return_bps"],
            "baseline_gross_bps": baseline_direction * row["future_return_bps"],
        })
    if len(scored) < int(min_oos_samples):
        return {
            "research_only": True,
            "available": False,
            "reason": "insufficient_oos_nonzero_feature_samples",
            "sample_count": len(examples),
            "train_samples": len(train),
            "oos_samples": len(scored),
            "minimum_oos_samples": int(min_oos_samples),
            "point_in_time_universe": gate,
        }

    stress = {}
    for multiple in COST_STRESS_MULTIPLIERS:
        stressed_cost = float(cost_bps) * multiple
        net = [row["gross_bps"] - stressed_cost for row in scored]
        baseline_net = [row["baseline_gross_bps"] - stressed_cost for row in scored]
        metrics = _economic_metrics(net)
        baseline_metrics = _economic_metrics(baseline_net)
        stress[f"{int(multiple)}x"] = {
            "cost_bps_round_trip": stressed_cost,
            **metrics,
            "baseline_avg_net_bps": baseline_metrics["avg_net_bps"],
            "baseline_profit_factor": baseline_metrics["profit_factor"],
            "incremental_vs_baseline_bps": metrics["avg_net_bps"] - baseline_metrics["avg_net_bps"],
            "positive_after_cost": metrics["avg_net_bps"] > 0,
        }

    canonical = stress["1x"]
    mid = len(scored) // 2
    halves = [scored[:mid], scored[mid:]] if mid else [scored]
    half_avg_net = [
        _avg([row["gross_bps"] - float(cost_bps) for row in half])
        for half in halves if half
    ]
    stable_oos_halves = len(half_avg_net) == 2 and all(value > 0 for value in half_avg_net)
    survives_cost_stress = all(stress[key]["positive_after_cost"] for key in ("1x", "2x", "3x"))
    incremental_positive = canonical["incremental_vs_baseline_bps"] > 0

    return {
        "research_only": True,
        "available": True,
        "candidate_id": "DATA-BREADTH-001",
        "horizon_hours": int(horizon_hours),
        "chronological_split": "60_percent_train_40_percent_oos",
        "non_overlapping": True,
        "point_in_time_universe": gate,
        "feature_window_hours": 24,
        "minimum_eligible_assets": int(min_eligible_assets),
        "training_only_direction": direction,
        "training_only_baseline_direction": baseline_direction,
        "threshold_tuning": False,
        "sample_count": len(examples),
        "train_samples": len(train),
        "oos_samples": len(scored),
        "minimum_oos_samples": int(min_oos_samples),
        "oos_directional_hit_rate": sum(1 for row in scored if row["gross_bps"] > 0) / len(scored),
        "cost_stress": stress,
        "oos_half_avg_net_bps": half_avg_net,
        "stable_positive_oos_halves": stable_oos_halves,
        "survives_3x_cost_stress": survives_cost_stress,
        "incremental_after_cost_vs_baseline_positive": incremental_positive,
        "stage1_pass": bool(canonical["positive_after_cost"] and incremental_positive and survives_cost_stress and stable_oos_halves),
        "promotion_authority": False,
        "production_authority": False,
        "note": "Rejection-oriented stage 1 only; liquidity/universe stability, multiple-testing, untouched-OOS and genuine-forward gates remain mandatory.",
    }


def evaluate_primary_horizons(dataset, cost_bps=BACKTEST_COST_BPS):
    return {
        "research_only": True,
        "candidate_id": "DATA-BREADTH-001",
        "results": {
            str(hours): evaluate_breadth_horizon(dataset, hours, cost_bps=cost_bps)
            for hours in PRIMARY_HORIZONS
        },
        "promotion_authority": False,
        "production_authority": False,
    }
