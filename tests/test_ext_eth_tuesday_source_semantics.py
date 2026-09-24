from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ATTESTATION_PATH = (
    ROOT
    / "orchestration"
    / "external_replication"
    / "ext_eth_tuesday_drift_001_source_semantics.json"
)
PREDECLARATION_PATH = (
    ROOT
    / "orchestration"
    / "external_replication"
    / "ext_eth_tuesday_drift_001_v1.json"
)
EXPECTED_SHA256 = "0d5d5b5a82c790464aa3718b1fef2e0d889734e607408e0e7678d99ed7df50dc"
PARENT_SHA256 = "6ddab16cbfbb846d0690dced9e2128244e2bc9ec6221243a02cb48fea4b5c98b"


def _canonical_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_source_semantics_attestation_digest_and_chronology() -> None:
    attestation = _load(ATTESTATION_PATH)
    digest = attestation.pop("artifact_sha256")
    assert digest == EXPECTED_SHA256
    assert hashlib.sha256(_canonical_json(attestation)).hexdigest() == EXPECTED_SHA256
    assert attestation["parent_artifact_sha256"] == PARENT_SHA256
    assert attestation["formed_pre_outcome"] is True
    assert attestation["outcomes_read_to_form_attestation"] is False
    assert attestation["source"]["published_results_are_project_evidence"] is False


def test_paper_close_to_close_semantics_lock_existing_tuesday_boundaries() -> None:
    attestation = _load(ATTESTATION_PATH)
    predeclaration = _load(PREDECLARATION_PATH)
    source = attestation["source"]
    translation = attestation["boundary_translation"]
    signal = predeclaration["signal_rules"]

    assert "ln(CP_n) - ln(CP_(n-1))" in source["paper_return_definition"]
    assert "end of the UTC day" in source["paper_daily_close_semantics"]
    assert translation["source_weekday"] == "TUESDAY"
    assert translation["equivalent_utc_interval"] == "Tuesday 00:00 UTC -> Wednesday 00:00 UTC"
    assert translation["project_entry_boundary"] == signal["entry_boundary"]
    assert translation["project_exit_boundary"] == signal["exit_boundary"]
    assert translation["off_by_one_day_shift_allowed"] is False
    assert translation["alternative_monday_to_tuesday_translation_allowed"] is False
    assert translation["post_outcome_boundary_reinterpretation_allowed"] is False


def test_attestation_changes_no_scientific_or_execution_authority() -> None:
    attestation = _load(ATTESTATION_PATH)
    interpretation = attestation["scientific_interpretation"]
    assert interpretation["hypothesis_or_threshold_changed"] is False
    assert interpretation["screen_schedule_changed"] is False
    assert interpretation["cost_model_changed"] is False
    assert interpretation["survival_gates_changed"] is False
    assert interpretation["multiple_testing_family_changed"] is False
    assert interpretation["evidence_authority_increased"] is False
    assert interpretation["profitability_claim_allowed"] is False
    assert all(value is False for value in attestation["authority_locks"].values())
