from __future__ import annotations

import copy

import pytest

from orchestration.strategy_predeclaration import (
    _validate_scientific_safety_flags,
    validate_predeclaration,
)


def _candidate() -> dict:
    return {
        "schema_version": 1,
        "hypothesis_id": "DISC-SAFETY-FLAG-REGRESSION-001",
        "fingerprint_id": "DISC-SAFETY-FLAG-REGRESSION-001-v1",
        "family": "safety_flag_regression",
        "economic_mechanism": "Synthetic admission safety regression only.",
        "hypothesis": "Unsafe nested scientific-control booleans must fail closed.",
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
            "multiple_testing_family_id": "DISC-SAFETY-FLAG-FAMILY-001",
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


def test_point_in_time_false_is_rejected_by_authoritative_admission():
    candidate = _candidate()
    candidate["data_contract"]["point_in_time"] = False
    with pytest.raises(RuntimeError, match=r"data_contract\.point_in_time must be true"):
        validate_predeclaration(candidate, rejected_entries=[])


@pytest.mark.parametrize(
    ("section", "field", "unsafe_value", "expected_text"),
    [
        ("data_contract", "point_in_time", False, "data_contract.point_in_time must be true"),
        (
            "data_contract",
            "screen_may_read_protected_oos",
            True,
            "data_contract.screen_may_read_protected_oos must be false",
        ),
        (
            "data_contract",
            "completed_bars_only",
            False,
            "data_contract.completed_bars_only must be true",
        ),
        (
            "data_contract",
            "asset_substitution_allowed",
            True,
            "data_contract.asset_substitution_allowed must be false",
        ),
        (
            "cost_model",
            "selection_uses_max_stress",
            False,
            "cost_model.selection_uses_max_stress must be true",
        ),
    ],
)
def test_all_scientific_safety_flags_fail_closed_when_flipped(
    section: str,
    field: str,
    unsafe_value: bool,
    expected_text: str,
):
    candidate = _candidate()
    candidate = copy.deepcopy(candidate)
    candidate[section][field] = unsafe_value
    with pytest.raises(RuntimeError, match=expected_text.replace(".", r"\.")):
        _validate_scientific_safety_flags(candidate)


def test_safe_values_do_not_block_schema_specific_validation():
    candidate = _candidate()
    candidate["data_contract"].update(
        {
            "screen_may_read_protected_oos": False,
            "completed_bars_only": True,
            "asset_substitution_allowed": False,
        }
    )
    candidate["cost_model"]["selection_uses_max_stress"] = True
    _validate_scientific_safety_flags(candidate)
