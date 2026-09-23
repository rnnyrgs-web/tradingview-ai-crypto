from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
LOCK_RELATIVE_PATH = Path(
    "orchestration/cohorts/strategy_factory_cohort_001_admission_provenance_lock.json"
)
REQUIRED_SOURCE_PATHS = {
    "orchestration/cohorts/strategy_factory_cohort_001_seed.json",
    "orchestration/cohorts/strategy_factory_cohort_001_readiness.json",
    "orchestration/cohorts/strategy_factory_cohort_001_ownership_correction.json",
    "orchestration/cohorts/strategy_factory_cohort_001_multiplicity_authority.json",
    "orchestration/cohorts/strategy_factory_cohort_001_canonical_admission.json",
    "orchestration/strategy_factory_cohort_001_admission.py",
    "orchestration/strategy_factory_cohort_001_provenance.py",
    "orchestration/strategy_predeclaration.py",
    "orchestration/scientific_design_identity.py",
    "orchestration/strategy_behavior_schema.py",
    "orchestration/strategy_behavior_value_contract.py",
    "strategy_dataset_preflight.py",
}


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            raise RuntimeError(f"duplicate JSON key: {key}")
        out[key] = value
    return out


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_strict_object,
            parse_constant=lambda value: (_ for _ in ()).throw(
                RuntimeError(f"non-standard JSON constant: {value}")
            ),
        )
    except OSError as exc:
        raise RuntimeError(f"unable to read {path}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"{path} must contain one JSON object")
    return payload


def _canonical_sha256_without(payload: dict[str, Any], digest_field: str) -> str:
    body = dict(payload)
    digest = body.pop(digest_field, None)
    if not isinstance(digest, str) or len(digest) != 64:
        raise RuntimeError(f"missing or invalid {digest_field}")
    canonical = json.dumps(
        body, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def git_blob_sha1(path: Path) -> str:
    data = path.read_bytes()
    header = f"blob {len(data)}\0".encode("ascii")
    return hashlib.sha1(header + data).hexdigest()  # noqa: S324 - Git object identity


def verify_admission_provenance_lock(
    repo_root: Path | None = None, lock_path: Path | None = None
) -> dict[str, Any]:
    root = (repo_root or REPO_ROOT).resolve()
    lock = (lock_path or (root / LOCK_RELATIVE_PATH)).resolve()
    payload = _load_json(lock)

    if payload.get("schema_version") != 1:
        raise RuntimeError("unsupported admission provenance lock schema")
    if payload.get("artifact_type") != "strategy_factory_cohort_001_admission_provenance_lock":
        raise RuntimeError("wrong admission provenance artifact type")
    if payload.get("contract_id") != "STRATEGY-FACTORY-COHORT-001-ADMISSION-PROVENANCE-LOCK-v1":
        raise RuntimeError("wrong admission provenance contract id")
    if _canonical_sha256_without(payload, "contract_sha256") != payload["contract_sha256"]:
        raise RuntimeError("admission provenance contract digest mismatch")

    source_blobs = payload.get("bound_source_git_blobs")
    if not isinstance(source_blobs, dict) or set(source_blobs) != REQUIRED_SOURCE_PATHS:
        raise RuntimeError("admission provenance source set mismatch")
    for relative_path, expected_blob in source_blobs.items():
        if not isinstance(expected_blob, str) or len(expected_blob) != 40:
            raise RuntimeError(f"invalid Git blob identity for {relative_path}")
        path = (root / relative_path).resolve()
        try:
            path.relative_to(root)
        except ValueError as exc:
            raise RuntimeError("admission provenance path escaped repository root") from exc
        if git_blob_sha1(path) != expected_blob:
            raise RuntimeError(f"admission provenance source drift: {relative_path}")

    admission = _load_json(
        root / "orchestration/cohorts/strategy_factory_cohort_001_canonical_admission.json"
    )
    if admission.get("receipt_sha256") != payload.get("bound_admission_receipt_sha256"):
        raise RuntimeError("canonical admission receipt identity drift")
    if admission.get("outcomes_read") is not False:
        raise RuntimeError("canonical admission must remain outcome-blind")
    if admission.get("protected_oos_opened") is not False or admission.get("genuine_forward_opened") is not False:
        raise RuntimeError("canonical admission opened protected evidence")
    if admission.get("trade_authority") is not False or admission.get("broker_connected") is not False:
        raise RuntimeError("canonical admission must not grant trading authority")

    multiplicity = _load_json(
        root / "orchestration/cohorts/strategy_factory_cohort_001_multiplicity_authority.json"
    )
    if multiplicity.get("contract_sha256") != payload.get("bound_multiplicity_contract_sha256"):
        raise RuntimeError("multiplicity authority identity drift")

    authority = payload.get("authority")
    required_false = (
        "outcomes_read",
        "protected_oos_opened",
        "genuine_forward_opened",
        "promotion_authority",
        "broker_connected",
        "trade_authority",
    )
    if not isinstance(authority, dict):
        raise RuntimeError("missing admission provenance authority block")
    if any(authority.get(key) is not False for key in required_false):
        raise RuntimeError("admission provenance authority lock weakened")
    if authority.get("integration_authority") != "NONE":
        raise RuntimeError("admission provenance lock cannot grant integration authority")
    if authority.get("receipt_is_not_claimed_immutable_against_repository_admin") is not True:
        raise RuntimeError("admission provenance trust boundary must remain explicit")
    if authority.get("any_source_or_receipt_change_requires_new_lock_new_head_ci_and_new_independent_review") is not True:
        raise RuntimeError("source drift must require a new reviewed head")

    return {
        "status": "VERIFIED_OUTCOME_BLIND_ADMISSION_PROVENANCE",
        "contract_sha256": payload["contract_sha256"],
        "bound_admission_receipt_sha256": payload["bound_admission_receipt_sha256"],
        "bound_multiplicity_contract_sha256": payload["bound_multiplicity_contract_sha256"],
        "source_count": len(source_blobs),
        "outcomes_read": False,
        "protected_oos_opened": False,
        "genuine_forward_opened": False,
        "integration_authority": "NONE",
        "broker_connected": False,
        "trade_authority": False,
    }
