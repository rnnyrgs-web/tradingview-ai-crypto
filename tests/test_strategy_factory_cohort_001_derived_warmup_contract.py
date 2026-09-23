from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from orchestration.cohorts.strategy_factory_cohort_001_warmup import (
    DECLARED_WARMUP_HOURS,
    DERIVED_FIRST_ELIGIBLE_INDEX,
    first_eligible_index,
    structurally_eligible,
)

ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_PATH = ROOT / "orchestration/cohorts/strategy_factory_cohort_001_derived_warmup_contract.json"
BINDING_PATH = ROOT / "orchestration/cohorts/strategy_factory_cohort_001_stage1_binding.json"
EXECUTION_PATH = ROOT / "orchestration/cohorts/strategy_factory_cohort_001_stage1_execution_contract.json"

EXPECTED = {
    "DISC-RESIDUAL-REV-001-v1": (720, 336 + 720),
    "DISC-SIGNED-VOLUME-DRIFT-001-v1": (720, 720 + 3 + 720),
    "DISC-LOWVOL-DRIFT-REV-001-v1": (720, 8 + 720),
    "DISC-MODERATEVOL-AUTOCORR-001-v1": (2160, 24 + 2160),
}


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _canonical_sha256(payload: dict) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def test_warmup_artifact_is_outcome_blind_and_self_digested() -> None:
    artifact = _load(ARTIFACT_PATH)
    claimed = artifact.pop("payload_sha256_excluding_this_field")
    assert claimed == _canonical_sha256(artifact)
    assert artifact["status"] == "OUTCOME_BLIND_DERIVED_EXECUTION_SEMANTICS"
    assert artifact["interpretation"]["warmup_hours_semantics"] == "LOWER_BOUND_ONLY"
    assert artifact["interpretation"]["identity_effect"].startswith("NONE:")
    assert artifact["evidence_locks"] == {
        "broker_connected": False,
        "genuine_forward_opened": False,
        "partial_reference_windows_allowed": False,
        "promotion_authority": False,
        "protected_oos_opened": False,
        "reuse_current_beta_for_historical_residuals_allowed": False,
        "strategy_outcomes_read": False,
        "threshold_tuning_allowed": False,
        "trade_authority": False,
    }


def test_derived_warmup_contract_binds_current_stage1_receipts_and_identities() -> None:
    artifact = _load(ARTIFACT_PATH)
    binding = _load(BINDING_PATH)
    execution = _load(EXECUTION_PATH)

    assert artifact["source_stage1_binding_receipt_sha256"] == binding["binding_receipt_sha256"]
    assert artifact["source_execution_contract_sha256"] == execution["execution_contract_sha256"]

    admitted = {row["fingerprint_id"]: row for row in binding["eligible_stage1_candidates"]}
    assert set(artifact["affected_candidates"]) == set(EXPECTED)
    for candidate_id, candidate in artifact["affected_candidates"].items():
        source = admitted[candidate_id]
        assert candidate["scientific_design_sha256"] == source["scientific_design_sha256"]
        assert candidate["strategy_behavior_sha256"] == source["strategy_behavior_sha256"]
        assert candidate["contract_sha256"] == source["contract_sha256"]


def test_nested_pit_history_floors_are_exact_and_stricter_than_declared_where_required() -> None:
    artifact = _load(ARTIFACT_PATH)
    for candidate_id, (declared, derived) in EXPECTED.items():
        record = artifact["affected_candidates"][candidate_id]
        assert DECLARED_WARMUP_HOURS[candidate_id] == declared
        assert DERIVED_FIRST_ELIGIBLE_INDEX[candidate_id] == derived
        assert record["declared_warmup_hours"] == declared
        assert record["derived_first_eligible_index"] == derived
        assert first_eligible_index(candidate_id) == derived
        assert not structurally_eligible(candidate_id, derived - 1)
        assert structurally_eligible(candidate_id, derived)
        assert derived >= declared


def test_structural_eligibility_rejects_invalid_indices_and_unknown_candidates() -> None:
    with pytest.raises(ValueError):
        structurally_eligible("DISC-RESIDUAL-REV-001-v1", -1)
    with pytest.raises(ValueError):
        structurally_eligible("DISC-RESIDUAL-REV-001-v1", True)
    with pytest.raises(ValueError):
        first_eligible_index("UNKNOWN")
