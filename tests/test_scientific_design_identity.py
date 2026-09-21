from __future__ import annotations

import copy

import pytest

from orchestration.rejected_fingerprints import (
    load_rejected_fingerprints,
    semantic_rejection_record,
)
from orchestration.scientific_design_identity import scientific_design_sha256
from orchestration.strategy_predeclaration import validate_predeclaration


def _candidate() -> dict:
    return {
        "schema_version": 1,
        "hypothesis_id": "DISC-IDENTITY-PERMUTATION-001",
        "fingerprint_id": "DISC-IDENTITY-PERMUTATION-001-v1",
        "family": "identity_regression",
        "economic_mechanism": "Synthetic mechanism used only to test canonical identity.",
        "hypothesis": "Equivalent set ordering must not create a new design identity.",
        "target_markets": ["BTC-USDC", "ETH-USDC", "SOL-USDC"],
        "target_timeframes": ["1h", "4h"],
        "formation_cutoff": "2026-09-20T00:00:00+00:00",
        "data_contract": {
            "source": "public timestamped venue data",
            "point_in_time": True,
            "historical_universe": "fixed_predeclared_assets",
            "fixed_instruments": ["BTC-USDC", "ETH-USDC", "SOL-USDC"],
        },
        "signal_rules": {
            "entry_condition": "frozen before outcomes",
            "ordered_sequence": ["first", "second"],
        },
        "execution_rules": {
            "entry_delay_bars": 1,
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
            "multiple_testing_family_id": "DISC-IDENTITY-PERMUTATION-FAMILY-001",
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


def test_unordered_market_timeframe_and_fixed_instrument_permutations_share_identity():
    original = _candidate()
    permuted = copy.deepcopy(original)
    permuted["target_markets"] = ["SOL-USDC", "BTC-USDC", "ETH-USDC"]
    permuted["target_timeframes"] = ["4h", "1h"]
    permuted["data_contract"]["fixed_instruments"] = ["ETH-USDC", "SOL-USDC", "BTC-USDC"]

    assert scientific_design_sha256(original) == scientific_design_sha256(permuted)

    rejected = [{
        "fingerprint_id": "OLD-REJECTED-v1",
        "do_not_resubmit_same_fingerprint": True,
        "semantic_identity_status": "BACKFILLED_STRUCTURED_CONTRACT",
        "scientific_design_sha256": scientific_design_sha256(original),
    }]
    permuted["hypothesis_id"] = "COSMETIC-PERMUTATION-RESCUE"
    permuted["fingerprint_id"] = "COSMETIC-PERMUTATION-RESCUE-v1"
    with pytest.raises(RuntimeError, match="rejected scientific design"):
        validate_predeclaration(permuted, rejected_entries=rejected)


def test_real_market_or_timeframe_membership_change_changes_identity():
    original = _candidate()

    market_change = copy.deepcopy(original)
    market_change["target_markets"].append("XRP-USDC")
    market_change["data_contract"]["fixed_instruments"].append("XRP-USDC")
    assert scientific_design_sha256(original) != scientific_design_sha256(market_change)

    timeframe_change = copy.deepcopy(original)
    timeframe_change["target_timeframes"].append("15m")
    assert scientific_design_sha256(original) != scientific_design_sha256(timeframe_change)


def test_genuinely_ordered_rule_sequence_remains_order_sensitive():
    original = _candidate()
    reordered_rules = copy.deepcopy(original)
    reordered_rules["signal_rules"]["ordered_sequence"] = ["second", "first"]

    assert scientific_design_sha256(original) != scientific_design_sha256(reordered_rules)


def test_actual_rejected_btc_leadlag_follower_permutation_stays_rejected():
    """The real structured BTC lead-lag reject cannot be rescued by follower ordering."""
    entries = load_rejected_fingerprints()
    rejected = next(
        entry for entry in entries if entry["fingerprint_id"] == "DISC-BTC-LEADLAG-001-v1"
    )
    original_projection = copy.deepcopy(rejected["projection"])
    original_digest = scientific_design_sha256(original_projection)
    assert original_digest == rejected["scientific_design_sha256"]

    permuted_projection = copy.deepcopy(original_projection)
    permuted_projection["data_contract"]["fixed_follower_instruments"] = [
        "SOL-USDT-SWAP",
        "ETH-USDT-SWAP",
    ]
    permuted_digest = scientific_design_sha256(permuted_projection)
    assert permuted_digest == original_digest
    matched = semantic_rejection_record(permuted_digest, entries)
    assert matched is not None
    assert matched["fingerprint_id"] == "DISC-BTC-LEADLAG-001-v1"

    membership_change = copy.deepcopy(original_projection)
    membership_change["data_contract"]["fixed_follower_instruments"] = ["ETH-USDT-SWAP"]
    changed_digest = scientific_design_sha256(membership_change)
    assert changed_digest != original_digest
    assert semantic_rejection_record(changed_digest, entries) is None
