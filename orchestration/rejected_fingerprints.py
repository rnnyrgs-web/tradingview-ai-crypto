from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from orchestration.scientific_design_identity import (
    SCIENTIFIC_IDENTITY_VERSION,
    STRATEGY_BEHAVIOR_IDENTITY_VERSION,
    scientific_design_sha256,
    strategy_behavior_sha256,
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PATH = ROOT / "orchestration" / "rejected_fingerprints.json"
DEFAULT_SEMANTIC_PATH = ROOT / "orchestration" / "rejected_semantic_designs.json"

REQUIRED_FIELDS = (
    "fingerprint_id",
    "fingerprint_version",
    "hypothesis",
    "economic_mechanism",
    "horizons_evaluated",
    "sample_sizes",
    "rejection_evidence",
    "rejection_reason",
    "rejection_date",
    "do_not_resubmit_same_fingerprint",
    "reconsideration_conditions",
)

REJECTED_SEMANTIC_SCHEMA_VERSION = 2
SEMANTIC_BACKFILL_AVAILABLE = "BACKFILLED_STRUCTURED_CONTRACT"
SEMANTIC_BACKFILL_UNAVAILABLE = "SEMANTIC_BACKFILL_UNAVAILABLE"
SEMANTIC_STATUSES = {SEMANTIC_BACKFILL_AVAILABLE, SEMANTIC_BACKFILL_UNAVAILABLE}


def _git_blob_sha1(raw: bytes) -> str:
    header = f"blob {len(raw)}\0".encode("ascii")
    return hashlib.sha1(header + raw).hexdigest()  # nosec B324 - Git object identity, not security


def _contract_sha256(payload: dict[str, Any]) -> str:
    detached = dict(payload)
    detached.pop("contract_sha256", None)
    detached.pop("contract_fingerprint_definition", None)
    encoded = json.dumps(
        detached,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _load_and_verify_source_contract(record: dict[str, Any], fingerprint_id: str) -> dict[str, Any]:
    """Authenticate one semantic backfill against its packaged frozen contract.

    Stored semantic hashes are not a trust root. For reconstructible rejections,
    the sidecar must point to one repository-local frozen source artifact whose
    Git blob identity and canonical contract SHA both match the durable receipt.
    This makes a projection/hash-only rewrite insufficient to rewrite negative
    memory silently: source bytes, contract digest and canonical exact rejection
    must all agree.
    """
    relative = record.get("source_artifact")
    expected_blob = record.get("source_blob_sha")
    expected_contract = record.get("source_contract_sha256")
    if not isinstance(relative, str) or not relative.strip():
        raise RuntimeError(f"rejected semantic-design {fingerprint_id} missing source_artifact")
    if not isinstance(expected_blob, str) or len(expected_blob) != 40:
        raise RuntimeError(f"rejected semantic-design {fingerprint_id} invalid source_blob_sha")
    if not isinstance(expected_contract, str) or len(expected_contract) != 64:
        raise RuntimeError(
            f"rejected semantic-design {fingerprint_id} invalid source_contract_sha256"
        )

    source_path = (ROOT / relative).resolve()
    try:
        source_path.relative_to(ROOT.resolve())
    except ValueError as exc:
        raise RuntimeError(
            f"rejected semantic-design {fingerprint_id} source_artifact escapes repository root"
        ) from exc
    if not source_path.is_file():
        raise RuntimeError(
            f"rejected semantic-design {fingerprint_id} source_artifact does not exist"
        )

    raw = source_path.read_bytes()
    actual_blob = _git_blob_sha1(raw)
    if actual_blob != expected_blob:
        raise RuntimeError(
            f"rejected semantic-design {fingerprint_id} source blob identity mismatch"
        )
    try:
        source = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(
            f"rejected semantic-design {fingerprint_id} source artifact must be canonical JSON"
        ) from exc
    if not isinstance(source, dict):
        raise RuntimeError(
            f"rejected semantic-design {fingerprint_id} source artifact must be an object"
        )
    if source.get("fingerprint_id") != fingerprint_id:
        raise RuntimeError(
            f"rejected semantic-design {fingerprint_id} source fingerprint mismatch"
        )
    if source.get("contract_sha256") != expected_contract:
        raise RuntimeError(
            f"rejected semantic-design {fingerprint_id} source contract receipt mismatch"
        )
    if _contract_sha256(source) != expected_contract:
        raise RuntimeError(
            f"rejected semantic-design {fingerprint_id} source contract content hash mismatch"
        )
    return source


def load_rejected_semantic_designs(path: Path = DEFAULT_SEMANTIC_PATH) -> dict[str, dict[str, Any]]:
    """Load deterministic label-invariant rejection identities.

    Backfilled identities are never trusted as stored hashes alone: both the
    full scientific-protocol digest and stricter executable-behavior digest are
    recomputed from the persisted projection and must match. Reconstructible
    entries are additionally bound to their packaged frozen source contract by
    Git blob identity and canonical contract SHA. Older rejections that cannot
    be reconstructed without guessing are explicitly marked unavailable instead
    of fuzzy-matched.
    """
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if payload.get("schema_version") != REJECTED_SEMANTIC_SCHEMA_VERSION:
        raise RuntimeError(
            "rejected semantic-design registry schema_version must equal "
            f"{REJECTED_SEMANTIC_SCHEMA_VERSION}"
        )
    if payload.get("scientific_identity_version") != SCIENTIFIC_IDENTITY_VERSION:
        raise RuntimeError("rejected semantic-design scientific identity version mismatch")
    if payload.get("strategy_behavior_identity_version") != STRATEGY_BEHAVIOR_IDENTITY_VERSION:
        raise RuntimeError("rejected semantic-design strategy behavior identity version mismatch")

    records = payload.get("records")
    if not isinstance(records, list):
        raise RuntimeError("rejected semantic-design registry must contain a list of records")

    by_fingerprint: dict[str, dict[str, Any]] = {}
    for record in records:
        if not isinstance(record, dict):
            raise RuntimeError("rejected semantic-design record must be an object")
        fingerprint_id = record.get("fingerprint_id")
        if not isinstance(fingerprint_id, str) or not fingerprint_id.strip():
            raise RuntimeError("rejected semantic-design record fingerprint_id must be non-empty")
        if fingerprint_id in by_fingerprint:
            raise RuntimeError(f"duplicate rejected semantic-design fingerprint id: {fingerprint_id}")
        status = record.get("semantic_identity_status")
        if status not in SEMANTIC_STATUSES:
            raise RuntimeError(
                f"rejected semantic-design {fingerprint_id} has invalid semantic_identity_status"
            )

        if status == SEMANTIC_BACKFILL_AVAILABLE:
            projection = record.get("projection")
            if not isinstance(projection, dict) or not projection:
                raise RuntimeError(
                    f"rejected semantic-design {fingerprint_id} must contain a behavior projection"
                )
            supplied_scientific_digest = record.get("scientific_design_sha256")
            computed_scientific_digest = scientific_design_sha256(projection)
            if (
                not isinstance(supplied_scientific_digest, str)
                or supplied_scientific_digest != computed_scientific_digest
            ):
                raise RuntimeError(
                    f"rejected semantic-design {fingerprint_id} scientific identity mismatch"
                )
            supplied_behavior_digest = record.get("strategy_behavior_sha256")
            computed_behavior_digest = strategy_behavior_sha256(projection)
            if (
                not isinstance(supplied_behavior_digest, str)
                or supplied_behavior_digest != computed_behavior_digest
            ):
                raise RuntimeError(
                    f"rejected semantic-design {fingerprint_id} strategy behavior identity mismatch"
                )
            _load_and_verify_source_contract(record, fingerprint_id)
        else:
            reason = record.get("reason")
            if not isinstance(reason, str) or not reason.strip():
                raise RuntimeError(
                    f"rejected semantic-design {fingerprint_id} unavailable backfill needs reason"
                )
            forbidden = (
                "scientific_design_sha256",
                "strategy_behavior_sha256",
                "projection",
                "source_artifact",
                "source_blob_sha",
                "source_contract_sha256",
            )
            if any(record.get(field) is not None for field in forbidden):
                raise RuntimeError(
                    f"rejected semantic-design {fingerprint_id} unavailable backfill cannot invent identity"
                )

        by_fingerprint[fingerprint_id] = record
    return by_fingerprint


def load_rejected_fingerprints(
    path: Path = DEFAULT_PATH,
    semantic_path: Path | None = None,
) -> list[dict[str, Any]]:
    """Load the canonical rejected-fingerprint registry plus semantic memory.

    The default canonical registry is augmented by a sidecar of deterministic
    scientific/executable identities. A custom registry path remains usable in
    isolated tests without requiring a matching sidecar unless one is supplied.
    """
    exact_path = Path(path)
    payload = json.loads(exact_path.read_text(encoding="utf-8"))
    entries = payload.get("entries")
    if not isinstance(entries, list):
        raise RuntimeError("rejected fingerprints registry must contain a list of entries")
    seen: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise RuntimeError("rejected fingerprint entry must be an object")
        missing = [field for field in REQUIRED_FIELDS if field not in entry]
        if missing:
            raise RuntimeError(f"rejected fingerprint entry missing fields: {missing}")
        fingerprint_id = str(entry["fingerprint_id"])
        if fingerprint_id in seen:
            raise RuntimeError(f"duplicate rejected fingerprint id: {fingerprint_id}")
        seen.add(fingerprint_id)
        if not isinstance(entry["horizons_evaluated"], list) or not entry["horizons_evaluated"]:
            raise RuntimeError(f"rejected fingerprint {fingerprint_id} must list evaluated horizons")
        if not isinstance(entry["do_not_resubmit_same_fingerprint"], bool):
            raise RuntimeError(
                f"rejected fingerprint {fingerprint_id} do_not_resubmit_same_fingerprint must be boolean"
            )

    use_semantic_path = semantic_path
    if use_semantic_path is None and exact_path.resolve() == DEFAULT_PATH.resolve():
        use_semantic_path = DEFAULT_SEMANTIC_PATH
    if use_semantic_path is None:
        return entries

    semantic = load_rejected_semantic_designs(Path(use_semantic_path))
    exact_ids = {str(entry["fingerprint_id"]) for entry in entries}
    if set(semantic) != exact_ids:
        missing = sorted(exact_ids - set(semantic))
        extra = sorted(set(semantic) - exact_ids)
        raise RuntimeError(
            f"rejected semantic-design coverage mismatch: missing={missing}, extra={extra}"
        )

    augmented: list[dict[str, Any]] = []
    for entry in entries:
        fingerprint_id = str(entry["fingerprint_id"])
        semantic_record = semantic[fingerprint_id]
        if semantic_record.get("semantic_identity_status") == SEMANTIC_BACKFILL_AVAILABLE:
            exact_contract = entry.get("rejection_evidence", {}).get("contract_sha256")
            semantic_contract = semantic_record.get("source_contract_sha256")
            if exact_contract != semantic_contract:
                raise RuntimeError(
                    f"rejected semantic-design {fingerprint_id} is not bound to canonical rejection contract"
                )
        merged = dict(entry)
        for key, value in semantic_record.items():
            if key != "fingerprint_id":
                merged[key] = value
        augmented.append(merged)
    return augmented


def is_rejected_fingerprint(
    fingerprint_id: str,
    entries: list[dict[str, Any]] | None = None,
) -> bool:
    """True only if ``fingerprint_id`` exactly matches a terminal rejection."""
    active = entries if entries is not None else load_rejected_fingerprints()
    return any(
        entry["fingerprint_id"] == fingerprint_id and entry.get("do_not_resubmit_same_fingerprint")
        for entry in active
    )


def rejection_record(
    fingerprint_id: str,
    entries: list[dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    active = entries if entries is not None else load_rejected_fingerprints()
    return next((entry for entry in active if entry["fingerprint_id"] == fingerprint_id), None)


def semantic_rejection_record(
    behavior_sha256: str,
    entries: list[dict[str, Any]] | None = None,
    *,
    scientific_design_digest: str | None = None,
) -> dict[str, Any] | None:
    """Return a terminal rejection matching executable behavior.

    Canonical durable memory must carry ``strategy_behavior_sha256`` and is
    matched only on that stricter no-rescue identity. The optional scientific
    fallback exists only for isolated injected legacy/test records that predate
    the behavior field; canonical registry loading never produces such records.
    """
    active = entries if entries is not None else load_rejected_fingerprints()
    for entry in active:
        if not entry.get("do_not_resubmit_same_fingerprint"):
            continue
        if entry.get("semantic_identity_status") != SEMANTIC_BACKFILL_AVAILABLE:
            continue
        stored_behavior = entry.get("strategy_behavior_sha256")
        if isinstance(stored_behavior, str):
            if stored_behavior == behavior_sha256:
                return entry
            continue
        if (
            scientific_design_digest is not None
            and entry.get("scientific_design_sha256") == scientific_design_digest
        ):
            return entry
    return None


def is_rejected_strategy_behavior(
    behavior_sha256: str,
    entries: list[dict[str, Any]] | None = None,
    *,
    scientific_design_digest: str | None = None,
) -> bool:
    return semantic_rejection_record(
        behavior_sha256,
        entries,
        scientific_design_digest=scientific_design_digest,
    ) is not None


def is_rejected_scientific_design(
    design_sha256: str,
    entries: list[dict[str, Any]] | None = None,
) -> bool:
    """Compatibility helper for injected legacy records only.

    Canonical no-rescue admission uses ``is_rejected_strategy_behavior``.
    """
    active = entries if entries is not None else load_rejected_fingerprints()
    return any(
        entry.get("do_not_resubmit_same_fingerprint")
        and entry.get("semantic_identity_status") == SEMANTIC_BACKFILL_AVAILABLE
        and entry.get("scientific_design_sha256") == design_sha256
        for entry in active
    )
