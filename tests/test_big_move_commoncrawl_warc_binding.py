import base64
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path

import pytest

from big_move_commoncrawl_warc_binding import (
    CONTRACT_ARTIFACT_ID,
    CONTRACT_GIT_BLOB_SHA,
    load_commoncrawl_contract,
    validate_commoncrawl_historical_capture,
)


def _write(root: Path, name: str, raw: bytes):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    return {"artifact_relpath": name, "sha256": hashlib.sha256(raw).hexdigest()}


def _sha1_base32(raw: bytes) -> str:
    return base64.b32encode(hashlib.sha1(raw, usedforsecurity=False).digest()).decode("ascii").rstrip("=")


def _fixture(
    root: Path,
    *,
    locator: str = "https://example.org/original-document",
    capture_timestamp: str = "20200102030405",
    document: bytes = b"Bitcoin is peer-to-peer electronic cash.",
    content_encoding: str = "",
    duplicate_index_row: bool = False,
    row_digest_override: str | None = None,
    warc_target_override: str | None = None,
):
    http_headers = [b"HTTP/1.1 200 OK", b"Content-Type: text/plain"]
    if content_encoding:
        http_headers.append(f"Content-Encoding: {content_encoding}".encode("ascii"))
    http_block = b"\r\n".join(http_headers) + b"\r\n\r\n" + document
    payload_sha1_base32 = _sha1_base32(document)
    payload_digest = "sha1:" + payload_sha1_base32
    block_digest = "sha1:" + _sha1_base32(http_block)
    warc_date = datetime.strptime(capture_timestamp, "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
    warc_date_text = warc_date.isoformat().replace("+00:00", "Z")
    target = warc_target_override or locator
    warc_headers = [
        b"WARC/1.0",
        b"WARC-Type: response",
        b"WARC-Record-ID: <urn:uuid:00000000-0000-0000-0000-000000000001>",
        f"WARC-Date: {warc_date_text}".encode("ascii"),
        f"WARC-Target-URI: {target}".encode("utf-8"),
        f"WARC-Payload-Digest: {payload_digest}".encode("ascii"),
        f"WARC-Block-Digest: {block_digest}".encode("ascii"),
        b"Content-Type: application/http; msgtype=response",
        f"Content-Length: {len(http_block)}".encode("ascii"),
    ]
    warc = b"\r\n".join(warc_headers) + b"\r\n\r\n" + http_block
    compressed = gzip.compress(warc, mtime=0)

    collection = "CC-MAIN-2020-05"
    filename = f"crawl-data/{collection}/segments/1579250589560.16/warc/CC-MAIN-test.warc.gz"
    row = {
        "url": locator,
        "timestamp": capture_timestamp,
        "status": "200",
        # Common Crawl CDX JSON uses bare Base32 SHA-1; the WARC header uses
        # WARC-Payload-Digest: sha1:<Base32>. Keep the real provider formats distinct.
        "digest": row_digest_override or payload_sha1_base32,
        "filename": filename,
        "offset": "12345",
        "length": str(len(compressed)),
    }
    rows = [row]
    if duplicate_index_row:
        rows.append(dict(row))
    index_raw = b"".join(json.dumps(item, sort_keys=True).encode() + b"\n" for item in rows)
    capture = {
        "schema": "commoncrawl_warc_capture_proof.v1",
        "index_collection": collection,
        "index_query_locator": f"https://index.commoncrawl.org/{collection}-index?url=example.org%2Foriginal-document&output=json",
        "index_response": _write(root, "cc/index.jsonl", index_raw),
        "warc_range_locator": f"https://data.commoncrawl.org/{filename}",
        "warc_range": _write(root, "cc/range.warc.gz", compressed),
    }
    return capture, document, hashlib.sha256(document).hexdigest()


def _validate(root: Path, capture, document, digest, *, decision="2024-01-01T00:00:00Z", locator="https://example.org/original-document"):
    return validate_commoncrawl_historical_capture(
        capture,
        upstream_locator=locator,
        decision_at=decision,
        document_bytes=document,
        document_sha256=digest,
        artifact_root=root,
    )


def test_commoncrawl_contract_is_git_blob_pinned():
    contract = load_commoncrawl_contract()
    assert contract["artifact_id"] == CONTRACT_ARTIFACT_ID
    assert len(CONTRACT_GIT_BLOB_SHA) == 40


def test_valid_capture_binds_exact_primary_document_bytes(tmp_path):
    capture, document, digest = _fixture(tmp_path)
    result = _validate(tmp_path, capture, document, digest)
    assert result["status"] == "BOUND"
    assert result["document_sha256"] == digest
    assert result["capture_at"] == "2020-01-02T03:04:05Z"
    assert result["authority"] == "HISTORICAL_AVAILABILITY_EVIDENCE_ONLY_NO_OUTCOME_OR_PREDICTION_AUTHORITY"


def test_post_decision_capture_cannot_be_backdated(tmp_path):
    capture, document, digest = _fixture(tmp_path, capture_timestamp="20250102030405")
    with pytest.raises(ValueError, match="after decision_at"):
        _validate(tmp_path, capture, document, digest, decision="2024-01-01T00:00:00Z")


def test_index_digest_must_match_warc_payload_digest(tmp_path):
    capture, document, digest = _fixture(tmp_path, row_digest_override="A" * 32)
    with pytest.raises(ValueError, match="index digest"):
        _validate(tmp_path, capture, document, digest)


def test_index_digest_must_use_real_commoncrawl_bare_base32_format(tmp_path):
    capture, document, digest = _fixture(tmp_path, row_digest_override="sha1:" + "A" * 32)
    with pytest.raises(ValueError, match="index digest missing or unsupported"):
        _validate(tmp_path, capture, document, digest)


def test_warc_target_uri_must_match_primary_locator(tmp_path):
    capture, document, digest = _fixture(tmp_path, warc_target_override="https://example.org/other")
    with pytest.raises(ValueError, match="WARC-Target-URI"):
        _validate(tmp_path, capture, document, digest)


def test_archived_http_entity_must_equal_retained_primary_document(tmp_path):
    capture, document, digest = _fixture(tmp_path)
    forged = b"different bytes"
    forged_digest = hashlib.sha256(forged).hexdigest()
    with pytest.raises(ValueError, match="do not equal archived"):
        _validate(tmp_path, capture, forged, forged_digest)


def test_non_identity_http_content_encoding_fails_closed(tmp_path):
    capture, document, digest = _fixture(tmp_path, content_encoding="gzip")
    with pytest.raises(ValueError, match="unsupported content-encoding"):
        _validate(tmp_path, capture, document, digest)


def test_ambiguous_matching_index_rows_fail_closed(tmp_path):
    capture, document, digest = _fixture(tmp_path, duplicate_index_row=True)
    with pytest.raises(ValueError, match="exactly one matching"):
        _validate(tmp_path, capture, document, digest)


def test_retained_compressed_range_length_is_bound_to_index(tmp_path):
    capture, document, digest = _fixture(tmp_path)
    index_path = tmp_path / capture["index_response"]["artifact_relpath"]
    row = json.loads(index_path.read_text().strip())
    row["length"] = str(int(row["length"]) + 1)
    raw = json.dumps(row, sort_keys=True).encode() + b"\n"
    index_path.write_bytes(raw)
    capture["index_response"] = {
        "artifact_relpath": capture["index_response"]["artifact_relpath"],
        "sha256": hashlib.sha256(raw).hexdigest(),
    }
    with pytest.raises(ValueError, match="range length"):
        _validate(tmp_path, capture, document, digest)
