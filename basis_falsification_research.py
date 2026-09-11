"""Stage-1 chronological falsification for frozen DATA-BASIS-001.

The basis feature definition is frozen before outcome inspection. This module
uses future OKX index closes only as research labels. Predictive direction is
learned from the chronological training segment and then frozen before the
later OOS segment is scored. No threshold search is performed.

This is deliberately only a first falsification stage: it can reject weak raw
basis evidence, but it cannot promote the feature. Incremental-value, regime,
liquidity, multiple-testing, untouched-OOS and genuine-forward gates remain
mandatory under COORD-DATA-003.
"""

from config import BACKTEST_COST_BPS

HOUR_MS = 60 * 60 * 1000
PRIMARY_HORIZONS = (24, 24 * 7)


def _timestamp_exact_examples(dataset, horizon_hours):
    basis = {int(p["ts"]): float(p["basis_bps"]) for p in dataset.get("points") or []}
    index = {int(p["ts"]): float(p["value"]) for p in dataset.get("index_points") or []}
    horizon_ms = int(horizon_hours) * HOUR_MS
    examples = []
    next_allowed_ts = None

    for ts in sorted(set(basis) & set(index)):
        if next_allowed_ts is not None and ts < next_allowed_ts:
            continue
        future_ts = ts + horizon_ms
        if future_ts not in index or index[ts] <= 0 or index[future_ts] <= 0:
            continue
        future_return_bps = (index[future_ts] / index[ts] - 1.0) * 10000.0
        examples.append({
            "forecast_ts": ts,
            "outcome_ts": future_ts,
            "basis_bps": basis[ts],
            "future_return_bps": future_return_bps,
        })
        next_allowed_ts = future_ts
    return examples


def _training_direction(examples):
    if len(examples) < 2:
        return None
    mean_x = sum(x["basis_bps"] for x in examples) / len(examples)
    mean_y = sum(x["future_return_bps"] for x in examples) / len(examples)
    covariance = sum(
        (x["basis_bps"] - mean_x) * (x["future_return_bps"] - mean_y)
        for x in examples
    )
    if covariance == 0:
        return None
    return 1 if covariance > 0 else -1


def evaluate_basis_horizon(dataset, horizon_hours, cost_bps=BACKTEST_COST_BPS,
                           train_fraction=0.6, min_total_samples=8):
    """Score one frozen horizon without tuning on the OOS segment."""
    if not dataset.get("research_only") or dataset.get("candidate_id") != "DATA-BASIS-001":
        return {"research_only": True, "available": False, "reason": "invalid_research_dataset"}
    if not dataset.get("available"):
        return {"research_only": True, "available": False, "reason": dataset.get("reason") or "dataset_unavailable"}

    examples = _timestamp_exact_examples(dataset, horizon_hours)
    if len(examples) < int(min_total_samples):
        return {
            "research_only": True,
            "available": False,
            "reason": "insufficient_non_overlapping_exact_horizon_samples",
            "sample_count": len(examples),
        }

    split = int(len(examples) * float(train_fraction))
    split = max(2, min(split, len(examples) - 2))
    train = examples[:split]
    oos = examples[split:]
    direction = _training_direction(train)
    if direction is None:
        return {
            "research_only": True,
            "available": False,
            "reason": "no_training_only_directional_association",
            "sample_count": len(examples),
            "train_samples": len(train),
            "oos_samples": len(oos),
        }

    scored = []
    for row in oos:
        signed_feature = direction * row["basis_bps"]
        if signed_feature == 0:
            continue
        signal = 1 if signed_feature > 0 else -1
        gross_bps = signal * row["future_return_bps"]
        scored.append({
            "forecast_ts": row["forecast_ts"],
            "outcome_ts": row["outcome_ts"],
            "gross_bps": gross_bps,
            "net_bps": gross_bps - float(cost_bps),
            "directionally_correct": gross_bps > 0,
        })

    if len(scored) < 2:
        return {"research_only": True, "available": False, "reason": "insufficient_oos_nonzero_feature_samples"}

    net = [x["net_bps"] for x in scored]
    gross = [x["gross_bps"] for x in scored]
    hit_rate = sum(1 for x in scored if x["directionally_correct"]) / len(scored)
    return {
        "research_only": True,
        "available": True,
        "candidate_id": "DATA-BASIS-001",
        "horizon_hours": int(horizon_hours),
        "chronological": True,
        "non_overlapping": True,
        "exact_timestamp_labels": True,
        "training_only_direction": direction,
        "threshold_tuning": False,
        "sample_count": len(examples),
        "train_samples": len(train),
        "oos_samples": len(scored),
        "cost_bps_round_trip": float(cost_bps),
        "oos_directional_hit_rate": hit_rate,
        "oos_avg_gross_bps": sum(gross) / len(gross),
        "oos_avg_net_bps": sum(net) / len(net),
        "oos_sum_net_bps": sum(net),
        "positive_after_cost_oos": (sum(net) / len(net)) > 0,
        "promotion_authority": False,
        "note": "Stage-1 univariate falsification only; all canonical downstream gates remain mandatory.",
    }


def evaluate_primary_horizons(dataset, cost_bps=BACKTEST_COST_BPS):
    return {
        "research_only": True,
        "candidate_id": "DATA-BASIS-001",
        "results": {
            str(hours): evaluate_basis_horizon(dataset, hours, cost_bps=cost_bps)
            for hours in PRIMARY_HORIZONS
        },
        "promotion_authority": False,
        "production_authority": False,
    }
