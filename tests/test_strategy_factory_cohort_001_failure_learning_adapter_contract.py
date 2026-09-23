from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = (
    ROOT
    / "orchestration"
    / "cohorts"
    / "strategy_factory_cohort_001_failure_learning_adapter_contract.json"
)


def _load() -> dict:
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


def test_failure_learning_adapter_contract_identity_is_deterministic() -> None:
    payload = _load()
    detached = dict(payload)
    expected = detached.pop("contract_sha256")
    detached.pop("contract_hash_definition")
    encoded = json.dumps(
        detached,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    assert hashlib.sha256(encoded).hexdigest() == expected


def test_failure_learning_adapter_preserves_frozen_cost_and_independence_semantics() -> None:
    payload = _load()
    mapping = payload["mapping"]
    rules = payload["scientific_rules"]
    assert mapping["validation.trades"] == "validation.independent_events"
    assert mapping["validation.gross_mean_bps"].startswith("failure_diagnostics.mean_0bps * 10000")
    assert rules["raw_trade_count_may_substitute_for_independent_validation_events"] is False
    assert rules["cost_stress_must_exactly_cover_frozen_multipliers"] == [1.0, 2.0, 3.0]
    rows = mapping["cost_stress"]
    assert [row["multiplier"] for row in rows] == [1.0, 2.0, 3.0]
    assert rows[0]["net_mean_bps"] == "validation.mean_24bps * 10000 when defined"
    assert rows[1]["net_mean_bps"] == "failure_diagnostics.mean_48bps * 10000 when defined"
    assert rows[2]["net_mean_bps"] == "validation.mean_72bps * 10000 when defined"
    assert rules["supplemental_0bps_48bps_and_winner_share_must_be_recomputed_from_the_same_validation_trade_stream_and_cross_asset_independent_event_clustering"] is True
    assert rules["gross_mean_must_not_be_reconstructed_by_adding_flat_round_trip_cost_to_independent_event_net_mean"] is True
    assert rules["undefined_sparse_metrics_must_not_be_fabricated_zero_filled_or_finite_capped"] is True
    assert rules["profit_factor_no_losses_must_preserve_mathematical_positive_infinity_semantics_without_nonstandard_JSON_numbers"] is True
    assert rules["no_new_48bps_promotion_gate_is_created"] is True
    correction = payload["correction"]
    assert correction["classification"] == "PRE_OUTCOME_FAILURE_LEARNING_ACCOUNTING_DEFECT"
    assert correction["outcomes_read"] is False


def test_failure_learning_adapter_fails_closed_on_authority_and_preserves_stage1_precedence() -> None:
    payload = _load()
    authority = payload["authority"]
    rules = payload["scientific_rules"]
    locks = payload["evidence_locks"]
    implementation = payload["implementation_state"]

    assert authority["public_canonical_minting_available"] is False
    assert authority["certified_dataset_adapter_required"] is True
    assert authority["test_only_or_caller_supplied_results_may_mint_canonical_screen"] is False
    assert authority["required_source_evidence_status"] == "CERTIFIED_COHORT_DEVELOPMENT_ONLY"
    assert set(authority["required_bindings"]) == {
        "canonical_admission_receipt_sha256",
        "selection_dataset_receipt_sha256",
        "stage1_binding_receipt_sha256",
        "stage1_execution_contract_sha256",
    }
    assert rules["underpowered_catastrophic_tail_remains_rejection_eligible_in_failure_learning"] is True
    assert rules["ordinary_underpower_without_sufficient_tail_evidence_is_inconclusive"] is True
    assert rules["stage1_status_precedence_must_remain_unchanged"] is True
    assert rules["failure_learning_may_reject_tail_risk_from_preserved_diagnostics_even_when_stage1_status_is_INCONCLUSIVE_POWER"] is True
    assert mapping_risk_keys(payload) == {
        "risk.worst_event_net_bps",
        "risk.winner_concentration_share",
        "risk.without_best_net_mean_bps",
    }
    assert implementation == {
        "supplemental_failure_diagnostics_implemented": True,
        "private_schema_mapper_implemented_for_fully_defined_metrics": True,
        "sparse_result_schema_compatible_with_511": True,
        "canonical_certified_dataset_adapter_implemented": False,
    }
    target = payload["target_failure_learning_contract"]
    assert target["source_head_sha_observed"] == (
        "3553a602892fc911f917664c8cfe502d877835bf"
    )
    assert target["sparse_metric_schema_repair_required_before_canonical_consumption"] is False
    assert target["integration_required_before_canonical_consumption"] is True
    assert authority["protected_oos_opened"] is False
    assert authority["genuine_forward_opened"] is False
    assert authority["broker_connected"] is False
    assert authority["trade_authority"] is False
    assert authority["promotion_authority"] is False
    assert locks["strategy_outcomes_read_to_form_contract"] is False
    assert locks["protected_oos_opened"] is False
    assert locks["genuine_forward_opened"] is False
    assert locks["post_outcome_mapping_changes_allowed"] is False


def mapping_risk_keys(payload: dict) -> set[str]:
    return {key for key in payload["mapping"] if key.startswith("risk.")}
