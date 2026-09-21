from __future__ import annotations

import copy

import pytest

from orchestration.rejected_fingerprints import (
    load_rejected_fingerprints,
    semantic_rejection_record,
)
from orchestration.scientific_design_identity import (
    SCIENTIFIC_IDENTITY_VERSION,
    SCIENTIFIC_SCALAR_CANONICALIZATION_VERSION,
    STRATEGY_BEHAVIOR_IDENTITY_VERSION,
    scientific_design_sha256,
    strategy_behavior_sha256,
)
from orchestration.strategy_predeclaration import freeze_predeclaration, validate_predeclaration


def _candidate() -> dict:
    return {
        "schema_version": 1,
        "hypothesis_id": "DISC-BEHAVIOR-IDENTITY-001",
        "fingerprint_id": "DISC-BEHAVIOR-IDENTITY-001-v1",
        "family": "behavior_identity_regression",
        "economic_mechanism": "Synthetic identity regression only.",
        "hypothesis": "Equivalent executable behavior must share one no-rescue identity.",
        "target_markets": ["BTC-USDC", "ETH-USDC"],
        "target_timeframes": ["1h"],
        "formation_cutoff": "2026-09-20T00:00:00+00:00",
        "data_contract": {
            "source": "public timestamped venue data",
            "point_in_time": True,
        },
        "signal_rules": {
            "threshold": 2,
            "entry_condition": "frozen before outcomes",
        },
        "execution_rules": {
            "entry_delay_bars": 1,
            "exit_rule": "fixed_holding_window",
        },
        "cost_model": {
            "fees_bps": 10,
            "spread_bps": 2,
            "slippage_bps": 3,
            "funding_bps_per_day": 0,
            "stress_multipliers": [1, 2, 3],
        },
        "search_plan": {
            "multiple_testing_family_id": "DISC-BEHAVIOR-IDENTITY-FAMILY-001",
            "planned_hypothesis_count": 2,
            "planned_parameter_variants": 1,
        },
        "validation_plan": {
            "chronological": True,
            "selection_uses_training_and_validation_only": True,
            "untouched_oos_required": True,
            "genuine_forward_required": True,
            "minimum_trade_count": 40,
        },
        "protected_evidence": {
            "untouched_oos_opened": False,
            "genuine_forward_opened": False,
        },
    }


def test_behavior_identity_contract_versions_are_explicit():
    assert SCIENTIFIC_IDENTITY_VERSION == 2
    assert STRATEGY_BEHAVIOR_IDENTITY_VERSION == 1
    assert SCIENTIFIC_SCALAR_CANONICALIZATION_VERSION == 1


def test_integral_float_and_negative_zero_are_identity_equivalent():
    original = _candidate()
    equivalent = copy.deepcopy(original)
    equivalent["execution_rules"]["entry_delay_bars"] = 1.0
    equivalent["cost_model"]["funding_bps_per_day"] = -0.0
    equivalent["signal_rules"]["threshold"] = 2.0

    assert strategy_behavior_sha256(original) == strategy_behavior_sha256(equivalent)
    assert scientific_design_sha256(original) == scientific_design_sha256(equivalent)


def test_genuinely_distinct_nonintegral_numeric_parameter_changes_behavior_identity():
    original = _candidate()
    changed = copy.deepcopy(original)
    changed["signal_rules"]["threshold"] = 2.5

    assert strategy_behavior_sha256(original) != strategy_behavior_sha256(changed)
    assert scientific_design_sha256(original) != scientific_design_sha256(changed)


def test_validation_plan_only_change_cannot_resurrect_rejected_behavior():
    original = _candidate()
    rejected = [{
        "fingerprint_id": "OLD-REJECTED-v1",
        "do_not_resubmit_same_fingerprint": True,
        "semantic_identity_status": "BACKFILLED_STRUCTURED_CONTRACT",
        "scientific_design_sha256": scientific_design_sha256(original),
        "strategy_behavior_sha256": strategy_behavior_sha256(original),
    }]

    changed_validation = copy.deepcopy(original)
    changed_validation["hypothesis_id"] = "RENAMED-VALIDATION-RESCUE"
    changed_validation["fingerprint_id"] = "RENAMED-VALIDATION-RESCUE-v1"
    changed_validation["validation_plan"]["minimum_trade_count"] = 80

    assert scientific_design_sha256(original) != scientific_design_sha256(changed_validation)
    assert strategy_behavior_sha256(original) == strategy_behavior_sha256(changed_validation)
    with pytest.raises(RuntimeError, match="rejected strategy behavior"):
        validate_predeclaration(changed_validation, rejected_entries=rejected)


def test_numeric_representation_change_cannot_resurrect_rejected_behavior():
    original = _candidate()
    rejected = [{
        "fingerprint_id": "OLD-REJECTED-v1",
        "do_not_resubmit_same_fingerprint": True,
        "semantic_identity_status": "BACKFILLED_STRUCTURED_CONTRACT",
        "scientific_design_sha256": scientific_design_sha256(original),
        "strategy_behavior_sha256": strategy_behavior_sha256(original),
    }]
    equivalent = copy.deepcopy(original)
    equivalent["hypothesis_id"] = "NUMERIC-COSMETIC-RESCUE"
    equivalent["fingerprint_id"] = "NUMERIC-COSMETIC-RESCUE-v1"
    equivalent["execution_rules"]["entry_delay_bars"] = 1.0
    equivalent["cost_model"]["funding_bps_per_day"] = -0.0

    with pytest.raises(RuntimeError, match="rejected strategy behavior"):
        validate_predeclaration(equivalent, rejected_entries=rejected)


def test_frozen_predeclaration_persists_and_verifies_both_identities():
    frozen = freeze_predeclaration(_candidate(), rejected_entries=[])
    assert frozen["scientific_design_sha256"] == scientific_design_sha256(frozen)
    assert frozen["strategy_behavior_sha256"] == strategy_behavior_sha256(frozen)

    tampered = copy.deepcopy(frozen)
    tampered["strategy_behavior_sha256"] = "0" * 64
    with pytest.raises(RuntimeError, match="strategy_behavior_sha256"):
        validate_predeclaration(tampered, rejected_entries=[])


def test_canonical_rejected_memory_mechanically_verifies_behavior_digests():
    entries = load_rejected_fingerprints()
    structured = [
        entry
        for entry in entries
        if entry.get("semantic_identity_status") == "BACKFILLED_STRUCTURED_CONTRACT"
    ]
    assert structured
    for entry in structured:
        assert entry["scientific_design_sha256"] == scientific_design_sha256(entry["projection"])
        assert entry["strategy_behavior_sha256"] == strategy_behavior_sha256(entry["projection"])
        matched = semantic_rejection_record(entry["strategy_behavior_sha256"], entries)
        assert matched is not None
        assert matched["fingerprint_id"] == entry["fingerprint_id"]
