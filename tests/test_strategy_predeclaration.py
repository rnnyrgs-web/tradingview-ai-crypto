from __future__ import annotations

import copy

import pytest

from orchestration.scientific_design_identity import scientific_design_sha256
from orchestration.strategy_predeclaration import (
    freeze_predeclaration,
    predeclaration_sha256,
    validate_predeclaration,
)


def _candidate() -> dict:
    return {
        "schema_version": 1,
        "hypothesis_id": "DISC-SYNTHETIC-MECHANISM-001",
        "fingerprint_id": "DISC-SYNTHETIC-MECHANISM-001-v1",
        "family": "synthetic_mechanism",
        "economic_mechanism": "A temporary liquidity imbalance should mean-revert only after quoted stress normalizes.",
        "hypothesis": "Post-shock normalization predicts positive after-cost reversion over the frozen holding window.",
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
            "fees_bps": 10.0,
            "spread_bps": 2.0,
            "slippage_bps": 3.0,
            "funding_bps_per_day": 0.0,
            "stress_multipliers": [1.0, 2.0, 3.0],
        },
        "search_plan": {
            "multiple_testing_family_id": "DISC-SYNTHETIC-MECHANISM-FAMILY-001",
            "planned_hypothesis_count": 4,
            "planned_parameter_variants": 3,
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


def test_freeze_is_deterministic_and_detached():
    original = _candidate()
    frozen = freeze_predeclaration(original, rejected_entries=[])
    reordered = {key: original[key] for key in reversed(list(original))}
    second = freeze_predeclaration(reordered, rejected_entries=[])

    assert frozen["contract_sha256"] == second["contract_sha256"]
    assert frozen["scientific_design_sha256"] == second["scientific_design_sha256"]
    assert frozen["contract_sha256"] == predeclaration_sha256(frozen)
    assert frozen["scientific_design_sha256"] == scientific_design_sha256(frozen)
    assert "contract_sha256" not in original
    assert "scientific_design_sha256" not in original

    original["signal_rules"]["entry_condition"] = "mutated after freeze"
    assert frozen["signal_rules"]["entry_condition"] == "frozen before outcomes"


def test_behavior_change_requires_new_digests():
    first = freeze_predeclaration(_candidate(), rejected_entries=[])
    changed = _candidate()
    changed["execution_rules"]["entry_delay_bars"] = 2
    second = freeze_predeclaration(changed, rejected_entries=[])
    assert first["scientific_design_sha256"] != second["scientific_design_sha256"]
    assert first["contract_sha256"] != second["contract_sha256"]


def test_labels_and_display_prose_do_not_change_scientific_design_identity():
    first = _candidate()
    renamed = copy.deepcopy(first)
    renamed["hypothesis_id"] = "RENAMED-HYPOTHESIS"
    renamed["fingerprint_id"] = "RENAMED-HYPOTHESIS-v9"
    renamed["family"] = "cosmetic_new_family_label"
    renamed["economic_mechanism"] = "Rewritten explanatory prose with the exact same executable design."
    renamed["hypothesis"] = "Different display wording only."

    assert scientific_design_sha256(first) == scientific_design_sha256(renamed)

    first_frozen = freeze_predeclaration(first, rejected_entries=[])
    renamed_frozen = freeze_predeclaration(renamed, rejected_entries=[])
    assert first_frozen["scientific_design_sha256"] == renamed_frozen["scientific_design_sha256"]
    assert first_frozen["contract_sha256"] != renamed_frozen["contract_sha256"]


def test_renamed_clone_of_rejected_scientific_design_is_rejected():
    original = _candidate()
    rejected = [{
        "fingerprint_id": "OLD-REJECTED-v1",
        "do_not_resubmit_same_fingerprint": True,
        "semantic_identity_status": "BACKFILLED_STRUCTURED_CONTRACT",
        "scientific_design_sha256": scientific_design_sha256(original),
    }]
    clone = copy.deepcopy(original)
    clone["hypothesis_id"] = "COSMETIC-RESCUE"
    clone["fingerprint_id"] = "COSMETIC-RESCUE-v1"
    clone["family"] = "renamed_family"
    clone["economic_mechanism"] = "New prose cannot reset a rejected executable design."
    clone["hypothesis"] = "Renamed display hypothesis."

    with pytest.raises(RuntimeError, match="rejected scientific design"):
        validate_predeclaration(clone, rejected_entries=rejected)


def test_material_behavior_change_gets_fresh_design_identity_but_keeps_search_ancestry():
    original = _candidate()
    original_digest = scientific_design_sha256(original)
    rejected = [{
        "fingerprint_id": "OLD-REJECTED-v1",
        "do_not_resubmit_same_fingerprint": True,
        "semantic_identity_status": "BACKFILLED_STRUCTURED_CONTRACT",
        "scientific_design_sha256": original_digest,
    }]

    successor = copy.deepcopy(original)
    successor["hypothesis_id"] = "MATERIAL-SUCCESSOR"
    successor["fingerprint_id"] = "MATERIAL-SUCCESSOR-v1"
    successor["signal_rules"]["entry_condition"] = "independent materially different frozen rule"
    assert successor["search_plan"]["multiple_testing_family_id"] == original["search_plan"]["multiple_testing_family_id"]
    assert scientific_design_sha256(successor) != original_digest
    validate_predeclaration(successor, rejected_entries=rejected)


def test_exact_rejected_fingerprint_cannot_be_resubmitted():
    rejected = [
        {
            "fingerprint_id": "DISC-SYNTHETIC-MECHANISM-001-v1",
            "do_not_resubmit_same_fingerprint": True,
        }
    ]
    with pytest.raises(RuntimeError, match="rejected fingerprint"):
        validate_predeclaration(_candidate(), rejected_entries=rejected)


def test_explicit_unreconstructible_rejected_predecessor_fails_closed():
    rejected = [{
        "fingerprint_id": "LEGACY-REJECTED-v1",
        "do_not_resubmit_same_fingerprint": True,
        "semantic_identity_status": "SEMANTIC_BACKFILL_UNAVAILABLE",
    }]
    candidate = _candidate()
    candidate["predecessor_fingerprints"] = ["LEGACY-REJECTED-v1"]
    with pytest.raises(RuntimeError, match="SEMANTIC_BACKFILL_UNAVAILABLE"):
        validate_predeclaration(candidate, rejected_entries=rejected)


def test_outcome_derived_fields_are_forbidden_anywhere_in_contract():
    candidate = _candidate()
    candidate["validation_plan"]["profit_factor"] = 1.8
    with pytest.raises(RuntimeError, match="outcome-derived fields"):
        validate_predeclaration(candidate, rejected_entries=[])


def test_protected_oos_and_forward_evidence_must_stay_locked():
    candidate = _candidate()
    candidate["protected_evidence"]["untouched_oos_opened"] = True
    with pytest.raises(RuntimeError, match="untouched OOS"):
        validate_predeclaration(candidate, rejected_entries=[])

    candidate = _candidate()
    candidate["protected_evidence"]["genuine_forward_opened"] = True
    with pytest.raises(RuntimeError, match="genuine-forward"):
        validate_predeclaration(candidate, rejected_entries=[])


def test_formation_cutoff_requires_timezone_and_search_breadth_is_predeclared():
    candidate = _candidate()
    candidate["formation_cutoff"] = "2026-09-20T00:00:00"
    with pytest.raises(RuntimeError, match="explicit timezone"):
        validate_predeclaration(candidate, rejected_entries=[])

    candidate = _candidate()
    candidate["search_plan"]["planned_parameter_variants"] = 0
    with pytest.raises(RuntimeError, match="positive integer"):
        validate_predeclaration(candidate, rejected_entries=[])


def test_cost_contract_cannot_hide_or_reduce_base_costs():
    candidate = _candidate()
    candidate["cost_model"]["stress_multipliers"] = [0.5, 1.0, 2.0]
    with pytest.raises(RuntimeError, match="cannot reduce"):
        validate_predeclaration(candidate, rejected_entries=[])

    candidate = _candidate()
    del candidate["cost_model"]["slippage_bps"]
    with pytest.raises(RuntimeError, match="cost_model missing fields"):
        validate_predeclaration(candidate, rejected_entries=[])


def test_frozen_digest_detects_post_freeze_tampering():
    frozen = freeze_predeclaration(_candidate(), rejected_entries=[])
    tampered = copy.deepcopy(frozen)
    tampered["signal_rules"]["entry_condition"] = "post-outcome rescue rule"
    with pytest.raises(RuntimeError, match="scientific_design_sha256"):
        validate_predeclaration(tampered, rejected_entries=[])


def test_caller_supplied_semantic_digest_is_verified_not_trusted():
    candidate = _candidate()
    candidate["scientific_design_sha256"] = "0" * 64
    with pytest.raises(RuntimeError, match="scientific_design_sha256"):
        validate_predeclaration(candidate, rejected_entries=[])


def test_frozen_contract_must_persist_scientific_design_identity():
    frozen = freeze_predeclaration(_candidate(), rejected_entries=[])
    del frozen["scientific_design_sha256"]
    with pytest.raises(RuntimeError, match="must persist scientific_design_sha256"):
        validate_predeclaration(frozen, rejected_entries=[])


def test_validation_contract_is_fail_closed():
    for field in (
        "chronological",
        "selection_uses_training_and_validation_only",
        "untouched_oos_required",
        "genuine_forward_required",
    ):
        candidate = _candidate()
        candidate["validation_plan"][field] = False
        with pytest.raises(RuntimeError, match=field):
            validate_predeclaration(candidate, rejected_entries=[])
