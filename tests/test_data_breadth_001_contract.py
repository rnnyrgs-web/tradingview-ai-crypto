import json
from pathlib import Path


def _contract() -> dict:
    return json.loads(Path("orchestration/data_breadth_001_candidate.json").read_text(encoding="utf-8"))


def test_data_breadth_001_is_frozen_research_only_and_distinct():
    cfg = _contract()
    assert cfg["task_id"] == "COORD-DATA-005"
    assert cfg["candidate_id"] == "DATA-BREADTH-001"
    assert cfg["status"] == "PREDECLARED_RESEARCH_ONLY"
    assert cfg["immutable_feature"]["name"] == "pit_cross_sectional_breadth_24h"
    assert cfg["immutable_feature"]["lookback_hours"] == 24
    assert cfg["immutable_feature"]["minimum_eligible_assets"] == 15
    assert cfg["immutable_feature"]["threshold_search"] is False
    assert cfg["source"]["blocked_oi_dependency"] is False
    assert cfg["source"]["paid_service_required"] is False
    assert cfg["source"]["point_in_time_universe_required"] is True
    assert cfg["source"]["survivorship_prone_static_universe_forbidden"] is True

    authority = cfg["authority"]
    assert authority["research_only"] is True
    assert authority["signal_authority"] is False
    assert authority["paper_authority"] is False
    assert authority["broker_authority"] is False
    assert authority["promotion_authority"] is False
    assert authority["threshold_changes"] is False
    assert authority["worker_concurrency_change"] is False
    assert authority["recurring_cost_change"] is False


def test_data_breadth_001_keeps_profitability_and_scientific_gates_closed():
    cfg = _contract()
    ev = cfg["evaluation_contract"]
    assert ev["primary_horizons"] == ["24h", "7d"]
    assert ev["chronological_split"] == "60_percent_train_40_percent_oos"
    assert ev["non_overlapping_forward_samples"] is True
    assert ev["minimum_oos_samples_per_primary_horizon"] == 8
    assert ev["training_only_constant_direction_baseline"] is True
    assert ev["incremental_after_cost_value_required"] is True
    assert ev["canonical_execution_costs_required"] is True
    assert ev["fixed_cost_stress_multipliers"] == [1.0, 2.0, 3.0]
    assert ev["oos_threshold_tuning"] is False
    assert ev["multiple_testing_accounting_required"] is True
    assert ev["untouched_oos_opened"] is False
    assert ev["genuine_forward_evidence_required_before_promotion"] is True

    forbidden = " ".join(cfg["forbidden_actions"]).lower()
    assert "present-day fixed survivor list" in forbidden
    assert "binance historical-oi" in forbidden
    assert "bybit historical-oi" in forbidden
    assert "do not tune breadth thresholds" in forbidden
    assert "do not open untouched oos" in forbidden
