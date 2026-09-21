from __future__ import annotations

import copy

import pytest

from orchestration.scientific_design_identity import strategy_behavior_sha256
from orchestration.strategy_predeclaration import validate_predeclaration


def _candidate() -> dict:
    return {
        "schema_version": 1,
        "hypothesis_id": "DISC-SCALAR-GUARD-001",
        "fingerprint_id": "DISC-SCALAR-GUARD-001-v1",
        "family": "scalar_guard",
        "economic_mechanism": "Frozen typed parameters must not change representation after rejection.",
        "hypothesis": "Representation-only changes must not create a fresh executable identity.",
        "target_markets": ["BTC-USDC", "ETH-USDC"],
        "target_timeframes": ["1h"],
        "formation_cutoff": "2026-09-20T00:00:00+00:00",
        "data_contract": {
            "source": "public timestamped venue data",
            "point_in_time": True,
            "historical_universe": "fixed_predeclared_assets",
        },
        "signal_rules": {
            "threshold": 2.0,
            "entry_condition": "abs(residual_zscore) >= 2.0 and liquidity < 1e6",
        },
        "execution_rules": {
            "entry_delay_bars": 1,
            "maximum_hold_bars": 24,
            "one_position_per_instrument": True,
            "exit_rule": "fixed_holding_window",
        },
        "cost_model": {
            "fees_bps": 10.0,
            "spread_bps": 2.0,
            "slippage_bps": 3.0,
            "funding_bps_per_day": 0.0,
            "stress_multipliers": [1.0, 2.0, 3.0],
        },
        "search_plan": {
            "multiple_testing_family_id": "DISC-SCALAR-GUARD-FAMILY-001",
            "planned_hypothesis_count": 2,
            "planned_parameter_variants": 2,
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


def _rejection_for(candidate: dict) -> dict:
    return {
        "fingerprint_id": "OLD-SCALAR-REJECTED-v1",
        "do_not_resubmit_same_fingerprint": True,
        "semantic_identity_status": "BACKFILLED_STRUCTURED_CONTRACT",
        "strategy_behavior_sha256": strategy_behavior_sha256(candidate),
    }


@pytest.mark.parametrize("encoded", ["1", "1e0", "-0.0", "  1  "])
def test_numeric_literal_string_cannot_rescue_rejected_execution_rule(encoded: str) -> None:
    original = _candidate()
    rejected = [_rejection_for(original)]
    rescue = copy.deepcopy(original)
    rescue["hypothesis_id"] = "RENAMED-SCALAR-RESCUE"
    rescue["fingerprint_id"] = "RENAMED-SCALAR-RESCUE-v1"
    rescue["execution_rules"]["entry_delay_bars"] = encoded

    with pytest.raises(RuntimeError, match="native JSON type"):
        validate_predeclaration(rescue, rejected_entries=rejected)


def test_boolean_literal_string_cannot_rescue_rejected_behavior() -> None:
    original = _candidate()
    rejected = [_rejection_for(original)]
    rescue = copy.deepcopy(original)
    rescue["hypothesis_id"] = "RENAMED-BOOL-RESCUE"
    rescue["fingerprint_id"] = "RENAMED-BOOL-RESCUE-v1"
    rescue["data_contract"]["point_in_time"] = "true"

    with pytest.raises(RuntimeError, match="native JSON type"):
        validate_predeclaration(rescue, rejected_entries=rejected)


def test_null_literal_string_is_not_an_admissible_behavior_parameter() -> None:
    candidate = _candidate()
    candidate["execution_rules"]["optional_stop"] = "null"
    with pytest.raises(RuntimeError, match="native JSON type"):
        validate_predeclaration(candidate, rejected_entries=[])


def test_descriptive_expression_with_numbers_remains_a_string() -> None:
    candidate = _candidate()
    validate_predeclaration(candidate, rejected_entries=[])


def test_genuine_native_numeric_behavior_change_remains_distinct() -> None:
    original = _candidate()
    changed = copy.deepcopy(original)
    changed["hypothesis_id"] = "DISC-SCALAR-GUARD-002"
    changed["fingerprint_id"] = "DISC-SCALAR-GUARD-002-v1"
    changed["execution_rules"]["entry_delay_bars"] = 2

    assert strategy_behavior_sha256(changed) != strategy_behavior_sha256(original)
    validate_predeclaration(changed, rejected_entries=[_rejection_for(original)])
