from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
PROVENANCE_V1 = (
    ROOT
    / "orchestration/external_replication/ext_eth_tuesday_drift_001_stage1_execution_provenance.json"
)
PROVENANCE_V2 = (
    ROOT
    / "orchestration/external_replication/ext_eth_tuesday_drift_001_stage1_execution_provenance_v2.json"
)
AUTHORITY_ANCHOR_V2 = (
    ROOT
    / "orchestration/external_replication/ext_eth_tuesday_drift_001_stage1_authority_anchor_v2.json"
)
AUTHORITY_ANCHOR_V3 = (
    ROOT
    / "orchestration/external_replication/ext_eth_tuesday_drift_001_stage1_authority_anchor_v3.json"
)
BASE_RUNNER = (
    ROOT
    / "orchestration/external_replication/eth_tuesday_drift_runner.py"
)
FINAL_RUNNER = (
    ROOT
    / "orchestration/external_replication/eth_tuesday_drift_stage1_frozen_runner.py"
)
EXPECTED_V1_PROVENANCE_SHA256 = "4499df212a3fef33ef3382b42f8cac552f95595c79f92f9cfbd72ccb3d7c4bc9"
EXPECTED_V2_PROVENANCE_SHA256 = "e452f5b55971854e7df40eee5c03b5a68c6c250fefd5ef9536733790a317a66d"
EXPECTED_BASE_RUNNER_BLOB = "2073a40c8ebf16dad1f2dacdc8783877aac7a7b5"
EXPECTED_NON_AUTHORITATIVE_BASE_RUNNER_BLOB = "8a3418ea41001fa7cf6b34c23ebd7c65033abbd5"
EXPECTED_RISK_AMENDMENT_SHA256 = "8e13286cd6c586c98f6ade79409a243efde266b55e7f4ee57492affd97c4c2c0"
EXPECTED_RISK_RUNNER_BLOB = "f39e0b03064036fd7cb66174d744ec789ecd6e28"
EXPECTED_FINAL_RUNNER_BLOB = "945c07146a8d553b8b37b763bf821f26d07a9450"
EXPECTED_NON_AUTHORITATIVE_FINAL_RUNNER_BLOB = "7e6ca072f93cd6037b0b0a72600d14f0c8e39def"


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def _git_blob_sha1(payload: bytes) -> str:
    header = f"blob {len(payload)}\0".encode("ascii")
    return hashlib.sha1(header + payload, usedforsecurity=False).hexdigest()


def _load_self_digest(path: Path) -> tuple[dict, str]:
    binding = json.loads(path.read_text(encoding="utf-8"))
    supplied = binding.pop("artifact_sha256")
    assert hashlib.sha256(_canonical_json(binding)).hexdigest() == supplied
    binding["artifact_sha256"] = supplied
    return binding, supplied


def test_v2_provenance_is_append_only_and_closes_transitive_base_evaluator_identity():
    """The old provenance remains immutable; v2 adds the omitted base evaluator identity."""
    _v1, v1_digest = _load_self_digest(PROVENANCE_V1)
    assert v1_digest == EXPECTED_V1_PROVENANCE_SHA256

    v2, v2_digest = _load_self_digest(PROVENANCE_V2)
    assert v2_digest == EXPECTED_V2_PROVENANCE_SHA256
    assert v2["parent_execution_provenance_sha256"] == EXPECTED_V1_PROVENANCE_SHA256
    assert v2["parent_execution_provenance"]["artifact_sha256"] == EXPECTED_V1_PROVENANCE_SHA256
    assert v2["scientific_reason"]["prior_v1_provenance_mutated"] is False
    assert v2["scientific_reason"]["hypothesis_or_outcome_rules_changed"] is False
    assert v2["formed_pre_outcome"] is True
    assert v2["outcomes_read_to_form_binding"] is False
    assert all(value is False for value in v2["authority_locks"].values())

    base_binding = v2["base_stage1_runner"]
    assert base_binding["git_blob_sha1"] == EXPECTED_BASE_RUNNER_BLOB
    anchor_v3, _ = _load_self_digest(AUTHORITY_ANCHOR_V3)
    base_replacement = anchor_v3["base_stage1_runner_replacement"]
    assert base_replacement["parent_git_blob_sha1"] == EXPECTED_BASE_RUNNER_BLOB
    assert base_replacement["git_blob_sha1"] == EXPECTED_NON_AUTHORITATIVE_BASE_RUNNER_BLOB
    assert base_replacement["direct_stage1_entry_allowed"] is False
    assert _git_blob_sha1(BASE_RUNNER.read_bytes()) == EXPECTED_NON_AUTHORITATIVE_BASE_RUNNER_BLOB

    assert v2["risk_amendment_sha256"] == EXPECTED_RISK_AMENDMENT_SHA256
    assert v2["risk_guarded_runner"]["git_blob_sha1"] == EXPECTED_RISK_RUNNER_BLOB

    final_binding = v2["final_stage1_runner"]
    assert final_binding["git_blob_sha1"] == EXPECTED_FINAL_RUNNER_BLOB
    anchor_v2, _ = _load_self_digest(AUTHORITY_ANCHOR_V2)
    replacement = anchor_v2["legacy_v2_final_runner_replacement"]
    assert replacement["parent_git_blob_sha1"] == EXPECTED_FINAL_RUNNER_BLOB
    assert replacement["git_blob_sha1"] == EXPECTED_NON_AUTHORITATIVE_FINAL_RUNNER_BLOB
    assert replacement["direct_stage1_entry_allowed"] is False
    final_source = FINAL_RUNNER.read_bytes()
    assert _git_blob_sha1(final_source) == EXPECTED_NON_AUTHORITATIVE_FINAL_RUNNER_BLOB
    final_text = final_source.decode("utf-8")
    assert 'binding.get("base_stage1_runner", {})' in final_text
    assert "imported base evaluator path differs from frozen binding" in final_text
    assert 'raise RuntimeError("legacy Stage-1 runner is non-authoritative")' in final_text


def test_final_runner_runtime_validates_all_transitive_behavior_bearing_file_identities():
    from orchestration.external_replication import eth_tuesday_drift_stage1_frozen_runner as final

    with pytest.raises(RuntimeError, match="base Stage-1 evaluator Git blob identity mismatch"):
        final.load_and_validate_execution_provenance()

    binding, digest = _load_self_digest(PROVENANCE_V2)
    assert digest == EXPECTED_V2_PROVENANCE_SHA256
    assert binding["artifact_sha256"] == EXPECTED_V2_PROVENANCE_SHA256
    assert binding["base_stage1_runner"]["git_blob_sha1"] == EXPECTED_BASE_RUNNER_BLOB
    assert binding["protected_safe_loader"]["git_blob_sha1"] == "791358a1a48993e3ffbbee42c8a561313d8f60ae"
    assert binding["risk_guarded_runner"]["git_blob_sha1"] == EXPECTED_RISK_RUNNER_BLOB
    assert binding["final_stage1_runner"]["git_blob_sha1"] == EXPECTED_FINAL_RUNNER_BLOB

    tampered = dict(binding["base_stage1_runner"])
    tampered["git_blob_sha1"] = "0" * 40
    with pytest.raises(RuntimeError, match="base Stage-1 evaluator Git blob identity mismatch"):
        final._verified_bound_path(tampered, label="base Stage-1 evaluator")


def test_bound_loader_materializes_only_frozen_development_eth_rows():
    """Exercise the actual bound loader without computing any strategy outcome."""
    from orchestration.external_replication import eth_tuesday_protected_safe_loader as loader

    rows = loader.load_frozen_eth_development_rows()
    assert rows
    protected_ms = int(loader._parse_hour(loader.PROTECTED_START_UTC).timestamp() * 1000)
    cutoff_ms = int(loader._parse_hour(loader.DEVELOPMENT_END_UTC).timestamp() * 1000)
    assert int(rows[-1]["ts"]) == cutoff_ms
    assert all(int(row["ts"]) < protected_ms for row in rows)
    assert all(float(row["open"]) > 0 for row in rows)
