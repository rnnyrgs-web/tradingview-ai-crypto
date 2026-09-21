from __future__ import annotations

import copy

import pytest

from orchestration.rejected_fingerprints import load_rejected_fingerprints
from orchestration.scientific_design_identity import (
    BEHAVIOR_FIELD_SEMANTICS_VERSION,
    strategy_behavior_sha256,
)
from orchestration.strategy_behavior_schema import (
    BEHAVIOR_SCHEMA_REGISTRY_VERSION,
    resolve_behavior_schema_id,
)
from orchestration.strategy_predeclaration import validate_predeclaration


def _candidate() -> dict:
    return {
        "schema_version": 1,
        "hypothesis_id": "DISC-FIELD-SEMANTICS-001",
        "fingerprint_id": "DISC-FIELD-SEMANTICS-001-v1",
        "family": "field_semantics_regression",
        "economic_mechanism": "Only explicitly behavior-driving fields may alter executable identity.",
        "hypothesis": "Caller metadata inside behavior containers must fail closed.",
        "target_markets": ["BTC-USDC", "ETH-USDC"],
        "target_timeframes": ["1h"],
        "formation_cutoff": "2026-09-21T00:00:00+00:00",
        "data_contract": {
            "source": "public timestamped venue data",
            "point_in_time": True,
            "historical_universe": "fixed_predeclared_assets",
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
            "multiple_testing_family_id": "DISC-FIELD-SEMANTICS-FAMILY-001",
            "planned_hypothesis_count": 2,
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


def _rejection_for(candidate: dict) -> dict:
    return {
        "fingerprint_id": "OLD-FIELD-SEMANTICS-REJECTED-v1",
        "do_not_resubmit_same_fingerprint": True,
        "semantic_identity_status": "BACKFILLED_STRUCTURED_CONTRACT",
        "strategy_behavior_sha256": strategy_behavior_sha256(candidate),
    }


def test_behavior_field_semantics_contract_is_versioned() -> None:
    assert BEHAVIOR_FIELD_SEMANTICS_VERSION == 2
    assert BEHAVIOR_SCHEMA_REGISTRY_VERSION == 1
    assert resolve_behavior_schema_id(_candidate()) == "TEST_FIELD_SEMANTICS_V1"


@pytest.mark.parametrize(
    ("section", "field"),
    [
        ("data_contract", "display_note"),
        ("signal_rules", "description"),
        ("execution_rules", "presentation_label"),
        ("cost_model", "analyst_comment"),
    ],
)
def test_inert_nested_metadata_cannot_create_fresh_behavior_identity(
    section: str,
    field: str,
) -> None:
    original = _candidate()
    rejected = [_rejection_for(original)]
    rescue = copy.deepcopy(original)
    rescue["hypothesis_id"] = "RENAMED-FIELD-SEMANTICS-RESCUE"
    rescue["fingerprint_id"] = "RENAMED-FIELD-SEMANTICS-RESCUE-v1"
    rescue["economic_mechanism"] = "Cosmetic rewrite only."
    rescue["hypothesis"] = "Cosmetic rewrite only."
    rescue[section][field] = "same executable behavior"

    with pytest.raises(RuntimeError, match="undeclared behavior field"):
        strategy_behavior_sha256(rescue)
    with pytest.raises(RuntimeError, match="undeclared behavior field"):
        validate_predeclaration(rescue, rejected_entries=rejected)


def test_nested_behavior_mapping_fails_closed_until_path_schema_exists() -> None:
    candidate = _candidate()
    candidate["signal_rules"]["entry_condition"] = {"expression": "frozen"}
    with pytest.raises(RuntimeError, match="nested behavior mappings require"):
        strategy_behavior_sha256(candidate)


def test_genuine_supported_behavior_change_remains_distinct() -> None:
    original = _candidate()
    changed = copy.deepcopy(original)
    changed["execution_rules"]["entry_delay_bars"] = 2
    assert strategy_behavior_sha256(changed) != strategy_behavior_sha256(original)


def test_real_rejected_projection_cannot_accept_inert_nested_note() -> None:
    entries = load_rejected_fingerprints()
    rejected = next(
        entry
        for entry in entries
        if entry.get("fingerprint_id") == "DISC-BTC-LEADLAG-001-v1"
    )
    projection = copy.deepcopy(rejected["projection"])
    projection["signal_rules"]["display_note"] = "same executable lead-lag rules"
    with pytest.raises(RuntimeError, match="undeclared behavior field"):
        strategy_behavior_sha256(projection)


def test_known_cross_mechanism_field_cannot_rescue_real_rejected_design() -> None:
    """A recognized field from another executor must not mint a fresh identity."""
    entries = load_rejected_fingerprints()
    rejected = next(
        entry
        for entry in entries
        if entry.get("fingerprint_id") == "DISC-BTC-LEADLAG-001-v1"
    )
    projection = copy.deepcopy(rejected["projection"])
    original_digest = strategy_behavior_sha256(projection)
    assert resolve_behavior_schema_id(projection) == "DISC_BTC_LEADLAG_V1"

    # compression_quantile is legitimate for the volatility-breakout executor,
    # but inert for the lead/lag executor. The old global union admitted it.
    projection["signal_rules"]["compression_quantile"] = 0.2
    with pytest.raises(RuntimeError, match="unsupported behavior schema shape"):
        strategy_behavior_sha256(projection)

    genuine_change = copy.deepcopy(rejected["projection"])
    genuine_change["signal_rules"]["underreaction_gap_min"] = 0.006
    assert resolve_behavior_schema_id(genuine_change) == "DISC_BTC_LEADLAG_V1"
    assert strategy_behavior_sha256(genuine_change) != original_digest
