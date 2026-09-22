from __future__ import annotations

from orchestration.strategy_failure_learning import (
    FAILURE_TAIL,
    FAILURE_UNDERPOWERED,
    classify_failure,
)
from orchestration.strategy_predeclaration import freeze_predeclaration


def _candidate() -> dict:
    return {
        "schema_version": 1,
        "hypothesis_id": "DISC-TEST-SPARSE-001",
        "fingerprint_id": "DISC-TEST-SPARSE-001-v1",
        "family": "test_sparse",
        "economic_mechanism": "Sparse event arrival can still carry measurable development evidence.",
        "hypothesis": "A frozen sparse-event rule is evaluated without fabricating undefined statistics.",
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
            "multiple_testing_family_id": "MTF-TEST-SPARSE-001",
            "planned_hypothesis_count": 1,
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


def _frozen() -> dict:
    return freeze_predeclaration(_candidate(), rejected_entries=[])


def _screen(parent: dict, *, trades: int = 0) -> dict:
    return {
        "schema_version": 1,
        "fingerprint_id": parent["fingerprint_id"],
        "contract_sha256": parent["contract_sha256"],
        "screen_id": "SCREEN-SPARSE-001",
        "screen_cutoff": "2026-09-20T21:00:00+00:00",
        "untouched_oos_opened": False,
        "genuine_forward_opened": False,
        "data_quality": {
            "chronology_pass": True,
            "point_in_time_pass": True,
            "data_contract_pass": True,
        },
        "validation": {
            "trades": trades,
            "gross_mean_bps": None,
            "net_mean_bps": None,
            "profit_factor": None,
            "half_net_bps": [None, None],
        },
        "risk": {
            "worst_event_net_bps": None,
            "winner_concentration_share": None,
            "without_best_net_mean_bps": None,
        },
        "asset_timeframe_cells": [
            {"market": "BTC-USDC", "timeframe": "1h", "trades": 0, "net_mean_bps": None},
        ],
        "regime_cells": [
            {"label": "sparse", "trades": 0, "net_mean_bps": None},
        ],
    }


def test_zero_event_screen_preserves_undefined_statistics_and_is_inconclusive() -> None:
    parent = _frozen()
    result = classify_failure(parent, _screen(parent), rejected_entries=[])

    assert result["status"] == "INCONCLUSIVE"
    assert result["failure_categories"] == [FAILURE_UNDERPOWERED]
    assert result["rejection_eligible"] is False


def test_sparse_observed_catastrophic_loss_remains_rejection_eligible() -> None:
    parent = _frozen()
    screen = _screen(parent, trades=1)
    screen["validation"]["gross_mean_bps"] = -600
    screen["validation"]["net_mean_bps"] = -624
    screen["risk"]["worst_event_net_bps"] = -624

    result = classify_failure(parent, screen, rejected_entries=[])

    assert result["status"] == "REJECTED"
    assert result["failure_categories"] == [FAILURE_TAIL]
    assert result["rejection_eligible"] is True


def test_one_event_without_leave_best_stat_remains_inconclusive() -> None:
    parent = _frozen()
    screen = _screen(parent, trades=1)
    screen["validation"]["gross_mean_bps"] = 80
    screen["validation"]["net_mean_bps"] = 56
    screen["validation"]["profit_factor"] = float("inf")
    screen["risk"]["worst_event_net_bps"] = 56
    screen["risk"]["winner_concentration_share"] = 1.0

    result = classify_failure(parent, screen, rejected_entries=[])

    assert result["status"] == "INCONCLUSIVE"
    assert result["failure_categories"] == [FAILURE_UNDERPOWERED]
    assert result["rejection_eligible"] is False


def test_powered_all_winner_profit_factor_positive_infinity_is_valid_economics() -> None:
    parent = _frozen()
    screen = _screen(parent, trades=20)
    screen["validation"] = {
        "trades": 20,
        "gross_mean_bps": 60,
        "net_mean_bps": 36,
        "profit_factor": float("inf"),
        "half_net_bps": [30, 42],
    }
    screen["risk"] = {
        "worst_event_net_bps": 5,
        "winner_concentration_share": 0.20,
        "without_best_net_mean_bps": 30,
    }
    screen["cost_stress"] = [
        {"multiplier": 1.0, "net_mean_bps": 36},
        {"multiplier": 2.0, "net_mean_bps": 12},
        {"multiplier": 3.0, "net_mean_bps": 2},
    ]
    screen["capacity"] = {"liquidity_capacity_pass": True}
    screen["asset_timeframe_cells"] = [
        {"market": "BTC-USDC", "timeframe": "1h", "trades": 7, "net_mean_bps": None},
        {"market": "ETH-USDC", "timeframe": "1h", "trades": 13, "net_mean_bps": 36},
    ]
    screen["regime_cells"] = [
        {"label": "thin", "trades": 3, "net_mean_bps": None},
        {"label": "normal", "trades": 17, "net_mean_bps": 36},
    ]

    result = classify_failure(parent, screen, rejected_entries=[])

    assert result["status"] == "SCREEN_PASS"
    assert result["failure_categories"] == []


def test_powered_missing_chronological_half_is_inconclusive_not_fabricated() -> None:
    parent = _frozen()
    screen = _screen(parent, trades=20)
    screen["validation"] = {
        "trades": 20,
        "gross_mean_bps": 60,
        "net_mean_bps": 36,
        "profit_factor": 2.0,
        "half_net_bps": [36, None],
    }
    screen["risk"] = {
        "worst_event_net_bps": -50,
        "winner_concentration_share": 0.20,
        "without_best_net_mean_bps": 30,
    }

    result = classify_failure(parent, screen, rejected_entries=[])

    assert result["status"] == "INCONCLUSIVE"
    assert result["failure_categories"] == [FAILURE_UNDERPOWERED]
    assert result["rejection_eligible"] is False


def test_powered_missing_half_does_not_mask_observed_catastrophic_tail() -> None:
    parent = _frozen()
    screen = _screen(parent, trades=20)
    screen["validation"] = {
        "trades": 20,
        "gross_mean_bps": -500,
        "net_mean_bps": -524,
        "profit_factor": 0.2,
        "half_net_bps": [-524, None],
    }
    screen["risk"] = {
        "worst_event_net_bps": -700,
        "winner_concentration_share": 0.10,
        "without_best_net_mean_bps": None,
    }

    result = classify_failure(parent, screen, rejected_entries=[])

    assert result["status"] == "REJECTED"
    assert result["failure_categories"] == [FAILURE_TAIL]
    assert result["rejection_eligible"] is True
