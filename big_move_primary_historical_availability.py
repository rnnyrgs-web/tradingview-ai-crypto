"""Independent historical-availability proof for Cohort 001 primary documents.

The existing primary-document binder proves content/value linkage but deliberately does
not treat caller-authored publication timestamps as anti-backdating evidence. This
module closes that specific boundary by requiring an exact Common Crawl WARC capture
of the same primary-document bytes at or before the historical decision timestamp,
and by requiring the retained index/WARC bytes to come from GitHub-attested trusted
remote acquisitions from canonical main.

When an exact URL query contains multiple authentic Common Crawl captures, the
outcome-blind v2 selector deterministically chooses the latest pre-decision capture and
requires that exact selected row identity to be frozen in the capture proof.

It grants historical-evidence authority only; never label, forecast, promotion, broker
or trading authority.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from big_move_commoncrawl_trusted_origin_v2 import (
    validate_trusted_commoncrawl_historical_capture_v2,
)

ELIGIBLE_SOURCE_IDS = {
    "PRIMARY_CONTRACT_OR_GENESIS_DOC",
    "TIMESTAMPED_PRIMARY_SUPPLY_DISCLOSURE",
}
MAX_RETAINED_BYTES = 32 * 1024 * 1024


def _safe_path(root: Path, relpath: Any, *, field: str) -> Path:
    if not isinstance(relpath, str) or not relpath.strip():
        raise ValueError(f"{field}.artifact_relpath missing")
    relative = Path(relpath)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"{field}.artifact_relpath must stay inside retained artifact root")
    base = root.resolve()
    path = (base / relative).resolve()
    if not path.is_relative_to(base):
        raise ValueError(f"{field}.artifact_relpath escapes retained artifact root")
    return path


def _verified_bytes(root: Path, relpath: Any, sha256: Any, *, field: str) -> bytes:
    if not isinstance(sha256, str) or len(sha256) != 64 or sha256.lower() != sha256:
        raise ValueError(f"{field}.sha256 must be lowercase SHA-256")
    try:
        int(sha256, 16)
    except ValueError as exc:
        raise ValueError(f"{field}.sha256 must be lowercase SHA-256") from exc
    path = _safe_path(root, relpath, field=field)
    try:
        if path.stat().st_size > MAX_RETAINED_BYTES:
            raise ValueError(f"{field} retained artifact is too large")
        raw = path.read_bytes()
    except OSError as exc:
        raise ValueError(f"{field} retained artifact is unavailable") from exc
    if hashlib.sha256(raw).hexdigest() != sha256:
        raise ValueError(f"{field} retained artifact SHA-256 mismatch")
    return raw


def _unique_json_object(pairs: list[tuple[str, Any]], *, field: str) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"{field} contains duplicate JSON object key {key!r}")
        result[key] = value
    return result


def _reject_nonstandard_json_constant(value: str, *, field: str) -> Any:
    raise ValueError(f"{field} contains non-standard JSON numeric constant {value}")


def _verified_json(root: Path, ref: Any, *, field: str) -> dict[str, Any]:
    if not isinstance(ref, dict):
        raise ValueError(f"{field} retained reference missing")
    raw = _verified_bytes(root, ref.get("artifact_relpath"), ref.get("sha256"), field=field)
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(f"{field} must contain JSON") from exc
    try:
        value = json.loads(
            text,
            object_pairs_hook=lambda pairs: _unique_json_object(pairs, field=field),
            parse_constant=lambda constant: _reject_nonstandard_json_constant(constant, field=field),
        )
    except json.JSONDecodeError as exc:
        raise ValueError(f"{field} must contain JSON") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{field} must contain a JSON object")
    return value


def validate_primary_document_historical_availability(
    record: dict[str, Any],
    *,
    decision_at: str,
    artifact_root: str | Path,
    repo_root: str | Path | None = None,
) -> dict[str, Any]:
    """Require an attested exact pre-decision Common Crawl capture for a primary document."""

    if not isinstance(record, dict) or record.get("source_id") not in ELIGIBLE_SOURCE_IDS:
        raise ValueError("record is not an eligible primary-document source")
    root = Path(artifact_root)
    proof = _verified_json(root, record.get("source_proof"), field="primary.source_proof")
    if proof.get("schema") != "primary_document_proof.v1":
        raise ValueError("primary source requires primary_document_proof.v1")
    if proof.get("source_id") != record.get("source_id"):
        raise ValueError("primary proof source_id does not match record")

    locator = proof.get("upstream_locator")
    if not isinstance(locator, str) or not locator.strip():
        raise ValueError("primary proof upstream_locator missing")
    document_sha256 = proof.get("document_sha256")
    document = _verified_bytes(
        root,
        proof.get("document_relpath"),
        document_sha256,
        field="primary.document",
    )
    capture = _verified_json(
        root,
        proof.get("historical_capture"),
        field="primary.historical_capture",
    )
    result = validate_trusted_commoncrawl_historical_capture_v2(
        capture,
        upstream_locator=locator,
        decision_at=decision_at,
        document_bytes=document,
        document_sha256=document_sha256,
        artifact_root=root,
        repo_root=repo_root,
    )
    return {
        "schema": "two_x_primary_document_historical_availability_result.v2",
        "status": "BOUND",
        "source_id": record.get("source_id"),
        "upstream_locator": locator,
        "document_sha256": document_sha256,
        "capture_at": result["capture_at"],
        "selected_index_row_sha256": result["selected_index_row_sha256"],
        "warc_record_id": result["warc_record_id"],
        "warc_payload_digest": result["warc_payload_digest"],
        "provider_origin": result["provider_origin"],
        "index_receipt_sha256": result["index_receipt_sha256"],
        "warc_receipt_sha256": result["warc_receipt_sha256"],
        "authority": "HISTORICAL_AVAILABILITY_EVIDENCE_ONLY_NO_OUTCOME_OR_PREDICTION_AUTHORITY",
    }
