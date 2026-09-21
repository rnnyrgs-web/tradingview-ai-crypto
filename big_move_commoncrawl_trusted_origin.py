"""Trusted-provider-origin boundary for Cohort-001 Common Crawl evidence.

The lower-level WARC binder proves chronology/content consistency for retained bytes. It
must not, by itself, prove that Common Crawl actually served those bytes. This wrapper
first verifies GitHub-attested acquisition bundles produced by the canonical trusted
remote-acquisition workflow, binds their exact requests/response bytes to the retained
CDX/WARC evidence, and only then delegates to the lower-level semantic binder.

Authority is deliberately narrow: provider-byte authenticity + historical document
availability only. It grants no outcome, candidate, strategy, promotion or trade
authority.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from big_move_commoncrawl_warc_binding import validate_commoncrawl_historical_capture
from trusted_remote_acquisition import (
    freeze_commoncrawl_index_request,
    freeze_commoncrawl_warc_request,
)
from trusted_remote_acquisition_consumer import verify_attested_acquisition_bundle


def _safe_bundle_path(root: Path, ref: Any, *, field: str) -> Path:
    if not isinstance(ref, dict):
        raise ValueError(f"{field} trusted acquisition bundle reference missing")
    relpath = ref.get("artifact_relpath")
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


def _retained_bytes(root: Path, ref: Any, *, field: str) -> bytes:
    if not isinstance(ref, dict):
        raise ValueError(f"{field} retained reference missing")
    relpath = ref.get("artifact_relpath")
    sha256 = ref.get("sha256")
    if not isinstance(relpath, str) or not relpath.strip():
        raise ValueError(f"{field}.artifact_relpath missing")
    if (
        not isinstance(sha256, str)
        or len(sha256) != 64
        or sha256.lower() != sha256
    ):
        raise ValueError(f"{field}.sha256 must be lowercase SHA-256")
    try:
        int(sha256, 16)
    except ValueError as exc:
        raise ValueError(f"{field}.sha256 must be lowercase SHA-256") from exc
    relative = Path(relpath)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"{field}.artifact_relpath must stay inside retained artifact root")
    base = root.resolve()
    path = (base / relative).resolve()
    if not path.is_relative_to(base):
        raise ValueError(f"{field}.artifact_relpath escapes retained artifact root")
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise ValueError(f"{field} retained artifact is unavailable") from exc
    if hashlib.sha256(raw).hexdigest() != sha256:
        raise ValueError(f"{field} retained artifact SHA-256 mismatch")
    return raw


def _receipt_request(receipt: dict[str, Any], *, field: str) -> dict[str, Any]:
    request = receipt.get("request")
    if not isinstance(request, dict):
        raise ValueError(f"{field} trusted receipt request block missing")
    return request


def _assert_request_exact(
    receipt: dict[str, Any],
    *,
    expected_url: str,
    expected_range_header: str | None,
    field: str,
) -> None:
    request = _receipt_request(receipt, field=field)
    if request.get("method") != "GET":
        raise ValueError(f"{field} trusted receipt method mismatch")
    if request.get("url") != expected_url:
        raise ValueError(f"{field} trusted receipt URL mismatch")
    if request.get("range_header") != expected_range_header:
        raise ValueError(f"{field} trusted receipt Range mismatch")


def _matching_index_row(
    raw: bytes,
    *,
    upstream_locator: str,
) -> dict[str, Any]:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("trusted Common Crawl index response must be UTF-8") from exc
    matches: list[dict[str, Any]] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError("trusted Common Crawl index response must be JSON-lines") from exc
        if not isinstance(row, dict):
            raise ValueError("trusted Common Crawl index row must be an object")
        if row.get("url") == upstream_locator and str(row.get("status")) == "200":
            matches.append(row)
    if len(matches) != 1:
        raise ValueError("trusted Common Crawl index must contain exactly one matching 200 row")
    return matches[0]


def validate_trusted_commoncrawl_historical_capture(
    capture: dict[str, Any],
    *,
    upstream_locator: str,
    decision_at: str,
    document_bytes: bytes,
    document_sha256: str,
    artifact_root: str | Path,
    repo_root: str | Path | None = None,
) -> dict[str, Any]:
    """Require attested provider origin before historical Common Crawl evidence can bind."""

    if not isinstance(capture, dict) or capture.get("schema") != "commoncrawl_warc_capture_proof.v1":
        raise ValueError("primary document requires commoncrawl_warc_capture_proof.v1")
    collection = capture.get("index_collection")
    if not isinstance(collection, str):
        raise ValueError("Common Crawl index_collection missing")
    root = Path(artifact_root)

    index_bundle = _safe_bundle_path(
        root,
        capture.get("index_acquisition_bundle"),
        field="commoncrawl.index_acquisition_bundle",
    )
    index_receipt, trusted_index_bytes = verify_attested_acquisition_bundle(
        index_bundle,
        expected_source_kind="COMMONCRAWL_INDEX",
    )
    expected_index = freeze_commoncrawl_index_request(
        collection=collection,
        target_url=upstream_locator,
    )
    _assert_request_exact(
        index_receipt,
        expected_url=expected_index.url,
        expected_range_header=None,
        field="commoncrawl.index_acquisition",
    )
    retained_index_bytes = _retained_bytes(
        root,
        capture.get("index_response"),
        field="commoncrawl.index_response",
    )
    if trusted_index_bytes != retained_index_bytes:
        raise ValueError("retained Common Crawl index bytes do not equal attested provider response")

    row = _matching_index_row(trusted_index_bytes, upstream_locator=upstream_locator)
    filename = row.get("filename")
    try:
        offset = int(row.get("offset"))
        length = int(row.get("length"))
    except (TypeError, ValueError) as exc:
        raise ValueError("trusted Common Crawl index offset/length must be integers") from exc
    expected_warc = freeze_commoncrawl_warc_request(
        collection=collection,
        filename=filename,
        offset=offset,
        length=length,
    )

    warc_bundle = _safe_bundle_path(
        root,
        capture.get("warc_acquisition_bundle"),
        field="commoncrawl.warc_acquisition_bundle",
    )
    warc_receipt, trusted_warc_bytes = verify_attested_acquisition_bundle(
        warc_bundle,
        expected_source_kind="COMMONCRAWL_WARC_RANGE",
    )
    _assert_request_exact(
        warc_receipt,
        expected_url=expected_warc.url,
        expected_range_header=expected_warc.range_header,
        field="commoncrawl.warc_acquisition",
    )
    retained_warc_bytes = _retained_bytes(
        root,
        capture.get("warc_range"),
        field="commoncrawl.warc_range",
    )
    if trusted_warc_bytes != retained_warc_bytes:
        raise ValueError("retained Common Crawl WARC bytes do not equal attested provider response")

    result = validate_commoncrawl_historical_capture(
        capture,
        upstream_locator=upstream_locator,
        decision_at=decision_at,
        document_bytes=document_bytes,
        document_sha256=document_sha256,
        artifact_root=root,
        repo_root=repo_root,
    )
    enriched = dict(result)
    enriched["provider_origin"] = "ATTESTED_TRUSTED_REMOTE_ACQUISITION"
    enriched["index_receipt_sha256"] = index_receipt.get("receipt_sha256")
    enriched["warc_receipt_sha256"] = warc_receipt.get("receipt_sha256")
    return enriched
