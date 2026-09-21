"""Authoritative Common Crawl capture selection + attested-origin boundary for Cohort 001.

This v2 boundary fixes a real-provider property that the legacy binder treated as an
error: an exact URL query can legitimately return multiple HTTP-200 captures in one
Common Crawl collection. Selection is outcome-blind and deterministic: among exact-URL,
HTTP-200 captures no later than the decision timestamp, choose the latest timestamp; for
same-timestamp alternatives choose the lexicographically smallest
(filename, numeric offset, numeric length, digest) tuple. Exact duplicate rows collapse
to one canonical identity.

The selected row must also be persisted in the caller's capture proof and must equal the
deterministic selection. Provider bytes themselves still require the canonical-main
GitHub-attested remote-acquisition boundary. This module grants historical-availability
authority only; never labels, forecasts, promotion, broker, or trading authority.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import big_move_commoncrawl_trusted_origin as legacy_origin
from big_move_commoncrawl_warc_binding import (
    COLLECTION_RE,
    SHA1_BASE32_RE,
    SHA256_RE,
    WARC_SHA1_BASE32_RE,
    _cc_timestamp,
    _clean_https,
    _parse_index_rows,
    _parse_warc_record,
    _utc,
)
from trusted_remote_acquisition import (
    freeze_commoncrawl_index_request,
    freeze_commoncrawl_warc_request,
)

CONTRACT_PATH = "money_intelligence/2x_commoncrawl_capture_selection_v2.json"
CONTRACT_ARTIFACT_ID = "2X-COMMONCRAWL-CAPTURE-SELECTION-002-v1"
CONTRACT_GIT_BLOB_SHA = "a237681ea3edecfe82bf26a59e0b1648af84731a"
_SELECTED_FIELDS = ("url", "status", "timestamp", "filename", "offset", "length", "digest")


def _git_blob_sha(raw: bytes) -> str:
    header = f"blob {len(raw)}\0".encode("ascii")
    return hashlib.sha1(header + raw, usedforsecurity=False).hexdigest()


def load_commoncrawl_selection_contract(repo_root: str | Path | None = None) -> dict[str, Any]:
    root = Path(repo_root) if repo_root is not None else Path(__file__).resolve().parent
    path = (root / CONTRACT_PATH).resolve()
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise ValueError("Common Crawl capture-selection contract is unavailable") from exc
    if _git_blob_sha(raw) != CONTRACT_GIT_BLOB_SHA:
        raise ValueError("Common Crawl capture-selection contract drifted from frozen Git blob")
    try:
        contract = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Common Crawl capture-selection contract is malformed") from exc
    if not isinstance(contract, dict) or contract.get("artifact_id") != CONTRACT_ARTIFACT_ID:
        raise ValueError("unexpected Common Crawl capture-selection contract identity")
    return contract


def _canonical_candidate(
    row: dict[str, Any],
    *,
    upstream_locator: str,
    collection: str,
    decision_at: str,
) -> tuple[dict[str, str], Any] | None:
    if row.get("url") != upstream_locator or str(row.get("status")) != "200":
        return None

    timestamp = row.get("timestamp")
    capture_at = _cc_timestamp(timestamp, field="commoncrawl.index.timestamp")
    decision = _utc(decision_at, field="decision_at")
    if capture_at > decision:
        return None

    filename = row.get("filename")
    if not isinstance(filename, str) or not filename.startswith(f"crawl-data/{collection}/"):
        raise ValueError("matching Common Crawl index filename does not belong to frozen collection")
    if not filename.endswith(".warc.gz") or "/warc/" not in filename:
        raise ValueError("matching Common Crawl index filename is not a WARC archive")

    try:
        offset = int(row.get("offset"))
        length = int(row.get("length"))
    except (TypeError, ValueError) as exc:
        raise ValueError("matching Common Crawl index offset/length must be integers") from exc
    if offset < 0 or length <= 0:
        raise ValueError("matching Common Crawl index offset/length are invalid")

    digest = row.get("digest")
    if not isinstance(digest, str) or not SHA1_BASE32_RE.fullmatch(digest):
        raise ValueError("matching Common Crawl index digest missing or unsupported")

    canonical = {
        "url": upstream_locator,
        "status": "200",
        "timestamp": timestamp,
        "filename": filename,
        "offset": str(offset),
        "length": str(length),
        "digest": digest,
    }
    return canonical, capture_at


def select_commoncrawl_index_row(
    raw: bytes,
    *,
    upstream_locator: str,
    collection: str,
    decision_at: str,
    declared_selection: dict[str, Any] | None = None,
) -> dict[str, str]:
    """Deterministically select one authenticated pre-decision Common Crawl capture."""

    if not isinstance(collection, str) or not COLLECTION_RE.fullmatch(collection):
        raise ValueError("Common Crawl index_collection is invalid")
    candidates: dict[str, tuple[dict[str, str], Any]] = {}
    for row in _parse_index_rows(raw):
        candidate = _canonical_candidate(
            row,
            upstream_locator=upstream_locator,
            collection=collection,
            decision_at=decision_at,
        )
        if candidate is None:
            continue
        canonical, capture_at = candidate
        identity = json.dumps(canonical, sort_keys=True, separators=(",", ":"))
        candidates[identity] = (canonical, capture_at)

    if not candidates:
        raise ValueError("no matching Common Crawl 200 capture at or before decision_at")

    latest_at = max(capture_at for _, capture_at in candidates.values())
    latest = [
        canonical
        for canonical, capture_at in candidates.values()
        if capture_at == latest_at
    ]
    selected = min(
        latest,
        key=lambda row: (
            row["filename"],
            int(row["offset"]),
            int(row["length"]),
            row["digest"],
        ),
    )

    if declared_selection is not None:
        if not isinstance(declared_selection, dict):
            raise ValueError("Common Crawl selected_index_row must be an object")
        projected = {field: declared_selection.get(field) for field in _SELECTED_FIELDS}
        if set(declared_selection) != set(_SELECTED_FIELDS) or projected != selected:
            raise ValueError(
                "declared Common Crawl selected_index_row does not equal deterministic selection"
            )
    return selected


def _selection_sha256(selected: dict[str, str]) -> str:
    raw = json.dumps(selected, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def validate_trusted_commoncrawl_historical_capture_v2(
    capture: dict[str, Any],
    *,
    upstream_locator: str,
    decision_at: str,
    document_bytes: bytes,
    document_sha256: str,
    artifact_root: str | Path,
    repo_root: str | Path | None = None,
) -> dict[str, Any]:
    """Require attested provider origin plus deterministic pre-decision capture selection."""

    load_commoncrawl_selection_contract(repo_root)
    if not isinstance(capture, dict) or capture.get("schema") != "commoncrawl_warc_capture_proof.v1":
        raise ValueError("primary document requires commoncrawl_warc_capture_proof.v1")
    collection = capture.get("index_collection")
    if not isinstance(collection, str) or not COLLECTION_RE.fullmatch(collection):
        raise ValueError("Common Crawl index_collection is invalid")
    root = Path(artifact_root)

    index_bundle = legacy_origin._safe_bundle_path(
        root,
        capture.get("index_acquisition_bundle"),
        field="commoncrawl.index_acquisition_bundle",
    )
    index_receipt, trusted_index_bytes = legacy_origin.verify_attested_acquisition_bundle(
        index_bundle,
        expected_source_kind="COMMONCRAWL_INDEX",
    )
    expected_index = freeze_commoncrawl_index_request(
        collection=collection,
        target_url=upstream_locator,
    )
    if capture.get("index_query_locator") != expected_index.url:
        raise ValueError("Common Crawl retained index locator does not equal trusted canonical request")
    legacy_origin._assert_request_exact(
        index_receipt,
        expected_url=expected_index.url,
        expected_range_header=None,
        field="commoncrawl.index_acquisition",
    )
    retained_index_bytes = legacy_origin._retained_bytes(
        root,
        capture.get("index_response"),
        field="commoncrawl.index_response",
    )
    if trusted_index_bytes != retained_index_bytes:
        raise ValueError("retained Common Crawl index bytes do not equal attested provider response")

    selected = select_commoncrawl_index_row(
        trusted_index_bytes,
        upstream_locator=upstream_locator,
        collection=collection,
        decision_at=decision_at,
        declared_selection=capture.get("selected_index_row"),
    )
    filename = selected["filename"]
    offset = int(selected["offset"])
    length = int(selected["length"])
    expected_warc = freeze_commoncrawl_warc_request(
        collection=collection,
        filename=filename,
        offset=offset,
        length=length,
    )
    if capture.get("warc_range_locator") != expected_warc.url:
        raise ValueError("Common Crawl retained WARC locator does not equal deterministic selected row")

    warc_bundle = legacy_origin._safe_bundle_path(
        root,
        capture.get("warc_acquisition_bundle"),
        field="commoncrawl.warc_acquisition_bundle",
    )
    warc_receipt, trusted_warc_bytes = legacy_origin.verify_attested_acquisition_bundle(
        warc_bundle,
        expected_source_kind="COMMONCRAWL_WARC_RANGE",
    )
    legacy_origin._assert_request_exact(
        warc_receipt,
        expected_url=expected_warc.url,
        expected_range_header=expected_warc.range_header,
        field="commoncrawl.warc_acquisition",
    )
    retained_warc_bytes = legacy_origin._retained_bytes(
        root,
        capture.get("warc_range"),
        field="commoncrawl.warc_range",
    )
    if trusted_warc_bytes != retained_warc_bytes:
        raise ValueError("retained Common Crawl WARC bytes do not equal attested provider response")
    if len(retained_warc_bytes) != length:
        raise ValueError("retained Common Crawl range length does not match selected index length")

    warc_locator = _clean_https(
        capture.get("warc_range_locator"),
        field="commoncrawl.warc_range_locator",
        required_host="data.commoncrawl.org",
    )
    if warc_locator != f"https://data.commoncrawl.org/{filename}":
        raise ValueError("Common Crawl WARC locator does not match selected index filename")

    warc_headers, _, _, body = _parse_warc_record(retained_warc_bytes)
    if warc_headers.get("warc-target-uri") != upstream_locator:
        raise ValueError("WARC-Target-URI does not match primary upstream locator")

    capture_at = _cc_timestamp(selected["timestamp"], field="commoncrawl.index.timestamp")
    warc_date = _utc(warc_headers.get("warc-date"), field="warc.WARC-Date")
    if warc_date != capture_at:
        raise ValueError("WARC-Date does not equal deterministic selected index timestamp")
    if warc_date > _utc(decision_at, field="decision_at"):
        raise ValueError("WARC capture occurred after decision_at")

    payload_digest = warc_headers.get("warc-payload-digest")
    payload_match = (
        WARC_SHA1_BASE32_RE.fullmatch(payload_digest)
        if isinstance(payload_digest, str)
        else None
    )
    if payload_match is None:
        raise ValueError("WARC-Payload-Digest missing or unsupported")
    if selected["digest"] != payload_match.group(1):
        raise ValueError("selected Common Crawl index digest does not match WARC-Payload-Digest")

    if not isinstance(document_sha256, str) or not SHA256_RE.fullmatch(document_sha256):
        raise ValueError("document_sha256 must be lowercase SHA-256")
    if hashlib.sha256(document_bytes).hexdigest() != document_sha256:
        raise ValueError("retained primary document SHA-256 mismatch")
    if hashlib.sha256(body).hexdigest() != document_sha256 or body != document_bytes:
        raise ValueError("retained primary document bytes do not equal archived WARC HTTP entity")

    record_id = warc_headers.get("warc-record-id")
    if (
        not isinstance(record_id, str)
        or not record_id.startswith("<urn:uuid:")
        or not record_id.endswith(">")
    ):
        raise ValueError("WARC-Record-ID is missing or malformed")

    return {
        "schema": "two_x_commoncrawl_historical_capture_result.v2",
        "status": "BOUND",
        "artifact_id": CONTRACT_ARTIFACT_ID,
        "index_collection": collection,
        "capture_at": warc_date.isoformat().replace("+00:00", "Z"),
        "target_uri": upstream_locator,
        "selected_index_row": selected,
        "selected_index_row_sha256": _selection_sha256(selected),
        "warc_record_id": record_id,
        "warc_filename": filename,
        "warc_offset": offset,
        "warc_length": length,
        "warc_payload_digest": payload_digest,
        "document_sha256": document_sha256,
        "provider_origin": "ATTESTED_TRUSTED_REMOTE_ACQUISITION",
        "index_receipt_sha256": index_receipt.get("receipt_sha256"),
        "warc_receipt_sha256": warc_receipt.get("receipt_sha256"),
        "authority": "HISTORICAL_AVAILABILITY_EVIDENCE_ONLY_NO_OUTCOME_OR_PREDICTION_AUTHORITY",
    }
