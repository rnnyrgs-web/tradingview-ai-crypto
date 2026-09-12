"""Chronological rejection-oriented falsifier for frozen DATA-FUNDING-001.

The feature is exactly the sum of already-realized OKX funding rates in the
preceding 24 hours, expressed in bps. Association sign and constant-direction
baseline are learned only from the chronological training segment and frozen
before OOS scoring. No OOS threshold search is performed.
"""

from config import BACKTEST_COST_BPS

HOUR_MS = 60 * 60 * 1000
WINDOW_MS = 24 * HOUR_MS
PRIMARY_HORIZONS = (24, 24 * 7)
DEFAULT_MIN_OOS_SAMPLES = 8
COST_STRESS_MULTIPLIERS = (1.0, 2.0, 3.0)


def _causal_examples(dataset, horizon_hours):
    funding = sorted(
        (int(p["ts"]), float(p["value"]))
        for p in (dataset.get("funding_points") or [])
    )
    index = {int(p["ts"]): float(p["value"]) for p in dataset.get("index_points") or []}
    horizon_ms = int(horizon_hours) * HOUR_MS
    examples = []
    next_allowed_ts = None

    for ts in sorted(index):
        if next_allowed_ts is not None and ts < next_allowed_ts:
            continue
        future_ts = ts + horizon_ms
        if future_ts not in index or index[ts] <= 0 or index[future_ts] <= 0:
            continue
        window_start = ts - WINDOW_MS
        realized = [rate for fts, rate in funding if window_start < fts <= ts]
        if not realized:
            continue
        feature_bps = 10000.0 * sum(realized)
        forward_return_bps = (index[future_ts] / index[ts] - 1.0) * 10000.0
        examples.append({
            "forecast_ts": ts,
            "outcome_ts": future_ts,
            "funding_pressure_bps": feature_bps,
            "funding_observations": len(realized),
            "future_return_bps": forward_return_bps,
        })
        next_allowed_ts = future_ts
    return examples


def _association_direction(examples):
    if len(examples) < 2:
        return None
    mean_x = sum(x["funding_pressure_bps"] for x in examples) / len(examples)
    mean_y = sum(x["future_return_bps"] for x in examples) / len(examples)
    covariance = sum(
        (x["funding_pressure_bps"] - mean_x) * (x["future_return_bps"] - mean_y)
        for x in examples
    )
    if covariance == 0:
        return None
    return 1 if covariance > 0 else -1


def _constant_direction(examples):
    if not examples:
        return None
    mean_return = sum(x["future_return_bps"] for x in examples) / len(examples)
    if mean_return == 0:
        return None
    return 1 if mean_return > 0 else -1


def _avg(values):
    return sum(values) / len(values) if values else None


def evaluate_funding_horizon(dataset, horizon_hours, cost_bps=BACKTEST_COST_BPS,
                             train_fraction=0.6,
                             min_oos_samples=DEFAULT_MIN_OOS_SAMPLES):
    if not dataset.get("research_only") or dataset.get("candidate_id") != "DATA-FUNDING-001":
        return {"research_only": True, "available": False, "reason": "invalid_research_dataset"}
    if not dataset.get("available"):
        return {"research_only": True, "available": False, "reason": dataset.get("reason") or "dataset_unavailable"}

    examples = _causal_examples(dataset, horizon_hours)
    if len(examples) < 4:
        return {"research_only": True, "available": False,
                "reason": "insufficient_non_overlapping_causal_samples",
                "sample_count": len(examples)}
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
        }

    scored = []
    for row in oos:
        signed_feature = direction * row["funding_pressure_bps"]
        if signed_feature == 0:
            continue
        signal = 1 if signed_feature > 0 else -1
        gross = signal * row["future_return_bps"]
        baseline_gross = baseline_direction * row["future_return_bps"]
        scored.append({**row, "gross_bps": gross, "baseline_gross_bps": baseline_gross})
    if len(scored) < int(min_oos_samples):
        return {
            "research_only": True,
            "available": False,
            "reason": "insufficient_oos_nonzero_feature_samples",
            "sample_count": len(examples),
            "train_samples": len(train),
            "oos_samples": len(scored),
            "minimum_oos_samples": int(min_oos_samples),
        }

    stress = {}
    for multiple in COST_STRESS_MULTIPLIERS:
        stressed_cost = float(cost_bps) * multiple
        net = [row["gross_bps"] - stressed_cost for row in scored]
        baseline_net = [row["baseline_gross_bps"] - stressed_cost for row in scored]
        stress[str(int(multiple)) + "x"] = {
            "cost_bps_round_trip": stressed_cost,
            "avg_net_bps": _avg(net),
            "baseline_avg_net_bps": _avg(baseline_net),
            "incremental_vs_baseline_bps": _avg(net) - _avg(baseline_net),
            "positive_after_cost": _avg(net) > 0,
        }

    mid = len(scored) // 2
    halves = [scored[:mid], scored[mid:]] if mid else [scored]
    half_avg_net = [
        _avg([row["gross_bps"] - float(cost_bps) for row in half])
        for half in halves if half
    ]
    canonical = stress["1x"]
    hit_rate = sum(1 for row in scored if row["gross_bps"] > 0) / len(scored)
    stable_oos_halves = len(half_avg_net) == 2 and all(v > 0 for v in half_avg_net)
    survives_cost_stress = all(stress[key]["positive_after_cost"] for key in ("1x", "2x", "3x"))
    incremental_positive = canonical["incremental_vs_baseline_bps"] > 0

    return {
        "research_only": True,
        "available": True,
        "candidate_id": "DATA-FUNDING-001",
        "horizon_hours": int(horizon_hours),
        "chronological_split": "60_percent_train_40_percent_oos",
        "non_overlapping": True,
        "causal_realized_funding_only": True,
        "feature_window_hours": 24,
        "assumed_fixed_funding_interval": False,
        "training_only_direction": direction,
        "training_only_baseline_direction": baseline_direction,
        "threshold_tuning": False,
        "sample_count": len(examples),
        "train_samples": len(train),
        "oos_samples": len(scored),
        "minimum_oos_samples": int(min_oos_samples),
        "oos_directional_hit_rate": hit_rate,
        "cost_stress": stress,
        "oos_half_avg_net_bps": half_avg_net,
        "stable_positive_oos_halves": stable_oos_halves,
        "survives_3x_cost_stress": survives_cost_stress,
        "incremental_after_cost_vs_baseline_positive": incremental_positive,
        "stage1_pass": bool(canonical["positive_after_cost"] and incremental_positive and survives_cost_stress and stable_oos_halves),
        "promotion_authority": False,
        "production_authority": False,
        "note": "Rejection-oriented stage 1 only; regime/liquidity, multiple-testing, untouched-OOS and genuine-forward gates remain mandatory.",
    }


def evaluate_primary_horizons(dataset, cost_bps=BACKTEST_COST_BPS):
    return {
        "research_only": True,
        "candidate_id": "DATA-FUNDING-001",
        "results": {
            str(hours): evaluate_funding_horizon(dataset, hours, cost_bps=cost_bps)
            for hours in PRIMARY_HORIZONS
        },
        "promotion_authority": False,
        "production_authority": False,
    }
