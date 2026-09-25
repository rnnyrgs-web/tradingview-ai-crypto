from __future__ import annotations

import hashlib
import fnmatch
import json
import shutil
from pathlib import Path

import pytest

from orchestration.strategy_factory_cohort_001_provenance import (
    LOCK_RELATIVE_PATH,
    REQUIRED_SOURCE_PATHS,
    verify_admission_provenance_lock,
)


ROOT = Path(__file__).resolve().parents[1]

# Explicit scientific dependencies: do not derive coverage from the verifier's
# own registry, because an omitted dependency must itself fail this regression.
SCIENTIFIC_SOURCE_PATHS = {
    "orchestration/scientific_design_identity.py",
    "orchestration/strategy_predeclaration.py",
    "orchestration/strategy_behavior_revision.py",
    "orchestration/strategy_behavior_schema.py",
    "orchestration/strategy_behavior_value_contract.py",
    "orchestration/strategy_factory_cohort_001_admission.py",
    "orchestration/strategy_factory_cohort_001_provenance.py",
    "strategy_dataset_preflight.py",
}


def test_scientific_identity_sources_are_bound_and_trigger_focused_ci() -> None:
    assert SCIENTIFIC_SOURCE_PATHS <= REQUIRED_SOURCE_PATHS
    workflow = (ROOT / ".github/workflows/strategy_factory_cohort_001_admission.yml").read_text()
    path_section = workflow.split("    paths:\n", 1)[1].split("  workflow_dispatch:", 1)[0]
    patterns = [line.strip()[2:].strip('"') for line in path_section.splitlines() if line.strip().startswith("- ")]
    for source in SCIENTIFIC_SOURCE_PATHS:
        assert any(fnmatch.fnmatchcase(source, pattern) for pattern in patterns), source
    revision_test = "tests/test_strategy_behavior_contract_revision.py"
    assert any(fnmatch.fnmatchcase(revision_test, pattern) for pattern in patterns)
    assert revision_test in workflow.split("python -m pytest -q", 1)[1]


def test_identity_revision_semantic_drift_fails_closed(tmp_path: Path) -> None:
    _copy_lock_fixture(tmp_path)
    relative = "orchestration/strategy_behavior_revision.py"
    source = (ROOT / relative).read_text()
    assert "DEFAULT_EXECUTABLE_CONTRACT_REVISION = 1" in source
    (tmp_path / relative).write_text(source.replace(
        "DEFAULT_EXECUTABLE_CONTRACT_REVISION = 1",
        "DEFAULT_EXECUTABLE_CONTRACT_REVISION = 2",
    ))
    with pytest.raises(RuntimeError, match="source drift.*strategy_behavior_revision"):
        verify_admission_provenance_lock(repo_root=tmp_path)


def test_revision_binding_cannot_be_dropped_with_valid_self_digest(tmp_path: Path) -> None:
    lock = _copy_lock_fixture(tmp_path)
    payload = json.loads(lock.read_text())
    payload["bound_source_git_blobs"].pop("orchestration/strategy_behavior_revision.py", None)
    payload["contract_sha256"] = _recompute_contract_digest(payload)
    lock.write_text(json.dumps(payload))
    with pytest.raises(RuntimeError, match="source set mismatch"):
        verify_admission_provenance_lock(repo_root=tmp_path)


def _copy_lock_fixture(tmp_path: Path) -> Path:
    for relative in REQUIRED_SOURCE_PATHS | {LOCK_RELATIVE_PATH.as_posix()}:
        source = ROOT / relative
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    return tmp_path / LOCK_RELATIVE_PATH


def _recompute_contract_digest(payload: dict[str, object]) -> str:
    body = dict(payload)
    body.pop("contract_sha256", None)
    canonical = json.dumps(
        body, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def test_admission_provenance_lock_verifies_exact_current_inputs() -> None:
    result = verify_admission_provenance_lock()
    assert result["status"] == "VERIFIED_OUTCOME_BLIND_ADMISSION_PROVENANCE"
    assert result["source_count"] == len(REQUIRED_SOURCE_PATHS)
    assert result["outcomes_read"] is False
    assert result["protected_oos_opened"] is False
    assert result["genuine_forward_opened"] is False
    assert result["integration_authority"] == "NONE"
    assert result["broker_connected"] is False
    assert result["trade_authority"] is False


def test_semantically_identical_source_byte_drift_fails_closed(tmp_path: Path) -> None:
    _copy_lock_fixture(tmp_path)
    seed = tmp_path / "orchestration/cohorts/strategy_factory_cohort_001_seed.json"
    seed.write_text(seed.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="source drift"):
        verify_admission_provenance_lock(repo_root=tmp_path)


def test_receipt_byte_drift_fails_closed(tmp_path: Path) -> None:
    _copy_lock_fixture(tmp_path)
    receipt = tmp_path / "orchestration/cohorts/strategy_factory_cohort_001_canonical_admission.json"
    receipt.write_text(receipt.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="source drift"):
        verify_admission_provenance_lock(repo_root=tmp_path)


def test_dropped_source_binding_fails_even_with_valid_new_self_digest(tmp_path: Path) -> None:
    lock = _copy_lock_fixture(tmp_path)
    payload = json.loads(lock.read_text(encoding="utf-8"))
    payload["bound_source_git_blobs"].pop(
        "orchestration/scientific_design_identity.py"
    )
    payload["contract_sha256"] = _recompute_contract_digest(payload)
    lock.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="source set mismatch"):
        verify_admission_provenance_lock(repo_root=tmp_path)


def test_authority_tamper_fails_even_with_valid_new_self_digest(tmp_path: Path) -> None:
    lock = _copy_lock_fixture(tmp_path)
    payload = json.loads(lock.read_text(encoding="utf-8"))
    payload["authority"]["integration_authority"] = "APPROVE"
    payload["contract_sha256"] = _recompute_contract_digest(payload)
    lock.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="cannot grant integration authority"):
        verify_admission_provenance_lock(repo_root=tmp_path)
