import json
from pathlib import Path

from market_data import _aligned_basis_history


CONTRACT_PATH = Path("orchestration/coord_data_002_basis_candidate.json")


def _contract():
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


def test_basis_candidate_contract_is_frozen_research_only_and_cost_safe():
    contract = _contract()
    candidate = contract["candidate"]
    plan = contract["evaluation_plan"]
    safety = contract["safety"]

    assert contract["task_id"] == "COORD-DATA-002"
    assert contract["experiment_id"] == "DATA-BASIS-001"
    assert candidate["source"] == "okx_public_mark_and_index_history"
    assert candidate["bar"] == "1H"
    assert candidate["timestamp_alignment"] == "exact_shared_timestamp_only"
    assert candidate["completed_candles_only"] is True
    assert candidate["interpolation_allowed"] is False
    assert candidate["nearest_neighbor_allowed"] is False
    assert candidate["forward_fill_allowed"] is False
    assert candidate["historical_oi_dependency"] is False
    assert plan["candidate_threshold_tuning_allowed"] is False
    assert plan["production_use_allowed"] is False
    assert plan["paper_trade_authority"] is False
    assert plan["broker_authority"] is False
    assert plan["promotion_authority"] is False
    assert safety == {
        "research_only": True,
        "changes_production_behavior": False,
        "changes_signal_thresholds": False,
        "changes_live_promotions": False,
        "changes_paper_ledger": False,
        "changes_broker_state": False,
        "changes_worker_concurrency": False,
        "adds_recurring_cost": False,
    }


def test_basis_alignment_uses_only_exact_shared_timestamps_without_interpolation():
    marks = [
        {"ts": 1_000, "value": 101.0},
        {"ts": 2_000, "value": 102.0},
        {"ts": 4_000, "value": 104.0},
    ]
    indexes = [
        {"ts": 1_000, "value": 100.0},
        {"ts": 3_000, "value": 103.0},
        {"ts": 4_000, "value": 100.0},
    ]

    aligned = _aligned_basis_history(marks, indexes)

    assert [row["ts"] for row in aligned] == [1_000, 4_000]
    assert aligned[0]["basis_bps"] == 100.0
    assert aligned[1]["basis_bps"] == 400.0
    assert all(row["ts"] not in {2_000, 3_000} for row in aligned)


def test_basis_candidate_predeclares_falsification_instead_of_feature_retention():
    contract = _contract()
    falsification = contract["falsification"]

    assert falsification["next_task"] == "COORD-DATA-003"
    assert falsification["retain_merely_to_increase_feature_count"] is False
    assert "incremental_oos_signal_quality_is_not_stable" in falsification["reject_if"]
    assert "apparent_edge_disappears_after_realistic_costs" in falsification["reject_if"]
    assert "robustness_or_multiple_testing_controls_fail" in falsification["reject_if"]
