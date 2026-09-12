"""Strict compatibility observability for the reserved falsification worker.

DATA-BASIS-001 is retired.  The worker/key name is retained temporarily to avoid
changing coordinator topology, but this projection only reports bounded
DATA-FUNDING-001 aggregate evidence from COORD-DATA-004.  Raw funding/price rows,
timestamps, arbitrary upstream payloads, and trading authority are never
projected.
"""

from __future__ import annotations


_ALLOWED_COLLECTION_REASONS = {
    "source_error",
    "insufficient_raw_history",
}
_ALLOWED_RESULT_REASONS = {
    "invalid_research_dataset",
    "dataset_unavailable",
    "source_error",
    "insufficient_raw_history",
    "insufficient_non_overlapping_causal_samples",
    "insufficient_oos_samples_before_scoring",
    "no_training_only_direction",
    "insufficient_oos_nonzero_feature_samples",
}


def _nonnegative_int(value):
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None


def _finite_number(value):
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return None
    value = float(value)
    if value != value or value in (float("inf"), float("-inf")):
        return None
    return value


def _reason(value, allowed):
    return value if isinstance(value, str) and value in allowed else None


def _direction(value):
    return value if value in (-1, 1) else None


def _compact_stress(raw: object) -> dict | None:
    if not isinstance(raw, dict):
        return None
    return {
        "cost_bps_round_trip": _finite_number(raw.get("cost_bps_round_trip")),
        "avg_net_bps": _finite_number(raw.get("avg_net_bps")),
        "baseline_avg_net_bps": _finite_number(raw.get("baseline_avg_net_bps")),
        "incremental_vs_baseline_bps": _finite_number(raw.get("incremental_vs_baseline_bps")),
        "positive_after_cost": raw.get("positive_after_cost") is True,
    }


def _compact_result(raw: object, expected_horizon: int) -> dict | None:
    if not isinstance(raw, dict):
        return None
    available = raw.get("available") is True
    stress = raw.get("cost_stress") if isinstance(raw.get("cost_stress"), dict) else {}
    halves = raw.get("oos_half_avg_net_bps")
    if isinstance(halves, list) and len(halves) <= 2:
        compact_halves = [_finite_number(value) for value in halves]
        if any(value is None for value in compact_halves):
            compact_halves = None
    else:
        compact_halves = None
    return {
        "available": available,
        "reason": _reason(raw.get("reason"), _ALLOWED_RESULT_REASONS),
        "horizon_hours": expected_horizon,
        "chronological_split": "60_percent_train_40_percent_oos" if raw.get("chronological_split") == "60_percent_train_40_percent_oos" else None,
        "non_overlapping": raw.get("non_overlapping") is True,
        "causal_realized_funding_only": raw.get("causal_realized_funding_only") is True,
        "feature_window_hours": 24 if raw.get("feature_window_hours") == 24 else None,
        "assumed_fixed_funding_interval": False,
        "training_only_direction": _direction(raw.get("training_only_direction")),
        "training_only_baseline_direction": _direction(raw.get("training_only_baseline_direction")),
        "threshold_tuning": raw.get("threshold_tuning") is True,
        "sample_count": _nonnegative_int(raw.get("sample_count")),
        "train_samples": _nonnegative_int(raw.get("train_samples")),
        "oos_samples": _nonnegative_int(raw.get("oos_samples")),
        "minimum_oos_samples": _nonnegative_int(raw.get("minimum_oos_samples")),
        "oos_directional_hit_rate": _finite_number(raw.get("oos_directional_hit_rate")),
        "cost_stress": {
            "1x": _compact_stress(stress.get("1x")),
            "2x": _compact_stress(stress.get("2x")),
            "3x": _compact_stress(stress.get("3x")),
        },
        "oos_half_avg_net_bps": compact_halves,
        "stable_positive_oos_halves": raw.get("stable_positive_oos_halves") is True,
        "survives_3x_cost_stress": raw.get("survives_3x_cost_stress") is True,
        "incremental_after_cost_vs_baseline_positive": raw.get("incremental_after_cost_vs_baseline_positive") is True,
        "stage1_pass": raw.get("stage1_pass") is True,
        "promotion_authority": False,
        "production_authority": False,
    }


def compact_basis_falsification(army: object) -> dict:
    """Compatibility API: return strict DATA-FUNDING-001 evidence only."""
    if not isinstance(army, dict):
        army = {}
    workers = army.get("workers") if isinstance(army.get("workers"), dict) else {}
    worker = workers.get("basis-falsification-btc") if isinstance(workers.get("basis-falsification-btc"), dict) else {}
    evidence = worker.get("latest_evidence") if isinstance(worker.get("latest_evidence"), dict) else {}

    # Never reinterpret old/rejected basis evidence as funding evidence.
    is_funding = evidence.get("candidate_id") == "DATA-FUNDING-001" and evidence.get("task_id") == "COORD-DATA-004"
    if not is_funding:
        evidence = {}

    collection = evidence.get("collection") if isinstance(evidence.get("collection"), dict) else {}
    raw_results = evidence.get("results") if isinstance(evidence.get("results"), dict) else {}

    return {
        "worker_exit": worker.get("last_exit_code") if isinstance(worker.get("last_exit_code"), int) else None,
        "worker_elapsed_s": _finite_number(worker.get("elapsed_seconds")),
        "worker_finished_at": worker.get("last_finished_at") if isinstance(worker.get("last_finished_at"), str) else None,
        "research_only": True,
        "task_id": "COORD-DATA-004",
        "candidate_id": "DATA-FUNDING-001",
        "legacy_observability_key": "basis_falsification",
        "base": evidence.get("base") if evidence.get("base") in {"BTC"} else "BTC",
        "evidence_conclusion": evidence.get("evidence_conclusion") if evidence.get("evidence_conclusion") in {"stage1_evaluated", "insufficient_evidence"} else None,
        "available_primary_results": _nonnegative_int(evidence.get("available_primary_results")),
        "stage1_pass_count": _nonnegative_int(evidence.get("stage1_pass_count")),
        "collection": {
            "available": collection.get("available") is True,
            "reason": _reason(collection.get("reason"), _ALLOWED_COLLECTION_REASONS),
            "funding_point_count": _nonnegative_int(collection.get("funding_point_count")),
            "index_point_count": _nonnegative_int(collection.get("index_point_count")),
            "funding_pages": _nonnegative_int(collection.get("funding_pages")),
            "index_pages": _nonnegative_int(collection.get("index_pages")),
            "uses_actual_funding_timestamps": collection.get("uses_actual_funding_timestamps") is True,
            "assumed_fixed_funding_interval": False,
            "completed_price_candles_only": collection.get("completed_price_candles_only") is True,
            "interpolation_allowed": False,
            "forward_fill_allowed": False,
            "nearest_neighbor_matching": False,
        },
        "results": {
            "24": _compact_result(raw_results.get("24"), 24),
            "168": _compact_result(raw_results.get("168"), 168),
        },
        "production_authority": False,
        "signal_authority": False,
        "paper_authority": False,
        "promotion_authority": False,
        "broker_authority": False,
    }
