from __future__ import annotations

import copy
import json
from pathlib import Path

from research_artifact import sha256_hex

ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = (
    ROOT
    / "orchestration"
    / "external_replication"
    / "ext_abnormal_day_momentum_001_v1.json"
)


def _load() -> dict:
    return json.loads(ARTIFACT.read_text(encoding="utf-8"))


def test_replication_artifact_digest_is_deterministic() -> None:
    artifact = _load()
    unsigned = copy.deepcopy(artifact)
    expected = unsigned.pop("artifact_sha256")
    assert sha256_hex(unsigned) == expected
    assert artifact["replication_id"] == "EXT-ABNORMAL-DAY-MOMENTUM-001-v1"
    assert artifact["status"] == "PREDECLARED_WAIT_CANONICAL_507_ADMISSION"


def test_replication_is_one_frozen_hypothesis_not_a_parameter_sweep() -> None:
    artifact = _load()
    rules = artifact["signal_rules"]
    testing = artifact["multiple_testing"]
    assert rules["reference_window_completed_utc_days"] == 90
    assert rules["abnormal_sigma_multiple"] == 1.5
    assert rules["latest_signal_hour_utc"] == 22
    assert rules["signal_at_23_utc_forbidden"] is True
    assert testing["planned_hypothesis_count"] == 1
    assert testing["planned_parameter_variants"] == 1
    assert testing["post_outcome_threshold_or_window_tuning_allowed"] is False
    assert testing["source_paper_asset_specific_thresholds_reused"] is False


def test_data_boundary_is_point_in_time_and_protected_oos_is_closed() -> None:
    artifact = _load()
    data = artifact["data_contract"]
    authority = artifact["screening_authority"]
    assert data["normalized_rows_sha256"] == (
        "047c098bb2957557f8344ca30c32339ecac01b5067ae424b147d21c9e9caaf9f"
    )
    assert data["fixed_instruments"] == [
        "BTC-USDT-SWAP",
        "ETH-USDT-SWAP",
        "SOL-USDT-SWAP",
    ]
    assert data["point_in_time"] is True
    assert data["selection_validation_end_utc"] == "2026-08-31T23:00:00Z"
    assert data["protected_oos_start_utc"] == "2026-09-01T00:00:00Z"
    assert data["screen_may_read_protected_oos"] is False
    assert authority["screen_started"] is False
    assert authority["protected_oos_opened"] is False
    assert authority["genuine_forward_opened"] is False
    assert authority["broker_connected"] is False
    assert authority["trade_authority"] is False
    assert authority["promotion_authority"] is False


def test_costs_and_stage_one_gates_match_frozen_factory_quality_bar() -> None:
    artifact = _load()
    costs = artifact["cost_model"]
    gates = artifact["cheap_stage_gates"]
    assert costs["base_total_bps"] == 24.0
    assert costs["stress_multipliers"] == [1.0, 2.0, 3.0]
    assert costs["three_x_total_bps"] == 72.0
    assert gates["minimum_independent_trades_train"] == 40
    assert gates["minimum_independent_trades_validation"] == 20
    assert gates["require_positive_after_cost_train"] is True
    assert gates["require_positive_after_cost_validation"] is True
    assert gates["require_validation_halves_positive"] is True
    assert gates["require_profit_factor_above_one"] is True
    assert gates["require_3x_cost_positive"] is True
    assert gates["catastrophic_tail_veto"] is True
    assert gates["single_winner_dependence_veto"] is True
    assert "do not lower sigma threshold" in gates["underpowered_action"]


def test_baselines_are_frozen_before_outcomes_and_complexity_has_to_earn_value() -> None:
    artifact = _load()
    baselines = artifact["baseline_and_ablation_plan"]
    assert baselines["formation_before_outcomes"] is True
    assert "immediately preceding completed 1h" in baselines["primary_mechanism_baseline"]
    assert "opposite" in baselines["sign_flip_falsifier"]
    assert "one completed 1h bar" in baselines["one_bar_delay"]
    assert "frequency- and direction-matched" in baselines["randomized_timing_placebo"]
    assert "does not beat the primary simple baseline" in baselines["complexity_rule"]


def test_external_published_results_are_mechanism_motivation_only() -> None:
    artifact = _load()
    source = artifact["source_research"]
    assert source["mechanism_only"] is True
    assert source["published_results_are_internal_evidence"] is False
    assert "our own chronological selection evidence" in source["adaptation_note"]
