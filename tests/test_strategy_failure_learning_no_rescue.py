from __future__ import annotations

import copy

import pytest

from orchestration.strategy_behavior_schema import allow_test_behavior_schemas
from orchestration.strategy_failure_learning import build_failure_learning_artifact
from orchestration.strategy_predeclaration import freeze_predeclaration


def _candidate() -> dict:
    return {
        "schema_version": 1,
        "hypothesis_id": "DISC-TEST-MOMENTUM-001",
        "fingerprint_id": "DISC-TEST-MOMENTUM-001-v1",
        "family": "test_momentum",
        "economic_mechanism": "Persistent spot-led order flow can continue after a completed impulse.",
        "hypothesis": "A frozen spot-led continuation rule has positive after-cost validation expectancy.",
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
            "multiple_testing_family_id": "MTF-TEST-MOM-001",
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


def _screen(parent: dict) -> dict:
    return {
        "schema_version": 1,
        "fingerprint_id": parent["fingerprint_id"],
        "contract_sha256": parent["contract_sha256"],
        "screen_id": "SCREEN-NO-RESCUE-001",
        "screen_cutoff": "2026-09-20T21:00:00+00:00",
        "untouched_oos_opened": False,
        "genuine_forward_opened": False,
        "data_quality": {
            "chronology_pass": True,
            "point_in_time_pass": True,
            "data_contract_pass": True,
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


def _proposal(parent: dict, fingerprint: str, *, distinct_behavior: bool) -> dict:
    child = copy.deepcopy(parent)
    child.pop("contract_sha256", None)
    child["hypothesis_id"] = fingerprint.removesuffix("-v2")
    child["fingerprint_id"] = fingerprint
    child["economic_mechanism"] = "Inventory replenishment after spot-led dislocation can produce short-horizon reversion."
    child["hypothesis"] = "A frozen inventory-replenishment condition has positive after-cost expectancy."
    if distinct_behavior:
        child["signal_rules"]["entry_condition"] = "independent materially different frozen rule"
    child["validation_plan"]["successor_uses_fresh_nonoverlapping_selection_window"] = True
    child["search_plan"]["planned_hypothesis_count"] = parent["search_plan"]["planned_hypothesis_count"] + 1
    return {
        "predeclaration": child,
        "change_dimensions": ["economic_mechanism", "structural_component"],
        "rationale": "Test a genuinely distinct executable mechanism rather than relabeling the failed parent.",
        "expected_information_gain": 0.8,
        "economic_plausibility": 0.8,
        "data_readiness": 0.9,
        "compute_cost": 0.2,
    }


def test_renamed_prose_only_parent_clone_is_rejected() -> None:
    with allow_test_behavior_schemas():
        parent = freeze_predeclaration(_candidate(), rejected_entries=[])
        proposal = _proposal(parent, "DISC-RENAMED-CLONE-001-v2", distinct_behavior=False)
        with pytest.raises(RuntimeError, match="executable behavior must differ"):
            build_failure_learning_artifact(parent, _screen(parent), [proposal], rejected_entries=[])


def test_sibling_successors_cannot_duplicate_one_executable_behavior() -> None:
    with allow_test_behavior_schemas():
        parent = freeze_predeclaration(_candidate(), rejected_entries=[])
        first = _proposal(parent, "DISC-DISTINCT-001-v2", distinct_behavior=True)
        second = copy.deepcopy(first)
        second["predeclaration"]["hypothesis_id"] = "DISC-DISTINCT-002"
        second["predeclaration"]["fingerprint_id"] = "DISC-DISTINCT-002-v2"
        second["predeclaration"]["economic_mechanism"] = "Same executable rule described with different mechanism prose."
        second["predeclaration"]["hypothesis"] = "Different words must not create another executable hypothesis."
        with pytest.raises(RuntimeError, match="unique executable behavior"):
            build_failure_learning_artifact(parent, _screen(parent), [first, second], rejected_entries=[])


def test_genuine_supported_behavior_change_remains_eligible() -> None:
    with allow_test_behavior_schemas():
        parent = freeze_predeclaration(_candidate(), rejected_entries=[])
        proposal = _proposal(parent, "DISC-DISTINCT-003-v2", distinct_behavior=True)
        artifact = build_failure_learning_artifact(parent, _screen(parent), [proposal], rejected_entries=[])
        assert len(artifact["successors"]) == 1
        assert artifact["successors"][0]["predeclaration"]["fingerprint_id"] == "DISC-DISTINCT-003-v2"
        assert artifact["untouched_oos_opened"] is False
        assert artifact["genuine_forward_opened"] is False
        assert artifact["trade_authority"] is False
