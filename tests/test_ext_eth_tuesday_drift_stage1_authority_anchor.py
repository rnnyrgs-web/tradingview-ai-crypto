from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pytest

from orchestration.external_replication import eth_tuesday_drift_stage1_authorized_runner as authorized
from orchestration.external_replication import eth_tuesday_drift_stage1_frozen_runner as legacy_frozen

ROOT = Path(__file__).resolve().parents[1]
ANCHOR_PATH = (
    ROOT
    / "orchestration"
    / "external_replication"
    / "ext_eth_tuesday_drift_001_stage1_authority_anchor_v2.json"
)
EXPECTED_ANCHOR_SHA256 = "8bada39aacc7f988d90b418a2a15337e97ed750b7674f2d68a7be96daa080d58"
EXPECTED_PARENT_ANCHOR_SHA256 = "51dc12aa867d54c357c82df970b3d48aa8d04e90f6f661d75dab54ad5d8137a8"
EXPECTED_V2_SHA256 = "e452f5b55971854e7df40eee5c03b5a68c6c250fefd5ef9536733790a317a66d"


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def _rehash_artifact(path: Path, mutate) -> None:
    document = json.loads(path.read_text(encoding="utf-8"))
    mutate(document)
    document.pop("artifact_sha256")
    document["artifact_sha256"] = hashlib.sha256(_canonical_json(document)).hexdigest()
    path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")


def _copy_closure(tmp_path: Path) -> Path:
    target_root = tmp_path / "repo"
    relative_paths = [
        "orchestration/external_replication/ext_eth_tuesday_drift_001_stage1_authority_anchor_v2.json",
        "orchestration/external_replication/ext_eth_tuesday_drift_001_stage1_authority_anchor_v1.json",
        "orchestration/external_replication/ext_eth_tuesday_drift_001_stage1_execution_provenance_v2.json",
        "orchestration/external_replication/ext_eth_tuesday_drift_001_stage1_execution.json",
        "orchestration/external_replication/ext_eth_tuesday_drift_001_stage1_risk_amendment.json",
        "orchestration/external_replication/eth_tuesday_drift_runner.py",
        "orchestration/external_replication/eth_tuesday_protected_safe_loader.py",
        "orchestration/external_replication/eth_tuesday_drift_stage1_guarded_runner.py",
        "orchestration/external_replication/eth_tuesday_drift_stage1_frozen_runner.py",
    ]
    for relative in relative_paths:
        source = ROOT / relative
        target = target_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    return target_root


def test_authority_anchor_is_independently_pinned_and_pre_outcome() -> None:
    document = json.loads(ANCHOR_PATH.read_text(encoding="utf-8"))
    supplied = document.pop("artifact_sha256")
    assert supplied == EXPECTED_ANCHOR_SHA256
    assert supplied == authorized.EXPECTED_AUTHORITY_ANCHOR_SHA256
    assert hashlib.sha256(_canonical_json(document)).hexdigest() == EXPECTED_ANCHOR_SHA256
    assert document["formed_pre_outcome"] is True
    assert document["outcomes_read_to_form_anchor"] is False
    assert (
        document["parent_authority_anchor_v1"]["artifact_sha256"]
        == EXPECTED_PARENT_ANCHOR_SHA256
        == authorized.EXPECTED_PARENT_AUTHORITY_ANCHOR_V1_SHA256
    )
    assert document["legacy_v2_final_runner_replacement"]["direct_stage1_entry_allowed"] is False
    assert document["admission_policy"]["stage1_execution_admitted"] is False
    assert document["admission_policy"]["integrated_admission_artifact_sha256"] is None
    assert document["admission_policy"]["read_only_review_receipt_is_execution_token"] is False
    assert all(value is False for value in document["authority_locks"].values())


def test_canonical_closure_validates_without_importing_behavior_for_scoring() -> None:
    anchor, v2, paths = authorized.verify_execution_closure()
    assert anchor["artifact_sha256"] == EXPECTED_ANCHOR_SHA256
    assert v2["artifact_sha256"] == EXPECTED_V2_SHA256
    assert set(paths) == {
        "base_stage1_runner",
        "protected_safe_loader",
        "risk_guarded_runner",
        "legacy_v2_final_runner",
    }


def test_stage1_execution_fails_closed_before_scientific_closure_without_integrated_admission(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden_closure() -> None:
        pytest.fail("scientific closure must not be reached before independent admission")

    monkeypatch.setattr(authorized, "verify_execution_closure", forbidden_closure)

    with pytest.raises(RuntimeError, match="independent review admission is not integrated"):
        authorized.run_canonical_stage1_frozen()


def test_legacy_frozen_runner_cannot_bypass_authorized_admission(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden_dataset_load() -> None:
        pytest.fail("legacy runner must not reach the frozen dataset")

    monkeypatch.setattr(
        legacy_frozen.protected_loader,
        "load_frozen_eth_development_rows",
        forbidden_dataset_load,
    )

    with pytest.raises(RuntimeError, match="legacy Stage-1 runner is non-authoritative"):
        legacy_frozen.run_canonical_stage1_frozen()


def test_tampered_behavior_is_rejected_before_import_time_sentinel_executes(tmp_path: Path) -> None:
    root = _copy_closure(tmp_path)
    base_path = root / "orchestration/external_replication/eth_tuesday_drift_runner.py"
    sentinel = tmp_path / "IMPORT_SENTINEL_EXECUTED"
    base_path.write_text(
        base_path.read_text(encoding="utf-8")
        + "\nfrom pathlib import Path as _SentinelPath\n"
        + f"_SentinelPath({str(sentinel)!r}).write_text('executed', encoding='utf-8')\n",
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="base Stage-1 evaluator Git blob identity mismatch"):
        authorized.verify_execution_closure(root=root)

    assert not sentinel.exists()


def test_self_rehashed_rewritten_v2_is_rejected_by_independent_anchor(tmp_path: Path) -> None:
    root = _copy_closure(tmp_path)
    v2_path = (
        root
        / "orchestration"
        / "external_replication"
        / "ext_eth_tuesday_drift_001_stage1_execution_provenance_v2.json"
    )
    _rehash_artifact(
        v2_path,
        lambda document: document.__setitem__("status", "ATTACKER_REHASHED_SELF_CONSISTENT_REWRITE"),
    )

    with pytest.raises(RuntimeError, match="execution provenance v2 immutable digest mismatch"):
        authorized.verify_execution_closure(root=root)


def test_self_rehashed_base_execution_contract_is_rejected_before_import(tmp_path: Path) -> None:
    root = _copy_closure(tmp_path)
    contract_path = (
        root
        / "orchestration"
        / "external_replication"
        / "ext_eth_tuesday_drift_001_stage1_execution.json"
    )

    def mutate(document: dict) -> None:
        document["result_authority"]["caller_or_synthetic_rows"] = "ATTACKER_REHASHED_BUT_STILL_FALSE_AUTHORITY"

    _rehash_artifact(contract_path, mutate)

    with pytest.raises(RuntimeError, match="base execution contract immutable digest mismatch"):
        authorized.verify_execution_closure(root=root)


def test_self_rehashed_risk_amendment_is_rejected_before_import(tmp_path: Path) -> None:
    root = _copy_closure(tmp_path)
    amendment_path = (
        root
        / "orchestration"
        / "external_replication"
        / "ext_eth_tuesday_drift_001_stage1_risk_amendment.json"
    )

    def mutate(document: dict) -> None:
        document["status"] = "ATTACKER_REHASHED_SELF_CONSISTENT_RISK_REWRITE"

    _rehash_artifact(amendment_path, mutate)

    with pytest.raises(RuntimeError, match="risk amendment immutable digest mismatch"):
        authorized.verify_execution_closure(root=root)


def test_self_rehashed_rewritten_anchor_cannot_replace_compiled_root(tmp_path: Path) -> None:
    root = _copy_closure(tmp_path)
    anchor_path = (
        root
        / "orchestration"
        / "external_replication"
        / "ext_eth_tuesday_drift_001_stage1_authority_anchor_v2.json"
    )
    _rehash_artifact(
        anchor_path,
        lambda document: document["admission_policy"].__setitem__(
            "stage1_execution_admitted", True
        ),
    )

    with pytest.raises(RuntimeError, match="Stage-1 authority anchor immutable digest mismatch"):
        authorized.verify_execution_closure(root=root, anchor_path=anchor_path)
