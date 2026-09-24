from __future__ import annotations

"""Only authority-bearing Stage-1 entry for EXT-ETH-TUESDAY-DRIFT-001-v1.

The original predeclaration, base execution contract, append-only risk amendment,
and v1 execution-provenance binding remain immutable. This v2 wrapper closes the
remaining transitive code-identity gap by authenticating the exact base evaluator
as well as the protected-safe loader, risk evaluator, and this final wrapper.

No protected OHLCV, baseline, Stage-2, promotion, broker, or trading authority is
opened here. Independent exact-head scientific review remains external authority.
"""

import hashlib
import json
from pathlib import Path
from typing import Mapping

from orchestration.external_replication import eth_tuesday_drift_runner as base
from orchestration.external_replication import eth_tuesday_drift_stage1_guarded_runner as risk_guard
from orchestration.external_replication import eth_tuesday_protected_safe_loader as protected_loader

ROOT = Path(__file__).resolve().parents[2]
PROVENANCE_BINDING_PATH = (
    ROOT
    / "orchestration"
    / "external_replication"
    / "ext_eth_tuesday_drift_001_stage1_execution_provenance_v2.json"
)

REPLICATION_ID = base.REPLICATION_ID
PARENT_ARTIFACT_SHA256 = base.PARENT_ARTIFACT_SHA256
BASE_EXECUTION_CONTRACT_SHA256 = "823d7bbfbd411056358721dfb1e7f3764c7a445306f62aaa156945a6cd2ca46c"
RISK_AMENDMENT_SHA256 = "8e13286cd6c586c98f6ade79409a243efde266b55e7f4ee57492affd97c4c2c0"
PARENT_EXECUTION_PROVENANCE_SHA256 = "4499df212a3fef33ef3382b42f8cac552f95595c79f92f9cfbd72ccb3d7c4bc9"


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


def _verified_bound_path(binding: Mapping[str, object], *, label: str) -> Path:
    relative_path = binding.get("path")
    expected_blob = binding.get("git_blob_sha1")
    if not isinstance(relative_path, str) or not relative_path:
        raise RuntimeError(f"{label} path missing")
    if not isinstance(expected_blob, str) or len(expected_blob) != 40:
        raise RuntimeError(f"{label} Git blob identity missing")
    path = (ROOT / relative_path).resolve()
    if not path.is_relative_to(ROOT.resolve()) or not path.is_file():
        raise RuntimeError(f"{label} path is not an in-repository file")
    actual_blob = _git_blob_sha1(path.read_bytes())
    if actual_blob != expected_blob:
        raise RuntimeError(f"{label} Git blob identity mismatch")
    return path


def load_and_validate_execution_provenance(
    path: Path = PROVENANCE_BINDING_PATH,
) -> dict:
    binding = json.loads(path.read_text(encoding="utf-8"))
    supplied = binding.pop("artifact_sha256", None)
    if not isinstance(supplied, str):
        raise RuntimeError("execution provenance artifact_sha256 missing")
    actual = hashlib.sha256(_canonical_json(binding)).hexdigest()
    if actual != supplied:
        raise RuntimeError("execution provenance artifact_sha256 mismatch")
    binding["artifact_sha256"] = supplied

    if binding.get("replication_id") != REPLICATION_ID:
        raise RuntimeError("execution provenance replication mismatch")
    if binding.get("parent_artifact_sha256") != PARENT_ARTIFACT_SHA256:
        raise RuntimeError("execution provenance parent mismatch")
    if binding.get("base_execution_contract_sha256") != BASE_EXECUTION_CONTRACT_SHA256:
        raise RuntimeError("execution provenance base-contract mismatch")
    if binding.get("risk_amendment_sha256") != RISK_AMENDMENT_SHA256:
        raise RuntimeError("execution provenance risk-amendment mismatch")
    if binding.get("parent_execution_provenance_sha256") != PARENT_EXECUTION_PROVENANCE_SHA256:
        raise RuntimeError("execution provenance v1-parent mismatch")
    if binding.get("formed_pre_outcome") is not True:
        raise RuntimeError("execution provenance must be frozen pre-outcome")
    if binding.get("outcomes_read_to_form_binding") is not False:
        raise RuntimeError("execution provenance outcome chronology drift")

    base_runner_path = _verified_bound_path(
        binding.get("base_stage1_runner", {}),
        label="base Stage-1 evaluator",
    )
    loader_path = _verified_bound_path(
        binding.get("protected_safe_loader", {}),
        label="protected-safe loader",
    )
    risk_runner_path = _verified_bound_path(
        binding.get("risk_guarded_runner", {}),
        label="risk guarded runner",
    )
    final_runner_path = _verified_bound_path(
        binding.get("final_stage1_runner", {}),
        label="final Stage-1 runner",
    )

    if base_runner_path != Path(base.__file__).resolve():
        raise RuntimeError("imported base evaluator path differs from frozen binding")
    if loader_path != Path(protected_loader.__file__).resolve():
        raise RuntimeError("imported protected-safe loader path differs from frozen binding")
    if risk_runner_path != Path(risk_guard.__file__).resolve():
        raise RuntimeError("imported risk runner path differs from frozen binding")
    if final_runner_path != Path(__file__).resolve():
        raise RuntimeError("executing final runner path differs from frozen binding")

    locks = binding.get("authority_locks", {})
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
        raise RuntimeError("execution provenance authority lock drift")
    return binding


def run_canonical_stage1_frozen() -> dict:
    """Reject direct legacy entry; only the admission-gated runner may execute."""
    raise RuntimeError("legacy Stage-1 runner is non-authoritative")
