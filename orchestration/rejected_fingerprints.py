from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from orchestration.scientific_design_identity import scientific_design_sha256

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

SEMANTIC_BACKFILL_AVAILABLE = "BACKFILLED_STRUCTURED_CONTRACT"
SEMANTIC_BACKFILL_UNAVAILABLE = "SEMANTIC_BACKFILL_UNAVAILABLE"
SEMANTIC_STATUSES = {SEMANTIC_BACKFILL_AVAILABLE, SEMANTIC_BACKFILL_UNAVAILABLE}


def load_rejected_semantic_designs(path: Path = DEFAULT_SEMANTIC_PATH) -> dict[str, dict[str, Any]]:
    """Load deterministic label-invariant rejection identities.

    Backfilled identities are never trusted as stored hashes alone: the digest
    is recomputed from the persisted behavior-driving projection and must
    match. Older rejections that cannot be reconstructed without guessing are
    explicitly marked unavailable instead of fuzzy-matched.
    """
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1:
        raise RuntimeError("rejected semantic-design registry schema_version must equal 1")
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
            supplied_digest = record.get("scientific_design_sha256")
            computed_digest = scientific_design_sha256(projection)
            if not isinstance(supplied_digest, str) or supplied_digest != computed_digest:
                raise RuntimeError(
                    f"rejected semantic-design {fingerprint_id} scientific identity mismatch"
                )
            for field in ("source_artifact", "source_blob_sha", "source_contract_sha256"):
                value = record.get(field)
                if not isinstance(value, str) or not value.strip():
                    raise RuntimeError(
                        f"rejected semantic-design {fingerprint_id} missing {field}"
                    )
        else:
            reason = record.get("reason")
            if not isinstance(reason, str) or not reason.strip():
                raise RuntimeError(
                    f"rejected semantic-design {fingerprint_id} unavailable backfill needs reason"
                )
            if record.get("scientific_design_sha256") is not None or record.get("projection") is not None:
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
        merged = dict(entry)
        for key, value in semantic[fingerprint_id].items():
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
    design_sha256: str,
    entries: list[dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    active = entries if entries is not None else load_rejected_fingerprints()
    return next(
        (
            entry
            for entry in active
            if entry.get("do_not_resubmit_same_fingerprint")
            and entry.get("semantic_identity_status") == SEMANTIC_BACKFILL_AVAILABLE
            and entry.get("scientific_design_sha256") == design_sha256
        ),
        None,
    )


def is_rejected_scientific_design(
    design_sha256: str,
    entries: list[dict[str, Any]] | None = None,
) -> bool:
    return semantic_rejection_record(design_sha256, entries) is not None
