import hashlib
import json
import shutil
from pathlib import Path

import pytest

from falsification_evaluator_identity import (
    FalsificationIdentityError,
    verify_falsification_identity,
)


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "orchestration" / "falsification_evaluator_identities.json"


def _copy_identity_tree(tmp_path: Path, candidate_id: str) -> Path:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    record = manifest["records"][candidate_id]
    paths = {
        "orchestration/falsification_evaluator_identities.json",
        record["contract_path"],
        *record["source_paths"],
    }
    for relative in paths:
        source = ROOT / relative
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    return tmp_path


@pytest.mark.parametrize(
    "candidate_id",
    ["DATA-BASIS-001", "DATA-FUNDING-001", "DATA-BREADTH-001"],
)
def test_declared_falsification_identity_matches_exact_contract_and_code(candidate_id):
    identity = verify_falsification_identity(candidate_id)

    assert identity["candidate_id"] == candidate_id
    assert len(identity["contract_sha256"]) == 64
    assert len(identity["source_bundle_sha256"]) == 64
    assert len(identity["falsification_fingerprint_sha256"]) == 64
    assert identity["verified"] is True


def test_evaluator_edit_cannot_reuse_frozen_identity(tmp_path):
    root = _copy_identity_tree(tmp_path, "DATA-BASIS-001")
    evaluator = root / "basis_falsification_research.py"
    evaluator.write_bytes(evaluator.read_bytes() + b"\n# outcome-aware rescue\n")

    with pytest.raises(FalsificationIdentityError, match="source digest mismatch"):
        verify_falsification_identity("DATA-BASIS-001", root=root)


def test_contract_and_evaluator_coedit_cannot_reuse_frozen_identity(tmp_path):
    root = _copy_identity_tree(tmp_path, "DATA-FUNDING-001")
    evaluator = root / "funding_falsification_research.py"
    contract = root / "orchestration/data_funding_001_candidate.json"
    evaluator.write_bytes(evaluator.read_bytes() + b"\n# relaxed after outcome\n")
    payload = json.loads(contract.read_text(encoding="utf-8"))
    payload["evaluation_contract"]["minimum_oos_samples_per_primary_horizon"] = 2
    contract.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(FalsificationIdentityError):
        verify_falsification_identity("DATA-FUNDING-001", root=root)


def test_explicit_refreeze_after_coedit_mints_a_distinct_fingerprint(tmp_path):
    candidate_id = "DATA-FUNDING-001"
    original = verify_falsification_identity(candidate_id)
    root = _copy_identity_tree(tmp_path, candidate_id)
    evaluator = root / "funding_falsification_research.py"
    contract = root / "orchestration/data_funding_001_candidate.json"
    evaluator.write_bytes(evaluator.read_bytes() + b"\n# materially changed evaluator\n")
    payload = json.loads(contract.read_text(encoding="utf-8"))
    payload["evaluation_contract"]["minimum_oos_samples_per_primary_horizon"] = 12
    contract.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")

    manifest_path = root / "orchestration/falsification_evaluator_identities.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    record = manifest["records"][candidate_id]
    record["contract_sha256"] = hashlib.sha256(contract.read_bytes()).hexdigest()
    bundle = hashlib.sha256()
    bundle.update(b"falsification-evaluator-source-bundle-v1\0")
    for relative in record["source_paths"]:
        source = (root / relative).read_bytes()
        record["source_sha256"][relative] = hashlib.sha256(source).hexdigest()
        bundle.update(relative.encode("utf-8"))
        bundle.update(b"\0")
        bundle.update(source)
        bundle.update(b"\0")
    record["source_bundle_sha256"] = bundle.hexdigest()
    projection = {
        "schema_version": 1,
        "candidate_id": candidate_id,
        "contract_path": record["contract_path"],
        "contract_sha256": record["contract_sha256"],
        "source_paths": record["source_paths"],
        "source_sha256": record["source_sha256"],
        "source_bundle_sha256": record["source_bundle_sha256"],
    }
    record["falsification_fingerprint_sha256"] = hashlib.sha256(
        json.dumps(projection, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    refrozen = verify_falsification_identity(candidate_id, root=root)
    assert refrozen["verified"] is True
    assert (
        refrozen["falsification_fingerprint_sha256"]
        != original["falsification_fingerprint_sha256"]
    )


def test_unknown_candidate_fails_closed():
    with pytest.raises(FalsificationIdentityError, match="unknown candidate"):
        verify_falsification_identity("RENAMED-RESCUE-001")
