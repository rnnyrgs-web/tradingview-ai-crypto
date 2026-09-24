"""Fail-closed identity binding for frozen falsification evaluators.

The manifest binds the exact predeclaration bytes and every behavior-driving
local source file used by each legacy falsifier.  Any contract or evaluator
change therefore produces a new exact scientific/executable fingerprint; it
cannot silently inherit a prior rejection or blocked result under the same
human-readable candidate id.

This is an exact-byte identity, not a claim that legacy evidence was produced
by today's source bytes.  Historical records remain historical unless they
already carry an independently durable execution receipt.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
MANIFEST_RELATIVE_PATH = Path("orchestration/falsification_evaluator_identities.json")
SCHEMA_VERSION = 1
_HEX = frozenset("0123456789abcdef")


class FalsificationIdentityError(RuntimeError):
    """Raised when frozen falsification identity cannot be authenticated."""


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _canonical_sha256(payload: dict) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return _sha256(encoded)


def _safe_file(root: Path, relative: str) -> Path:
    candidate = Path(relative)
    if candidate.is_absolute() or ".." in candidate.parts or not candidate.parts:
        raise FalsificationIdentityError(f"unsafe identity path: {relative!r}")
    path = root.joinpath(candidate)
    if path.is_symlink() or not path.is_file():
        raise FalsificationIdentityError(f"identity source missing or non-regular: {relative}")
    try:
        path.resolve(strict=True).relative_to(root.resolve(strict=True))
    except ValueError as exc:
        raise FalsificationIdentityError(f"identity source escapes repository: {relative}") from exc
    return path


def _require_sha256(value: object, field: str) -> str:
    text = str(value or "")
    if len(text) != 64 or any(char not in _HEX for char in text):
        raise FalsificationIdentityError(f"invalid {field}")
    return text


def _source_bundle_sha256(root: Path, source_paths: list[str]) -> tuple[str, dict[str, str]]:
    digest = hashlib.sha256()
    digest.update(b"falsification-evaluator-source-bundle-v1\0")
    source_digests: dict[str, str] = {}
    for relative in source_paths:
        payload = _safe_file(root, relative).read_bytes()
        source_digests[relative] = _sha256(payload)
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(payload)
        digest.update(b"\0")
    return digest.hexdigest(), source_digests


def _identity_projection(candidate_id: str, record: dict) -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "candidate_id": candidate_id,
        "contract_path": record["contract_path"],
        "contract_sha256": record["contract_sha256"],
        "source_paths": record["source_paths"],
        "source_sha256": record["source_sha256"],
        "source_bundle_sha256": record["source_bundle_sha256"],
    }


def verify_falsification_identity(candidate_id: str, *, root: Path | str = ROOT) -> dict:
    """Authenticate and return one frozen evaluator/contract identity.

    The returned fingerprint is safe to persist with any newly produced
    falsification evidence.  A mismatch raises instead of allowing evaluation
    under stale or caller-asserted identity.
    """

    repository_root = Path(root)
    manifest_path = _safe_file(repository_root, MANIFEST_RELATIVE_PATH.as_posix())
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise FalsificationIdentityError("identity manifest is not canonical JSON") from exc
    if not isinstance(manifest, dict) or manifest.get("schema_version") != SCHEMA_VERSION:
        raise FalsificationIdentityError("unsupported identity manifest schema")
    records = manifest.get("records")
    if not isinstance(records, dict) or candidate_id not in records:
        raise FalsificationIdentityError(f"unknown candidate: {candidate_id}")
    record = records[candidate_id]
    if not isinstance(record, dict):
        raise FalsificationIdentityError("candidate identity record must be an object")

    contract_path = record.get("contract_path")
    source_paths = record.get("source_paths")
    source_sha256 = record.get("source_sha256")
    if not isinstance(contract_path, str):
        raise FalsificationIdentityError("contract_path must be a string")
    if (
        not isinstance(source_paths, list)
        or not source_paths
        or source_paths != sorted(set(source_paths))
        or not all(isinstance(path, str) for path in source_paths)
    ):
        raise FalsificationIdentityError("source_paths must be unique and sorted")
    if not isinstance(source_sha256, dict) or set(source_sha256) != set(source_paths):
        raise FalsificationIdentityError("source digest keys do not match source paths")

    contract_bytes = _safe_file(repository_root, contract_path).read_bytes()
    actual_contract_sha = _sha256(contract_bytes)
    expected_contract_sha = _require_sha256(record.get("contract_sha256"), "contract_sha256")
    if actual_contract_sha != expected_contract_sha:
        raise FalsificationIdentityError("contract digest mismatch")
    try:
        contract = json.loads(contract_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise FalsificationIdentityError("contract is not valid UTF-8 JSON") from exc
    declared_candidate = contract.get("candidate_id", contract.get("experiment_id"))
    if declared_candidate != candidate_id:
        raise FalsificationIdentityError("contract candidate identity mismatch")

    actual_bundle_sha, actual_source_sha = _source_bundle_sha256(repository_root, source_paths)
    expected_source_sha = {
        path: _require_sha256(source_sha256[path], f"source_sha256[{path}]")
        for path in source_paths
    }
    if actual_source_sha != expected_source_sha:
        raise FalsificationIdentityError("source digest mismatch")
    expected_bundle_sha = _require_sha256(
        record.get("source_bundle_sha256"), "source_bundle_sha256"
    )
    if actual_bundle_sha != expected_bundle_sha:
        raise FalsificationIdentityError("source bundle digest mismatch")

    projection = _identity_projection(candidate_id, record)
    actual_fingerprint = _canonical_sha256(projection)
    expected_fingerprint = _require_sha256(
        record.get("falsification_fingerprint_sha256"),
        "falsification_fingerprint_sha256",
    )
    if actual_fingerprint != expected_fingerprint:
        raise FalsificationIdentityError("falsification fingerprint mismatch")
    return {
        **projection,
        "falsification_fingerprint_sha256": actual_fingerprint,
        "verified": True,
    }
