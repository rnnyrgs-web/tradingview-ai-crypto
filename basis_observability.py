"""Bounded observability projection for research-only DATA-BASIS falsification.

This module exposes only fixed aggregate Stage-1 and Stage-2 evidence needed to
decide whether DATA-BASIS-001 should be rejected or studied further. Raw market
rows, timestamps, arbitrary upstream errors, and any trading authority are never
projected.
"""

from __future__ import annotations


_ALLOWED_COLLECTION_REASONS = {
    "source_error",
    "insufficient_exact_timestamp_coverage",
}
_ALLOWED_RESULT_REASONS = {
    "invalid_research_dataset",
    "dataset_unavailable",
    "source_error",
    "insufficient_exact_timestamp_coverage",
    "insufficient_non_overlapping_exact_horizon_samples",
    "insufficient_oos_samples_before_scoring",
    "no_training_only_directional_association",
    "insufficient_oos_nonzero_feature_samples",
}
_ALLOWED_ROBUSTNESS_REASONS = {
    "invalid_research_dataset",
    "dataset_unavailable",
    "source_error",
    "insufficient_exact_timestamp_coverage",
    "insufficient_non_overlapping_exact_horizon_samples",
    "insufficient_oos_samples_before_robustness",
    "training_direction_unavailable",
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


def _compact_result(raw: object, expected_horizon: int) -> dict | None:
    if not isinstance(raw, dict):
        return None
    available = raw.get("available") is True
    direction = raw.get("training_only_direction")
    if direction not in (-1, 1):
        direction = None
    return {
        "available": available,
        "reason": _reason(raw.get("reason"), _ALLOWED_RESULT_REASONS),
        "horizon_hours": expected_horizon,
        "chronological": raw.get("chronological") is True,
        "non_overlapping": raw.get("non_overlapping") is True,
        "exact_timestamp_labels": raw.get("exact_timestamp_labels") is True,
        "training_only_direction": direction,
        "threshold_tuning": raw.get("threshold_tuning") is True,
        "sample_count": _nonnegative_int(raw.get("sample_count")),
        "train_samples": _nonnegative_int(raw.get("train_samples")),
        "oos_samples": _nonnegative_int(raw.get("oos_samples")),
        "minimum_oos_samples": _nonnegative_int(raw.get("minimum_oos_samples")),
        "cost_bps_round_trip": _finite_number(raw.get("cost_bps_round_trip")),
        "oos_directional_hit_rate": _finite_number(raw.get("oos_directional_hit_rate")),
        "oos_avg_gross_bps": _finite_number(raw.get("oos_avg_gross_bps")),
        "oos_avg_net_bps": _finite_number(raw.get("oos_avg_net_bps")),
        "oos_sum_net_bps": _finite_number(raw.get("oos_sum_net_bps")),
        "positive_after_cost_oos": raw.get("positive_after_cost_oos") is True if available else None,
        "promotion_authority": False,
    }


def _compact_stress(raw: object) -> dict | None:
    if not isinstance(raw, dict):
        return None
    return {
        "cost_bps_round_trip": _finite_number(raw.get("cost_bps_round_trip")),
        "avg_net_bps": _finite_number(raw.get("avg_net_bps")),
        "positive_after_cost": raw.get("positive_after_cost") is True,
    }


def _compact_robustness(raw: object, expected_horizon: int) -> dict | None:
    if not isinstance(raw, dict):
        return None
    available = raw.get("available") is True
    basis_direction = raw.get("training_only_basis_direction")
    constant_direction = raw.get("training_only_constant_direction")
    if basis_direction not in (-1, 1):
        basis_direction = None
    if constant_direction not in (-1, 1):
        constant_direction = None
    checkpoints = raw.get("training_direction_checkpoints")
    if not isinstance(checkpoints, list) or len(checkpoints) != 3 or any(x not in (-1, 1, None) for x in checkpoints):
        checkpoints = None
    stress = raw.get("cost_stress") if isinstance(raw.get("cost_stress"), dict) else {}
    return {
        "available": available,
        "reason": _reason(raw.get("reason"), _ALLOWED_ROBUSTNESS_REASONS),
        "horizon_hours": expected_horizon,
        "chronological": raw.get("chronological") is True,
        "non_overlapping": raw.get("non_overlapping") is True,
        "threshold_tuning": raw.get("threshold_tuning") is True,
        "untouched_oos_opened": raw.get("untouched_oos_opened") is True,
        "oos_samples": _nonnegative_int(raw.get("oos_samples")),
        "training_only_basis_direction": basis_direction,
        "training_only_constant_direction": constant_direction,
        "training_direction_checkpoints": checkpoints,
        "training_direction_stable": raw.get("training_direction_stable") is True,
        "basis_oos_hit_rate": _finite_number(raw.get("basis_oos_hit_rate")),
        "constant_baseline_oos_hit_rate": _finite_number(raw.get("constant_baseline_oos_hit_rate")),
        "basis_oos_avg_net_bps": _finite_number(raw.get("basis_oos_avg_net_bps")),
        "constant_baseline_oos_avg_net_bps": _finite_number(raw.get("constant_baseline_oos_avg_net_bps")),
        "incremental_vs_constant_avg_net_bps": _finite_number(raw.get("incremental_vs_constant_avg_net_bps")),
        "beats_training_only_constant_baseline": raw.get("beats_training_only_constant_baseline") is True,
        "cost_stress": {
            "1x": _compact_stress(stress.get("1x")),
            "2x": _compact_stress(stress.get("2x")),
            "3x": _compact_stress(stress.get("3x")),
        },
        "oos_half_minimum_met": raw.get("oos_half_minimum_met") is True,
        "first_half_avg_net_bps": _finite_number(raw.get("first_half_avg_net_bps")),
        "second_half_avg_net_bps": _finite_number(raw.get("second_half_avg_net_bps")),
        "both_oos_halves_positive": raw.get("both_oos_halves_positive") if isinstance(raw.get("both_oos_halves_positive"), bool) else None,
        "promotion_authority": False,
        "production_authority": False,
    }


def compact_basis_falsification(army: object) -> dict:
    """Return a strict allowlist of the BTC basis worker's latest evidence."""
    if not isinstance(army, dict):
        army = {}
    workers = army.get("workers") if isinstance(army.get("workers"), dict) else {}
    worker = workers.get("basis-falsification-btc") if isinstance(workers.get("basis-falsification-btc"), dict) else {}
    evidence = worker.get("latest_evidence") if isinstance(worker.get("latest_evidence"), dict) else {}
    collection = evidence.get("collection") if isinstance(evidence.get("collection"), dict) else {}
    raw_results = evidence.get("results") if isinstance(evidence.get("results"), dict) else {}
    raw_robustness = evidence.get("profitability_robustness") if isinstance(evidence.get("profitability_robustness"), dict) else {}

    return {
        "worker_exit": worker.get("last_exit_code") if isinstance(worker.get("last_exit_code"), int) else None,
        "worker_elapsed_s": _finite_number(worker.get("elapsed_seconds")),
        "worker_finished_at": worker.get("last_finished_at") if isinstance(worker.get("last_finished_at"), str) else None,
        "research_only": True,
        "task_id": "COORD-DATA-003",
        "candidate_id": "DATA-BASIS-001",
        "base": "BTC",
        "evidence_conclusion": evidence.get("evidence_conclusion") if evidence.get("evidence_conclusion") in {"stage1_evaluated", "stage1_and_stage2_evaluated", "insufficient_evidence"} else None,
        "available_primary_results": _nonnegative_int(evidence.get("available_primary_results")),
        "available_robustness_results": _nonnegative_int(evidence.get("available_robustness_results")),
        "collection": {
            "available": collection.get("available") is True,
            "reason": _reason(collection.get("reason"), _ALLOWED_COLLECTION_REASONS),
            "target_points": _nonnegative_int(collection.get("target_points")),
            "point_count": _nonnegative_int(collection.get("point_count")),
            "mark_point_count": _nonnegative_int(collection.get("mark_point_count")),
            "index_point_count": _nonnegative_int(collection.get("index_point_count")),
            "mark_pages": _nonnegative_int(collection.get("mark_pages")),
            "index_pages": _nonnegative_int(collection.get("index_pages")),
            "alignment": "exact_shared_timestamp_only" if collection.get("alignment") == "exact_shared_timestamp_only" else None,
            "completed_candles_only": collection.get("completed_candles_only") is True,
            "interpolation_allowed": False,
        },
        "results": {
            "24": _compact_result(raw_results.get("24"), 24),
            "168": _compact_result(raw_results.get("168"), 168),
        },
        "profitability_robustness": {
            "24": _compact_robustness(raw_robustness.get("24"), 24),
            "168": _compact_robustness(raw_robustness.get("168"), 168),
        },
        "production_authority": False,
        "signal_authority": False,
        "paper_authority": False,
        "promotion_authority": False,
        "broker_authority": False,
    }
