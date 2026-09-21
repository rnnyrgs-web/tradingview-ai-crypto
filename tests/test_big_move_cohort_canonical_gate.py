import json
from pathlib import Path

import pytest

from big_move_cohort_canonical_gate import (
    CANONICAL_CONTRACT_ARTIFACT_ID,
    CANONICAL_CONTRACT_GIT_BLOB_SHA,
    DERIVED_OUTPUT_BINDING_BLOCKERS,
    evaluate_authoritative_coverage,
    load_canonical_contract,
)


def test_canonical_contract_is_exactly_pinned():
    contract = load_canonical_contract()
    assert contract["artifact_id"] == CANONICAL_CONTRACT_ARTIFACT_ID
    assert contract["coverage_thresholds"] == {
        "minimum_assets": 12,
        "minimum_snapshots": 624,
        "minimum_decisions_per_asset": 52,
    }
    assert len(CANONICAL_CONTRACT_GIT_BLOB_SHA) == 40


def test_authoritative_gate_keeps_outcomes_sealed_while_derived_outputs_are_unbound():
    result = evaluate_authoritative_coverage([])
    assert result["status"] == "COVERAGE_BLOCKED"
    assert result["structural_coverage_status"] == "COVERAGE_BLOCKED"
    assert result["outcome_access"] == "SEALED"
    assert result["labels_opened"] is False
    assert result["prediction_authority"] is False
    assert result["trade_authority"] is False
    assert result["broker_connected"] is False
    assert result["live_trading"] is False
    assert set(result["derived_output_binding_blockers"]) == set(DERIVED_OUTPUT_BINDING_BLOCKERS)
    assert all(
        f"DERIVED_OUTPUT_NOT_DETERMINISTICALLY_BOUND:{field}" in result["blockers"]
        for field in DERIVED_OUTPUT_BINDING_BLOCKERS
    )


def test_modified_threshold_contract_cannot_become_authoritative(tmp_path):
    repo_root = Path(__file__).parents[1]
    source = repo_root / "money_intelligence/2x_cohort_001_preflight_contract.json"
    contract = json.loads(source.read_text())
    contract["coverage_thresholds"]["minimum_assets"] = 1
    target = tmp_path / "money_intelligence/2x_cohort_001_preflight_contract.json"
    target.parent.mkdir(parents=True)
    target.write_text(json.dumps(contract, indent=2) + "\n")

    with pytest.raises(ValueError, match="drifted from frozen Git blob"):
        load_canonical_contract(tmp_path)


def test_authoritative_api_accepts_no_caller_contract_override():
    with pytest.raises(TypeError):
        evaluate_authoritative_coverage([], contract={"coverage_thresholds": {}})
