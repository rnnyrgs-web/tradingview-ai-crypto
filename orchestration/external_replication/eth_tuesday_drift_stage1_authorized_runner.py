from __future__ import annotations

"""Authority-bearing Stage-1 entry for EXT-ETH-TUESDAY-DRIFT-001-v1.

This stdlib-only bootstrap closes pre-outcome trust-boundary defects:
1. behavior-bearing project modules are authenticated as inert bytes before any
   of them are imported or allowed to execute top-level code;
2. the exact v2 provenance document is pinned by an append-only authority
   anchor whose digest is compiled into this entrypoint; and
3. the actual base execution contract and risk-amendment artifacts are
   authenticated against their hard-pinned immutable digests before imports or
   dataset access, then rechecked after downstream validation.

No outcome is opened by importing this module or by validating the closure.
Independent exact-head scientific/review admission remains external authority.
"""

import hashlib
import importlib.util
import json
import sys
import types
from pathlib import Path
from typing import Mapping

ROOT = Path(__file__).resolve().parents[2]
AUTHORITY_ANCHOR_PATH = (
    ROOT
    / "orchestration"
    / "external_replication"
    / "ext_eth_tuesday_drift_001_stage1_authority_anchor_v1.json"
)
BASE_EXECUTION_CONTRACT_RELATIVE_PATH = (
    "orchestration/external_replication/ext_eth_tuesday_drift_001_stage1_execution.json"
)
RISK_AMENDMENT_RELATIVE_PATH = (
    "orchestration/external_replication/ext_eth_tuesday_drift_001_stage1_risk_amendment.json"
)

REPLICATION_ID = "EXT-ETH-TUESDAY-DRIFT-001-v1"
EXPECTED_AUTHORITY_ANCHOR_SHA256 = "51dc12aa867d54c357c82df970b3d48aa8d04e90f6f661d75dab54ad5d8137a8"
EXPECTED_PARENT_PROVENANCE_V2_SHA256 = "e452f5b55971854e7df40eee5c03b5a68c6c250fefd5ef9536733790a317a66d"
EXPECTED_PARENT_ARTIFACT_SHA256 = "6ddab16cbfbb846d0690dced9e2128244e2bc9ec6221243a02cb48fea4b5c98b"
EXPECTED_BASE_EXECUTION_CONTRACT_SHA256 = "823d7bbfbd411056358721dfb1e7f3764c7a445306f62aaa156945a6cd2ca46c"
EXPECTED_RISK_AMENDMENT_SHA256 = "8e13286cd6c586c98f6ade79409a243efde266b55e7f4ee57492affd97c4c2c0"

BASE_MODULE_NAME = "orchestration.external_replication.eth_tuesday_drift_runner"
LOADER_MODULE_NAME = "orchestration.external_replication.eth_tuesday_protected_safe_loader"
RISK_MODULE_NAME = "orchestration.external_replication.eth_tuesday_drift_stage1_guarded_runner"


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


def _load_exact_artifact(
    path: Path,
    *,
    expected_sha256: str,
    label: str,
) -> dict:
    document = json.loads(path.read_text(encoding="utf-8"))
    supplied = document.pop("artifact_sha256", None)
    if not isinstance(supplied, str):
        raise RuntimeError(f"{label} artifact_sha256 missing")
    actual = hashlib.sha256(_canonical_json(document)).hexdigest()
    if actual != supplied:
        raise RuntimeError(f"{label} artifact_sha256 mismatch")
    if supplied != expected_sha256:
        raise RuntimeError(f"{label} immutable digest mismatch")
    document["artifact_sha256"] = supplied
    return document


def _verified_repo_file(root: Path, relative_path: str, *, label: str) -> Path:
    root_resolved = root.resolve()
    path = (root_resolved / relative_path).resolve()
    if not path.is_relative_to(root_resolved) or not path.is_file():
        raise RuntimeError(f"{label} path is not an in-repository file")
    return path


def _verified_bound_path(
    root: Path,
    binding: Mapping[str, object],
    *,
    label: str,
) -> Path:
    relative_path = binding.get("path")
    expected_blob = binding.get("git_blob_sha1")
    if not isinstance(relative_path, str) or not relative_path:
        raise RuntimeError(f"{label} path missing")
    if not isinstance(expected_blob, str) or len(expected_blob) != 40:
        raise RuntimeError(f"{label} Git blob identity missing")

    path = _verified_repo_file(root, relative_path, label=label)
    actual_blob = _git_blob_sha1(path.read_bytes())
    if actual_blob != expected_blob:
        raise RuntimeError(f"{label} Git blob identity mismatch")
    return path


def verify_execution_closure(
    *,
    root: Path = ROOT,
    anchor_path: Path | None = None,
) -> tuple[dict, dict, dict[str, Path]]:
    """Authenticate frozen artifacts and behavior code as inert bytes before imports."""
    root = root.resolve()
    if anchor_path is None:
        anchor_path = (
            root
            / "orchestration"
            / "external_replication"
            / "ext_eth_tuesday_drift_001_stage1_authority_anchor_v1.json"
        )

    anchor = _load_exact_artifact(
        anchor_path,
        expected_sha256=EXPECTED_AUTHORITY_ANCHOR_SHA256,
        label="Stage-1 authority anchor",
    )
    if anchor.get("replication_id") != REPLICATION_ID:
        raise RuntimeError("authority-anchor replication mismatch")
    if anchor.get("parent_artifact_sha256") != EXPECTED_PARENT_ARTIFACT_SHA256:
        raise RuntimeError("authority-anchor parent mismatch")
    if anchor.get("base_execution_contract_sha256") != EXPECTED_BASE_EXECUTION_CONTRACT_SHA256:
        raise RuntimeError("authority-anchor base-contract mismatch")
    if anchor.get("risk_amendment_sha256") != EXPECTED_RISK_AMENDMENT_SHA256:
        raise RuntimeError("authority-anchor risk-amendment mismatch")
    if anchor.get("formed_pre_outcome") is not True:
        raise RuntimeError("authority anchor must be frozen pre-outcome")
    if anchor.get("outcomes_read_to_form_anchor") is not False:
        raise RuntimeError("authority-anchor outcome chronology drift")

    parent = anchor.get("parent_execution_provenance_v2")
    if not isinstance(parent, Mapping):
        raise RuntimeError("authority-anchor v2 parent missing")
    if parent.get("artifact_sha256") != EXPECTED_PARENT_PROVENANCE_V2_SHA256:
        raise RuntimeError("authority-anchor v2 digest drift")
    parent_path_value = parent.get("path")
    if not isinstance(parent_path_value, str) or not parent_path_value:
        raise RuntimeError("authority-anchor v2 path missing")
    parent_path = _verified_repo_file(root, parent_path_value, label="authority-anchor v2")

    provenance_v2 = _load_exact_artifact(
        parent_path,
        expected_sha256=EXPECTED_PARENT_PROVENANCE_V2_SHA256,
        label="execution provenance v2",
    )
    if provenance_v2.get("replication_id") != REPLICATION_ID:
        raise RuntimeError("execution provenance v2 replication mismatch")
    if provenance_v2.get("parent_artifact_sha256") != EXPECTED_PARENT_ARTIFACT_SHA256:
        raise RuntimeError("execution provenance v2 parent mismatch")
    if provenance_v2.get("base_execution_contract_sha256") != EXPECTED_BASE_EXECUTION_CONTRACT_SHA256:
        raise RuntimeError("execution provenance v2 base-contract mismatch")
    if provenance_v2.get("risk_amendment_sha256") != EXPECTED_RISK_AMENDMENT_SHA256:
        raise RuntimeError("execution provenance v2 risk-amendment mismatch")

    # The authority anchor's digest strings are not sufficient by themselves.
    # Authenticate the actual frozen scientific artifacts as inert data before
    # any behavior-bearing project module is imported or any dataset is read.
    base_contract_path = _verified_repo_file(
        root,
        BASE_EXECUTION_CONTRACT_RELATIVE_PATH,
        label="base execution contract",
    )
    base_contract = _load_exact_artifact(
        base_contract_path,
        expected_sha256=EXPECTED_BASE_EXECUTION_CONTRACT_SHA256,
        label="base execution contract",
    )
    if base_contract.get("replication_id") != REPLICATION_ID:
        raise RuntimeError("base execution contract replication mismatch")
    if base_contract.get("parent_artifact_sha256") != EXPECTED_PARENT_ARTIFACT_SHA256:
        raise RuntimeError("base execution contract parent mismatch")

    risk_amendment_path = _verified_repo_file(
        root,
        RISK_AMENDMENT_RELATIVE_PATH,
        label="risk amendment",
    )
    risk_amendment = _load_exact_artifact(
        risk_amendment_path,
        expected_sha256=EXPECTED_RISK_AMENDMENT_SHA256,
        label="risk amendment",
    )
    if risk_amendment.get("replication_id") != REPLICATION_ID:
        raise RuntimeError("risk amendment replication mismatch")
    if risk_amendment.get("parent_artifact_sha256") != EXPECTED_PARENT_ARTIFACT_SHA256:
        raise RuntimeError("risk amendment parent mismatch")
    if risk_amendment.get("base_execution_contract_sha256") != EXPECTED_BASE_EXECUTION_CONTRACT_SHA256:
        raise RuntimeError("risk amendment execution-contract mismatch")

    anchor_bindings = anchor.get("behavior_bindings")
    if not isinstance(anchor_bindings, Mapping):
        raise RuntimeError("authority-anchor behavior bindings missing")

    required = {
        "base_stage1_runner": "base Stage-1 evaluator",
        "protected_safe_loader": "protected-safe loader",
        "risk_guarded_runner": "risk guarded runner",
        "legacy_v2_final_runner": "legacy v2 final runner",
    }
    paths: dict[str, Path] = {}
    for key, label in required.items():
        binding = anchor_bindings.get(key)
        if not isinstance(binding, Mapping):
            raise RuntimeError(f"{label} authority-anchor binding missing")
        paths[key] = _verified_bound_path(root, binding, label=label)

    v2_keys = {
        "base_stage1_runner": "base_stage1_runner",
        "protected_safe_loader": "protected_safe_loader",
        "risk_guarded_runner": "risk_guarded_runner",
        "legacy_v2_final_runner": "final_stage1_runner",
    }
    for anchor_key, v2_key in v2_keys.items():
        anchor_binding = anchor_bindings[anchor_key]
        v2_binding = provenance_v2.get(v2_key)
        if not isinstance(v2_binding, Mapping):
            raise RuntimeError(f"execution provenance v2 {v2_key} binding missing")
        if (
            anchor_binding.get("path") != v2_binding.get("path")
            or anchor_binding.get("git_blob_sha1") != v2_binding.get("git_blob_sha1")
        ):
            raise RuntimeError(f"authority-anchor/{v2_key} identity disagreement")

    if anchor_bindings["legacy_v2_final_runner"].get("direct_stage1_entry_allowed") is not False:
        raise RuntimeError("legacy v2 final runner must remain non-authoritative")

    locks = anchor.get("authority_locks", {})
    if any(
        locks.get(key) is not False
        for key in (
            "stage1_started",
            "stage1_pnl_opened",
            "baseline_pnl_opened",
            "protected_oos_opened",
            "genuine_forward_opened",
            "profitability_claim_allowed",
            "promotion_authority",
            "broker_connected",
            "trade_authority",
        )
    ):
        raise RuntimeError("authority-anchor lock drift")

    return anchor, provenance_v2, paths


def _namespace_module(name: str, path: Path) -> types.ModuleType:
    module = types.ModuleType(name)
    module.__package__ = name
    module.__path__ = [str(path)]  # type: ignore[attr-defined]
    return module


def _load_exact_module(
    *,
    fullname: str,
    path: Path,
    package: types.ModuleType,
    attribute: str,
) -> types.ModuleType:
    spec = importlib.util.spec_from_file_location(fullname, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load verified module {fullname}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[fullname] = module
    setattr(package, attribute, module)
    spec.loader.exec_module(module)
    if Path(getattr(module, "__file__", "")).resolve() != path.resolve():
        raise RuntimeError(f"verified module {fullname} resolved to unexpected path")
    return module


def _restore_modules(previous: Mapping[str, object]) -> None:
    for name, prior in previous.items():
        if prior is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = prior  # type: ignore[assignment]


def _load_verified_behavior_modules(
    paths: Mapping[str, Path],
) -> tuple[types.ModuleType, types.ModuleType, types.ModuleType, dict[str, object]]:
    """Load only files already authenticated by ``verify_execution_closure``."""
    managed_names = (
        "orchestration",
        "orchestration.external_replication",
        BASE_MODULE_NAME,
        LOADER_MODULE_NAME,
        RISK_MODULE_NAME,
    )
    previous = {name: sys.modules.get(name) for name in managed_names}

    orchestration_pkg = _namespace_module("orchestration", ROOT / "orchestration")
    external_pkg = _namespace_module(
        "orchestration.external_replication",
        ROOT / "orchestration" / "external_replication",
    )
    setattr(orchestration_pkg, "external_replication", external_pkg)
    sys.modules["orchestration"] = orchestration_pkg
    sys.modules["orchestration.external_replication"] = external_pkg

    try:
        base = _load_exact_module(
            fullname=BASE_MODULE_NAME,
            path=paths["base_stage1_runner"],
            package=external_pkg,
            attribute="eth_tuesday_drift_runner",
        )
        loader = _load_exact_module(
            fullname=LOADER_MODULE_NAME,
            path=paths["protected_safe_loader"],
            package=external_pkg,
            attribute="eth_tuesday_protected_safe_loader",
        )
        risk = _load_exact_module(
            fullname=RISK_MODULE_NAME,
            path=paths["risk_guarded_runner"],
            package=external_pkg,
            attribute="eth_tuesday_drift_stage1_guarded_runner",
        )
    except Exception:
        _restore_modules(previous)
        raise
    return base, loader, risk, previous


def run_canonical_stage1_frozen() -> dict:
    """Run the frozen cheap screen only after an external admission gate permits it."""
    _, _, paths = verify_execution_closure()
    base, loader, risk_guard, previous = _load_verified_behavior_modules(paths)
    try:
        _, execution_contract = base.load_and_validate_contracts()
        if execution_contract.get("artifact_sha256") != EXPECTED_BASE_EXECUTION_CONTRACT_SHA256:
            raise RuntimeError("base execution contract immutable digest changed after closure verification")
        risk_amendment = risk_guard.load_and_validate_risk_amendment()
        if risk_amendment.get("artifact_sha256") != EXPECTED_RISK_AMENDMENT_SHA256:
            raise RuntimeError("risk amendment immutable digest changed after closure verification")
        rows = loader.load_frozen_eth_development_rows()
        result = risk_guard.evaluate_stage1_guarded(rows)
    finally:
        _restore_modules(previous)

    result["evidence_authority"] = (
        "FROZEN_DATASET_PREIMPORT_CODE_AND_CONTRACT_AUTHENTICATED_REVIEW_AUTHORITY_EXTERNAL_RISK_OVERLAY"
    )
    result["authority"]["stage2_baseline_execution_allowed"] = False
    result["authority"]["profitability_claim_allowed"] = False
    result["authority"]["deep_promotion_allowed"] = False
    result["authority"]["protected_oos_opened"] = False
    result["authority"]["trade_authority"] = False
    return result
