from __future__ import annotations

import json
from pathlib import Path

import pytest

import kraken_eth_session_source_chronology_gate as gate


ROOT = Path(__file__).resolve().parents[1]


def _copy_binding(tmp_path: Path) -> None:
    for relative in (gate.CONTRACT_PATH, gate.AMENDMENT_PATH):
        source = ROOT / relative
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.read_bytes())


def test_gate_binds_exact_parent_and_chronology_amendment() -> None:
    result = gate.validate_source_chronology_binding()
    assert result["status"] == "SOURCE_CHRONOLOGY_BOUND_PRE_PROVIDER_FETCH"
    assert result["contract_id"] == gate.CONTRACT_ID
    assert result["contract_artifact_sha256"] == gate.CONTRACT_ARTIFACT_SHA256
    assert result["amendment_id"] == gate.AMENDMENT_ID
    assert result["amendment_artifact_sha256"] == gate.AMENDMENT_ARTIFACT_SHA256
    assert result["retrospective_h1_evidence_classification"] == gate.H1_EVIDENCE_LABEL
    assert result["independent_replication_authority"] is False
    assert result["profitability_claim_authority"] is False
    assert result["promotion_authority"] is False
    assert result["broker_connected"] is False
    assert result["trade_authority"] is False


def test_gate_rejects_missing_chronology_amendment(tmp_path: Path) -> None:
    contract = ROOT / gate.CONTRACT_PATH
    target = tmp_path / gate.CONTRACT_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(contract.read_bytes())
    with pytest.raises(FileNotFoundError):
        gate.validate_source_chronology_binding(tmp_path)


def test_gate_rejects_positive_h1_promotion_authority(tmp_path: Path) -> None:
    _copy_binding(tmp_path)
    amendment_path = tmp_path / gate.AMENDMENT_PATH
    amendment = json.loads(amendment_path.read_text(encoding="utf-8"))
    amendment["evidence_reclassification"]["deep_candidate_promotion_allowed_from_h1_alone"] = True
    amendment_path.write_text(json.dumps(amendment), encoding="utf-8")
    with pytest.raises(ValueError, match="artifact identity mismatch|self-digest mismatch"):
        gate.validate_source_chronology_binding(tmp_path)


def test_gate_rejects_forward_boundary_drift_even_with_recomputed_self_digest(tmp_path: Path) -> None:
    _copy_binding(tmp_path)
    amendment_path = tmp_path / gate.AMENDMENT_PATH
    amendment = json.loads(amendment_path.read_text(encoding="utf-8"))
    amendment["genuine_forward_binding"]["start_utc"] = "2026-09-24T16:00:00Z"
    amendment["artifact_sha256"] = gate._artifact_digest(amendment)
    amendment_path.write_text(json.dumps(amendment), encoding="utf-8")
    with pytest.raises(ValueError, match="artifact identity mismatch"):
        gate.validate_source_chronology_binding(tmp_path)


def test_gate_rejects_contract_byte_drift_even_if_json_semantics_are_same(tmp_path: Path) -> None:
    _copy_binding(tmp_path)
    contract_path = tmp_path / gate.CONTRACT_PATH
    contract_path.write_bytes(contract_path.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="exact Git blob identity mismatch"):
        gate.validate_source_chronology_binding(tmp_path)
