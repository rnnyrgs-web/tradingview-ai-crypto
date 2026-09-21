"""Fail-closed Common Crawl WARC historical-availability binding for 2x Cohort 001.

A caller-authored ``published_at`` is not proof that a primary document existed before a
historical decision. This module binds the exact retained primary-document bytes to a
Common Crawl index row and the exact retained WARC response range selected by that row.

This is deliberately narrow. It accepts only HTTP 200 response records whose target URI
exactly matches the primary-document locator, whose Common Crawl capture time is no later
than the decision timestamp, whose compressed range length matches the index, whose WARC
block digest is recomputed, and whose HTTP entity bytes reproduce the retained document
SHA-256. Unsupported encodings or ambiguous index rows fail closed.
"""

from __future__ import annotations

import base64
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path
import re
from typing import Any
from urllib.parse import parse_qs, urlsplit

UTC = timezone.utc
CONTRACT_PATH = "money_intelligence/2x_commoncrawl_warc_binding_v1.json"
CONTRACT_ARTIFACT_ID = "2X-COMMONCRAWL-WARC-BINDING-001-v1"
CONTRACT_GIT_BLOB_SHA = "37ea2df16cc1b025658144dca467a56ec71c5bfb"
MAX_RETAINED_BYTES = 32 * 1024 * 1024
COLLECTION_RE = re.compile(r"^CC-MAIN-\d{4}-\d{2}$")
TIMESTAMP_RE = re.compile(r"^\d{14}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
SHA1_BASE32_RE = re.compile(r"^[A-Z2-7]{32}$")
WARC_SHA1_BASE32_RE = re.compile(r"^sha1:([A-Z2-7]{32})$")


def _git_blob_sha(raw: bytes) -> str:
    header = f"blob {len(raw)}\0".encode("ascii")
    return hashlib.sha1(header + raw, usedforsecurity=False).hexdigest()


def _utc(value: Any, *, field: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError(f"{field} must be RFC3339 UTC ending in Z")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise ValueError(f"{field} must be valid RFC3339 UTC") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != UTC.utcoffset(parsed):
        raise ValueError(f"{field} must be UTC")
    return parsed


def _cc_timestamp(value: Any, *, field: str) -> datetime:
    if not isinstance(value, str) or not TIMESTAMP_RE.fullmatch(value):
        raise ValueError(f"{field} must be Common Crawl YYYYmmddHHMMSS")
    try:
        return datetime.strptime(value, "%Y%m%d%H%M%S").replace(tzinfo=UTC)
    except ValueError as exc:
        raise ValueError(f"{field} is not a valid Common Crawl timestamp") from exc


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


def _retained_bytes(root: Path, ref: Any, *, field: str) -> bytes:
    if not isinstance(ref, dict):
        raise ValueError(f"{field} retained reference missing")
    sha256 = ref.get("sha256")
    if not isinstance(sha256, str) or not SHA256_RE.fullmatch(sha256):
        raise ValueError(f"{field}.sha256 must be lowercase SHA-256")
    path = _safe_path(root, ref.get("artifact_relpath"), field=field)
    try:
        size = path.stat().st_size
        if size > MAX_RETAINED_BYTES:
            raise ValueError(f"{field} retained artifact is too large")
        raw = path.read_bytes()
    except OSError as exc:
        raise ValueError(f"{field} retained artifact is unavailable") from exc
    if hashlib.sha256(raw).hexdigest() != sha256:
        raise ValueError(f"{field} retained artifact SHA-256 mismatch")
    return raw


def _clean_https(value: Any, *, field: str, required_host: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty URL")
    parts = urlsplit(value)
    if (
        parts.scheme != "https"
        or parts.hostname != required_host
        or parts.username
        or parts.password
        or parts.fragment
    ):
        raise ValueError(f"{field} must be clean HTTPS on {required_host}")
    return value


def load_commoncrawl_contract(repo_root: str | Path | None = None) -> dict[str, Any]:
    root = Path(repo_root) if repo_root is not None else Path(__file__).resolve().parent
    path = (root / CONTRACT_PATH).resolve()
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise ValueError("Common Crawl binding contract is unavailable") from exc
    if _git_blob_sha(raw) != CONTRACT_GIT_BLOB_SHA:
        raise ValueError("Common Crawl binding contract drifted from frozen Git blob")
    try:
        contract = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Common Crawl binding contract is malformed") from exc
    if not isinstance(contract, dict) or contract.get("artifact_id") != CONTRACT_ARTIFACT_ID:
        raise ValueError("unexpected Common Crawl binding contract identity")
    return contract


def _parse_index_rows(raw: bytes) -> list[dict[str, Any]]:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("Common Crawl index response must be UTF-8") from exc
    rows: list[dict[str, Any]] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        # output=json returns JSON objects line-by-line. CDXJ prefix text is
        # intentionally unsupported here to avoid ambiguous parsing.
        try:
            row = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise ValueError("Common Crawl index response must be JSON-lines") from exc
        if not isinstance(row, dict):
            raise ValueError("Common Crawl index row must be an object")
        rows.append(row)
    if not rows:
        raise ValueError("Common Crawl index response contains no rows")
    return rows


def _split_headers(raw: bytes, *, field: str) -> tuple[bytes, bytes]:
    marker = b"\r\n\r\n"
    if marker not in raw:
        raise ValueError(f"{field} must use CRLF-delimited headers")
    return raw.split(marker, 1)


def _header_map(
    raw: bytes,
    *,
    field: str,
    first_line_prefix: bytes | None = None,
) -> tuple[str, dict[str, str]]:
    head, _ = _split_headers(raw, field=field)
    lines = head.split(b"\r\n")
    if not lines:
        raise ValueError(f"{field} headers missing")
    try:
        first = lines[0].decode("ascii")
    except UnicodeDecodeError as exc:
        raise ValueError(f"{field} first line must be ASCII") from exc
    if first_line_prefix is not None and not lines[0].startswith(first_line_prefix):
        raise ValueError(f"{field} first line is unexpected")
    headers: dict[str, str] = {}
    for line in lines[1:]:
        if b":" not in line:
            raise ValueError(f"{field} malformed header line")
        key_raw, value_raw = line.split(b":", 1)
        try:
            key = key_raw.decode("ascii").strip().lower()
            value = value_raw.decode("utf-8").strip()
        except UnicodeDecodeError as exc:
            raise ValueError(f"{field} header encoding is unsupported") from exc
        if not key or key in headers:
            raise ValueError(f"{field} duplicate or empty header")
        headers[key] = value
    return first, headers


def _sha1_base32(raw: bytes) -> str:
    digest = hashlib.sha1(raw, usedforsecurity=False).digest()
    return base64.b32encode(digest).decode("ascii").rstrip("=")


def _parse_warc_record(
    compressed: bytes,
) -> tuple[dict[str, str], bytes, dict[str, str], bytes]:
    try:
        warc = gzip.decompress(compressed)
    except (OSError, EOFError) as exc:
        raise ValueError("Common Crawl retained range is not a valid gzip WARC member") from exc

    first, warc_headers = _header_map(warc, field="warc", first_line_prefix=b"WARC/")
    _, block = _split_headers(warc, field="warc")
    if not first.startswith("WARC/"):
        raise ValueError("WARC version line missing")
    if warc_headers.get("warc-type") != "response":
        raise ValueError("Common Crawl WARC record must be WARC-Type response")
    try:
        declared_length = int(warc_headers.get("content-length", ""))
    except ValueError as exc:
        raise ValueError("WARC Content-Length must be an integer") from exc
    if declared_length != len(block):
        raise ValueError("WARC Content-Length does not match retained block bytes")

    block_digest = warc_headers.get("warc-block-digest")
    computed_block = "sha1:" + _sha1_base32(block)
    if block_digest != computed_block:
        raise ValueError("WARC block digest does not match retained block bytes")

    status_line, http_headers = _header_map(block, field="http", first_line_prefix=b"HTTP/")
    _, body = _split_headers(block, field="http")
    parts = status_line.split()
    if len(parts) < 2 or parts[1] != "200":
        raise ValueError("Common Crawl WARC HTTP response must be status 200")
    content_encoding = http_headers.get("content-encoding", "").strip().lower()
    if content_encoding not in {"", "identity"}:
        raise ValueError("Common Crawl HTTP entity uses unsupported content-encoding")
    return warc_headers, block, http_headers, body


def validate_commoncrawl_historical_capture(
    capture: dict[str, Any],
    *,
    upstream_locator: str,
    decision_at: str | datetime,
    document_bytes: bytes,
    document_sha256: str,
    artifact_root: str | Path,
    repo_root: str | Path | None = None,
) -> dict[str, Any]:
    """Bind primary-document bytes to one historical Common Crawl response capture."""

    load_commoncrawl_contract(repo_root)
    if not isinstance(capture, dict) or capture.get("schema") != "commoncrawl_warc_capture_proof.v1":
        raise ValueError("primary document requires commoncrawl_warc_capture_proof.v1")
    decision = _utc(decision_at, field="decision_at") if isinstance(decision_at, str) else decision_at
    if not isinstance(decision, datetime) or decision.tzinfo is None:
        raise ValueError("decision_at must be timezone-aware")
    decision = decision.astimezone(UTC)

    collection = capture.get("index_collection")
    if not isinstance(collection, str) or not COLLECTION_RE.fullmatch(collection):
        raise ValueError("Common Crawl index_collection is invalid")

    index_locator = _clean_https(
        capture.get("index_query_locator"),
        field="commoncrawl.index_query_locator",
        required_host="index.commoncrawl.org",
    )
    index_parts = urlsplit(index_locator)
    if index_parts.path != f"/{collection}-index":
        raise ValueError("Common Crawl index locator collection mismatch")
    query = parse_qs(index_parts.query)
    if query.get("output") != ["json"]:
        raise ValueError("Common Crawl index query must request output=json")

    root = Path(artifact_root)
    index_raw = _retained_bytes(root, capture.get("index_response"), field="commoncrawl.index_response")
    rows = _parse_index_rows(index_raw)
    matches = [
        row
        for row in rows
        if row.get("url") == upstream_locator
        and str(row.get("status")) == "200"
        and isinstance(row.get("timestamp"), str)
    ]
    if len(matches) != 1:
        raise ValueError("Common Crawl index must contain exactly one matching 200 capture row")
    row = matches[0]

    capture_at = _cc_timestamp(row.get("timestamp"), field="commoncrawl.index.timestamp")
    if capture_at > decision:
        raise ValueError("Common Crawl capture occurred after decision_at")

    filename = row.get("filename")
    if not isinstance(filename, str) or not filename.startswith(f"crawl-data/{collection}/"):
        raise ValueError("Common Crawl index filename does not belong to frozen collection")
    if not filename.endswith(".warc.gz") or "/warc/" not in filename:
        raise ValueError("Common Crawl index filename is not a WARC archive")
    try:
        offset = int(row.get("offset"))
        length = int(row.get("length"))
    except (TypeError, ValueError) as exc:
        raise ValueError("Common Crawl index offset/length must be integers") from exc
    if offset < 0 or length <= 0:
        raise ValueError("Common Crawl index offset/length are invalid")

    warc_locator = _clean_https(
        capture.get("warc_range_locator"),
        field="commoncrawl.warc_range_locator",
        required_host="data.commoncrawl.org",
    )
    if warc_locator != f"https://data.commoncrawl.org/{filename}":
        raise ValueError("Common Crawl WARC locator does not match index filename")

    compressed = _retained_bytes(root, capture.get("warc_range"), field="commoncrawl.warc_range")
    if len(compressed) != length:
        raise ValueError("retained Common Crawl range length does not match index length")

    warc_headers, _, _, body = _parse_warc_record(compressed)
    if warc_headers.get("warc-target-uri") != upstream_locator:
        raise ValueError("WARC-Target-URI does not match primary upstream locator")
    warc_date = _utc(warc_headers.get("warc-date"), field="warc.WARC-Date")
    if warc_date != capture_at:
        raise ValueError("WARC-Date does not equal Common Crawl index timestamp")
    if warc_date > decision:
        raise ValueError("WARC capture occurred after decision_at")

    payload_digest = warc_headers.get("warc-payload-digest")
    row_digest = row.get("digest")
    payload_match = WARC_SHA1_BASE32_RE.fullmatch(payload_digest) if isinstance(payload_digest, str) else None
    if payload_match is None:
        raise ValueError("WARC-Payload-Digest missing or unsupported")
    if not isinstance(row_digest, str) or not SHA1_BASE32_RE.fullmatch(row_digest):
        raise ValueError("Common Crawl index digest missing or unsupported")
    if row_digest != payload_match.group(1):
        raise ValueError("Common Crawl index digest does not match WARC-Payload-Digest")

    if not isinstance(document_sha256, str) or not SHA256_RE.fullmatch(document_sha256):
        raise ValueError("document_sha256 must be lowercase SHA-256")
    if hashlib.sha256(document_bytes).hexdigest() != document_sha256:
        raise ValueError("retained primary document SHA-256 mismatch")
    if hashlib.sha256(body).hexdigest() != document_sha256 or body != document_bytes:
        raise ValueError("retained primary document bytes do not equal archived WARC HTTP entity")

    record_id = warc_headers.get("warc-record-id")
    if not isinstance(record_id, str) or not record_id.startswith("<urn:uuid:") or not record_id.endswith(">"):
        raise ValueError("WARC-Record-ID is missing or malformed")

    return {
        "schema": "two_x_commoncrawl_historical_capture_result.v1",
        "status": "BOUND",
        "artifact_id": CONTRACT_ARTIFACT_ID,
        "index_collection": collection,
        "capture_at": warc_date.isoformat().replace("+00:00", "Z"),
        "target_uri": upstream_locator,
        "warc_record_id": record_id,
        "warc_filename": filename,
        "warc_offset": offset,
        "warc_length": length,
        "warc_payload_digest": payload_digest,
        "document_sha256": document_sha256,
        "authority": "HISTORICAL_AVAILABILITY_EVIDENCE_ONLY_NO_OUTCOME_OR_PREDICTION_AUTHORITY",
    }