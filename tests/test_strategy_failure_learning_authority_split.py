from __future__ import annotations

import copy

import pytest

from orchestration.strategy_behavior_schema import allow_test_behavior_schemas
from orchestration.strategy_failure_learning import build_failure_learning_artifact, classify_failure
from orchestration.strategy_predeclaration import freeze_predeclaration


def _candidate() -> dict:
    return {
        "schema_version": 1,
        "hypothesis_id": "DISC-AUTHORITY-SPLIT-001",
        "fingerprint_id": "DISC-AUTHORITY-SPLIT-001-v1",
        "family": "authority_split_test",
        "economic_mechanism": "A frozen mechanism exists only to exercise failure-learning authority boundaries.",
        "hypothesis": "Failure learning classifies evidence without allocating research budget.",
        "target_markets": ["BTC-USDC", "ETH-USDC"],
        "target_timeframes": ["1h"],
        "formation_cutoff": "2026-09-20T20:00:00+00:00",
        "data_contract": {
            "source": "public timestamped venue data",
            "point_in_time": True,
            "historical_universe": "fixed_predeclared_assets",
        },
        "signal_rules": {
            "shock_definition": "frozen before outcomes",
            "entry_condition": "frozen before outcomes",
        },
        "execution_rules": {
            "entry_delay_bars": 1,
            "exit_rule": "fixed_holding_window",
            "position_overlap": "forbidden",
        },
        "cost_model": {
            "fees_bps": 8,
            "spread_bps": 4,
            "slippage_bps": 8,
            "funding_bps_per_day": 2,
            "stress_multipliers": [1.0, 2.0, 3.0],
        },
        "search_plan": {
            "multiple_testing_family_id": "MTF-AUTHORITY-SPLIT-001",
            "planned_hypothesis_count": 4,
            "planned_parameter_variants": 1,
        },
        "validation_plan": {
            "chronological": True,
            "selection_uses_training_and_validation_only": True,
            "untouched_oos_required": True,
            "genuine_forward_required": True,
        },
        "protected_evidence": {
            "untouched_oos_opened": False,
            "genuine_forward_opened": False,
        },
        "failure_learning_plan": {
            "minimum_validation_trades": 20,
            "minimum_cell_trades": 8,
            "minimum_stable_cell_fraction": 0.67,
            "catastrophic_event_loss_bps": 500,
            "max_winner_concentration_share": 0.50,
            "require_positive_validation_halves": True,
        },
    }


def _frozen(candidate: dict | None = None) -> dict:
    with allow_test_behavior_schemas():
        return freeze_predeclaration(candidate or _candidate(), rejected_entries=[])


def _screen(parent: dict) -> dict:
    return {
        "schema_version": 1,
        "fingerprint_id": parent["fingerprint_id"],
        "contract_sha256": parent["contract_sha256"],
        "screen_id": "SCREEN-AUTHORITY-SPLIT-001",
        "screen_cutoff": "2026-09-20T21:00:00+00:00",
        "untouched_oos_opened": False,
        "genuine_forward_opened": False,
        "data_quality": {
            "chronology_pass": True,
            "point_in_time_pass": True,
            "data_contract_pass": True,
        },
        "validation_window": {
            "start_utc": "2026-08-01T00:00:00+00:00",
            "end_utc": "2026-08-31T00:00:00+00:00",
            "half_windows": [
                {
                    "start_utc": "2026-08-01T00:00:00+00:00",
                    "end_utc": "2026-08-16T00:00:00+00:00",
                },
                {
                    "start_utc": "2026-08-16T00:00:00+00:00",
                    "end_utc": "2026-08-31T00:00:00+00:00",
                },
            ],
        },
        "validation": {
            "trades": 40,
            "gross_mean_bps": -5,
            "net_mean_bps": -20,
            "profit_factor": 0.8,
            "half_net_bps": [-18, -22],
        },
        "cost_stress": [
            {"multiplier": 1.0, "net_mean_bps": -20},
            {"multiplier": 2.0, "net_mean_bps": -30},
            {"multiplier": 3.0, "net_mean_bps": -40},
        ],
        "risk": {
            "worst_event_net_bps": -120,
            "winner_concentration_share": 0.25,
            "without_best_net_mean_bps": -22,
        },
        "asset_timeframe_cells": [],
        "regime_cells": [],
        "capacity": {"liquidity_capacity_pass": True},
    }


def _proposal(parent: dict) -> dict:
    child = copy.deepcopy(parent)
    child.pop("contract_sha256", None)
    child["hypothesis_id"] = "DISC-AUTHORITY-SPLIT-SUCCESSOR-001"
    child["fingerprint_id"] = "DISC-AUTHORITY-SPLIT-SUCCESSOR-001-v1"
    child["economic_mechanism"] = "Inventory replenishment after a completed dislocation can produce reversion."
    child["hypothesis"] = "A separately frozen replenishment rule has after-cost expectancy."
    child["signal_rules"]["entry_condition"] = "materially distinct frozen successor rule"
    child["validation_plan"]["successor_uses_fresh_nonoverlapping_selection_window"] = True
    child["validation_plan"]["successor_selection_window"] = {
        "start_utc": "2026-09-01T00:00:00+00:00",
        "end_utc": "2026-09-15T00:00:00+00:00",
    }
    child["search_plan"]["planned_hypothesis_count"] = 5
    return {
        "predeclaration": child,
        "change_dimensions": ["economic_mechanism", "structural_component"],
        "rationale": "Test a distinct causal mechanism; allocation belongs to #517, not #511.",
    }


def test_failure_learning_emits_eligible_unranked_successors_only() -> None:
    parent = _frozen()
    with allow_test_behavior_schemas():
        artifact = build_failure_learning_artifact(parent, _screen(parent), [_proposal(parent)], rejected_entries=[])
    assert artifact["successor_ranking_authority"] is False
    assert artifact["successor_allocation_authority"] is False
    assert artifact["successor_allocation_owner"] == "ISSUE_517"
    assert len(artifact["successors"]) == 1
    assert artifact["successors"][0]["eligibility"] == "ELIGIBLE_UNRANKED"
    assert "rank" not in artifact["successors"][0]
    assert "rank_score" not in artifact["successors"][0]


def test_failure_learning_rejects_allocation_score_inputs() -> None:
    parent = _frozen()
    proposal = _proposal(parent)
    proposal["expected_information_gain"] = 0.9
    with allow_test_behavior_schemas(), pytest.raises(RuntimeError, match="allocation.*#517|ranking.*#517"):
        build_failure_learning_artifact(parent, _screen(parent), [proposal], rejected_entries=[])


def test_predeclaration_cannot_lower_project_validation_floor() -> None:
    candidate = _candidate()
    candidate["failure_learning_plan"]["minimum_validation_trades"] = 1
    parent = _frozen(candidate)
    with pytest.raises(RuntimeError, match="project.*minimum|minimum.*20"):
        classify_failure(parent, _screen(parent), rejected_entries=[])


def test_screen_cutoff_must_follow_frozen_formation_cutoff() -> None:
    parent = _frozen()
    screen = _screen(parent)
    screen["screen_cutoff"] = "2026-09-20T19:59:59+00:00"
    with pytest.raises(RuntimeError, match="screen_cutoff.*formation_cutoff|formation_cutoff.*screen_cutoff"):
        classify_failure(parent, screen, rejected_entries=[])


def test_chronological_halves_must_be_nonoverlapping_exact_partition() -> None:
    parent = _frozen()
    screen = _screen(parent)
    screen["validation_window"]["half_windows"][1]["start_utc"] = "2026-08-15T23:00:00+00:00"
    with pytest.raises(RuntimeError, match="half.*overlap|partition|chronological"):
        classify_failure(parent, screen, rejected_entries=[])


def test_successor_fresh_window_must_be_actually_disjoint_not_boolean_only() -> None:
    parent = _frozen()
    proposal = _proposal(parent)
    proposal["predeclaration"]["validation_plan"]["successor_selection_window"] = {
        "start_utc": "2026-08-20T00:00:00+00:00",
        "end_utc": "2026-09-05T00:00:00+00:00",
    }
    with allow_test_behavior_schemas(), pytest.raises(RuntimeError, match="overlap|disjoint|non-overlapping"):
        build_failure_learning_artifact(parent, _screen(parent), [proposal], rejected_entries=[])
