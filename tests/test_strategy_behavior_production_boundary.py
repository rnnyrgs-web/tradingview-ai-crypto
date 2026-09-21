from __future__ import annotations

import copy

import pytest

from orchestration.rejected_fingerprints import load_rejected_fingerprints
from orchestration.scientific_design_identity import (
    scientific_design_sha256,
    strategy_behavior_sha256,
)
from orchestration.strategy_behavior_schema import (
    PRODUCTION_BEHAVIOR_SCHEMAS,
    allow_test_behavior_schemas,
    resolve_behavior_schema_id,
)
from orchestration.strategy_predeclaration import validate_predeclaration


def _synthetic_test_candidate() -> dict:
    return {
        "schema_version": 1,
        "hypothesis_id": "PRODUCTION-BOUNDARY-ATTACK",
        "fingerprint_id": "PRODUCTION-BOUNDARY-ATTACK-v1",
        "family": "regression_only",
        "economic_mechanism": "Regression fixture only.",
        "hypothesis": "A TEST_* schema must never be production-admissible.",
        "target_markets": ["BTC-USDC", "ETH-USDC"],
        "target_timeframes": ["1h"],
        "formation_cutoff": "2026-09-20T00:00:00+00:00",
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
            "fees_bps": 10,
            "spread_bps": 2,
            "slippage_bps": 3,
            "funding_bps_per_day": 0,
            "stress_multipliers": [1, 2, 3],
        },
        "search_plan": {
            "multiple_testing_family_id": "PRODUCTION-BOUNDARY-FAMILY",
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
    }


def _breadth_design() -> dict:
    return {
        "target_markets": ["BTC-USDT-SWAP", "ETH-USDT-SWAP", "SOL-USDT-SWAP"],
        "target_timeframes": ["1h"],
        "data_contract": {
            "source": "OKX /api/v5/market/history-candles",
            "bar": "1H",
            "fixed_instruments": ["BTC-USDT-SWAP", "ETH-USDT-SWAP", "SOL-USDT-SWAP"],
            "normalized_rows_sha256": "047c098bb2957557f8344ca30c32339ecac01b5067ae424b147d21c9e9caaf9f",
            "normalized_row_count": 35997,
            "coverage_start_utc": "2025-05-07T05:00:00+00:00",
            "coverage_end_utc": "2026-09-19T03:00:00+00:00",
            "selection_train_start_utc": "2025-05-07T05:00:00+00:00",
            "selection_train_end_utc": "2026-04-30T23:00:00+00:00",
            "selection_validation_start_utc": "2026-05-01T00:00:00+00:00",
            "selection_validation_end_utc": "2026-08-31T23:00:00+00:00",
            "protected_oos_start_utc": "2026-09-01T00:00:00+00:00",
            "protected_oos_end_utc": "2026-09-19T03:00:00+00:00",
            "point_in_time": True,
            "screen_may_read_protected_oos": False,
            "historical_universe": "fixed_predeclared_assets",
        },
        "signal_rules": {
            "lookback_hours": 6,
            "per_asset_return": "close_t / close_t_minus_6h - 1",
            "direction_gate": "all three 6h returns have the same non-zero sign",
            "strength_gate": "median(abs(6h return across assets)) >= rolling_30d_median_of_same_statistic",
            "dispersion_gate": "cross_sectional_std(6h returns) <= rolling_30d_60th_percentile_of_same_statistic",
            "decision_time": "completed 1h bar close only",
            "warmup_hours": 720,
        },
        "execution_rules": {
            "entry": "next completed bar open after signal",
            "direction": "same as synchronized basket sign",
            "portfolio": "equal notional BTC/ETH/SOL basket",
            "hold_hours": 6,
            "overlap": "ignore new signals while basket position is open",
            "stop": "none in cheap screen; fixed-hold falsification only",
        },
        "cost_model": {
            "fees_bps": 12,
            "spread_bps": 2,
            "slippage_bps": 6,
            "adverse_funding_allowance_bps_per_trade": 4,
            "stress_multipliers": [1, 2, 3],
        },
        "validation_plan": {
            "chronological": True,
            "selection_uses_training_and_validation_only": True,
            "untouched_oos_required": True,
            "genuine_forward_required": True,
            "minimum_independent_trades_train": 40,
            "minimum_independent_trades_validation": 20,
        },
    }


def test_test_only_schema_is_impossible_through_production_admission() -> None:
    candidate = _synthetic_test_candidate()
    assert all(not schema_id.startswith("TEST_") for schema_id in PRODUCTION_BEHAVIOR_SCHEMAS)

    with pytest.raises(RuntimeError, match="unsupported behavior schema shape"):
        resolve_behavior_schema_id(candidate)
    with pytest.raises(RuntimeError, match="unsupported behavior schema shape"):
        strategy_behavior_sha256(candidate)
    with pytest.raises(RuntimeError, match="unsupported behavior schema shape"):
        validate_predeclaration(candidate, rejected_entries=[])

    # Regression code can opt in process-locally; this cannot be selected by a
    # candidate field and is never active in production admission by default.
    with allow_test_behavior_schemas():
        assert resolve_behavior_schema_id(candidate) == "TEST_SYNTHETIC_LIQUIDITY_V1"
        validate_predeclaration(candidate, rejected_entries=[])


def test_cohort_dataset_instance_changes_do_not_mint_new_behavior_identity() -> None:
    original = _breadth_design()
    original_behavior = strategy_behavior_sha256(original)
    original_scientific = scientific_design_sha256(original)

    for field, replacement in (
        ("normalized_rows_sha256", "f" * 64),
        ("normalized_row_count", 40000),
        ("coverage_end_utc", "2026-09-20T03:00:00+00:00"),
        ("selection_train_end_utc", "2026-04-29T23:00:00+00:00"),
        ("selection_validation_end_utc", "2026-08-30T23:00:00+00:00"),
        ("protected_oos_end_utc", "2026-09-20T03:00:00+00:00"),
    ):
        changed = copy.deepcopy(original)
        changed["data_contract"][field] = replacement
        assert strategy_behavior_sha256(changed) == original_behavior
        assert scientific_design_sha256(changed) != original_scientific


def test_behavior_defining_universe_change_still_changes_behavior_identity() -> None:
    original = _breadth_design()
    changed = copy.deepcopy(original)
    changed["data_contract"]["fixed_instruments"] = [
        "BTC-USDT-SWAP",
        "ETH-USDT-SWAP",
    ]
    assert strategy_behavior_sha256(changed) != strategy_behavior_sha256(original)


def test_rejected_btc_leadlag_dataset_rehash_cannot_resurrect_design() -> None:
    entries = load_rejected_fingerprints()
    rejected = next(
        entry
        for entry in entries
        if entry.get("fingerprint_id") == "DISC-BTC-LEADLAG-001-v1"
    )
    original = copy.deepcopy(rejected["projection"])
    changed = copy.deepcopy(original)
    changed["data_contract"]["normalized_rows_sha256"] = "f" * 64

    assert strategy_behavior_sha256(changed) == strategy_behavior_sha256(original)
    assert scientific_design_sha256(changed) != scientific_design_sha256(original)
