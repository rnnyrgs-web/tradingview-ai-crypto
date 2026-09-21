import base64
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path

import pytest

import big_move_commoncrawl_trusted_origin as trusted_origin
from big_move_primary_historical_availability import (
    validate_primary_document_historical_availability,
)
from trusted_remote_acquisition import (
    freeze_commoncrawl_index_request,
    freeze_commoncrawl_warc_request,
)


def _write(root: Path, name: str, raw: bytes):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    return {"artifact_relpath": name, "sha256": hashlib.sha256(raw).hexdigest()}


def _json(root: Path, name: str, value):
    return _write(root, name, json.dumps(value, sort_keys=True, separators=(",", ":")).encode())


def _sha1_base32(raw: bytes) -> str:
    return base64.b32encode(hashlib.sha1(raw, usedforsecurity=False).digest()).decode("ascii").rstrip("=")


def _record(root: Path, *, capture_timestamp="20200102030405", document=b"Bitcoin primary document"):
    locator = "https://example.org/original-document"
    http_block = b"HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\n\r\n" + document
    payload_sha1_base32 = _sha1_base32(document)
    payload_digest = "sha1:" + payload_sha1_base32
    block_digest = "sha1:" + _sha1_base32(http_block)
    warc_date = datetime.strptime(capture_timestamp, "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
    warc_date_text = warc_date.isoformat().replace("+00:00", "Z")
    headers = [
        b"WARC/1.0",
        b"WARC-Type: response",
        b"WARC-Record-ID: <urn:uuid:00000000-0000-0000-0000-000000000002>",
        f"WARC-Date: {warc_date_text}".encode(),
        f"WARC-Target-URI: {locator}".encode(),
        f"WARC-Payload-Digest: {payload_digest}".encode(),
        f"WARC-Block-Digest: {block_digest}".encode(),
        b"Content-Type: application/http; msgtype=response",
        f"Content-Length: {len(http_block)}".encode(),
    ]
    compressed = gzip.compress(b"\r\n".join(headers) + b"\r\n\r\n" + http_block, mtime=0)
    collection = "CC-MAIN-2020-05"
    filename = f"crawl-data/{collection}/segments/1579250589560.16/warc/CC-MAIN-test.warc.gz"
    row = {
        "url": locator,
        "timestamp": capture_timestamp,
        "status": "200",
        "digest": payload_sha1_base32,
        "filename": filename,
        "offset": "42",
        "length": str(len(compressed)),
    }
    index_request = freeze_commoncrawl_index_request(collection=collection, target_url=locator)
    warc_request = freeze_commoncrawl_warc_request(
        collection=collection,
        filename=filename,
        offset=42,
        length=len(compressed),
    )
    capture = {
        "schema": "commoncrawl_warc_capture_proof.v1",
        "index_collection": collection,
        "index_query_locator": index_request.url,
        "index_response": _write(root, "cc/index.jsonl", json.dumps(row, sort_keys=True).encode() + b"\n"),
        "selected_index_row": row,
        "index_acquisition_bundle": {"artifact_relpath": "attested/index/trusted-acquisition.tar"},
        "warc_range_locator": warc_request.url,
        "warc_range": _write(root, "cc/range.warc.gz", compressed),
        "warc_acquisition_bundle": {"artifact_relpath": "attested/warc/trusted-acquisition.tar"},
    }
    capture_ref = _json(root, "cc/capture.json", capture)
    document_ref = _write(root, "primary/document.txt", document)
    proof = {
        "schema": "primary_document_proof.v1",
        "source_id": "PRIMARY_CONTRACT_OR_GENESIS_DOC",
        "upstream_locator": locator,
        "published_at": "2020-01-01T00:00:00Z",
        "effective_at": "2020-01-01T00:00:00Z",
        "document_relpath": document_ref["artifact_relpath"],
        "document_sha256": document_ref["sha256"],
        "media_type": "text/plain",
        "claim_value": "Bitcoin",
        "historical_capture": capture_ref,
    }
    proof_ref = _json(root, "primary/proof.json", proof)
    record = {
        "source_id": "PRIMARY_CONTRACT_OR_GENESIS_DOC",
        "source_version": "v1",
        "observed_at": "2020-01-01T00:00:00Z",
        "available_at": "2020-01-01T00:00:00Z",
        "value": "Bitcoin",
        "source_proof": proof_ref,
    }
    return record, proof_ref


def _install_fake_attested_provider(monkeypatch, root: Path):
    def fake_verify(bundle_path, *, expected_source_kind):
        bundle_name = str(bundle_path)
        rows = [json.loads(line) for line in (root / "cc/index.jsonl").read_text().splitlines() if line.strip()]
        capture = json.loads((root / "cc/capture.json").read_text())
        selected = capture["selected_index_row"]
        collection = selected["filename"].split("/")[1]
        if expected_source_kind == "COMMONCRAWL_INDEX":
            request = freeze_commoncrawl_index_request(collection=collection, target_url=selected["url"])
            raw = (root / "cc/index.jsonl").read_bytes()
            receipt_sha = "a" * 64
        elif expected_source_kind == "COMMONCRAWL_WARC_RANGE":
            request = freeze_commoncrawl_warc_request(
                collection=collection,
                filename=selected["filename"],
                offset=int(selected["offset"]),
                length=int(selected["length"]),
            )
            raw = (root / "cc/range.warc.gz").read_bytes()
            receipt_sha = "b" * 64
        else:
            raise AssertionError(expected_source_kind)
        assert rows
        assert bundle_name.endswith("trusted-acquisition.tar")
        return {
            "request": {
                "method": "GET",
                "url": request.url,
                "range_header": request.range_header,
            },
            "receipt_sha256": receipt_sha,
        }, raw

    monkeypatch.setattr(trusted_origin, "verify_attested_acquisition_bundle", fake_verify)


def test_primary_document_requires_exact_predecision_archive_binding(tmp_path, monkeypatch):
    record, _ = _record(tmp_path)
    _install_fake_attested_provider(monkeypatch, tmp_path)
    result = validate_primary_document_historical_availability(
        record,
        decision_at="2024-01-01T00:00:00Z",
        artifact_root=tmp_path,
    )
    assert result["status"] == "BOUND"
    assert result["capture_at"] == "2020-01-02T03:04:05Z"
    assert len(result["selected_index_row_sha256"]) == 64
    assert result["provider_origin"] == "ATTESTED_TRUSTED_REMOTE_ACQUISITION"
    assert result["index_receipt_sha256"] == "a" * 64
    assert result["warc_receipt_sha256"] == "b" * 64
    assert result["authority"] == "HISTORICAL_AVAILABILITY_EVIDENCE_ONLY_NO_OUTCOME_OR_PREDICTION_AUTHORITY"


def test_caller_authored_old_publication_time_without_archive_capture_fails(tmp_path):
    record, proof_ref = _record(tmp_path)
    proof_path = tmp_path / proof_ref["artifact_relpath"]
    proof = json.loads(proof_path.read_text())
    proof.pop("historical_capture")
    raw = json.dumps(proof, sort_keys=True, separators=(",", ":")).encode()
    proof_path.write_bytes(raw)
    record["source_proof"] = {
        "artifact_relpath": proof_ref["artifact_relpath"],
        "sha256": hashlib.sha256(raw).hexdigest(),
    }
    with pytest.raises(ValueError, match="historical_capture"):
        validate_primary_document_historical_availability(
            record,
            decision_at="2024-01-01T00:00:00Z",
            artifact_root=tmp_path,
        )


def test_missing_trusted_acquisition_bundle_fails_closed(tmp_path):
    record, proof_ref = _record(tmp_path)
    proof = json.loads((tmp_path / proof_ref["artifact_relpath"]).read_text())
    capture_ref = proof["historical_capture"]
    capture_path = tmp_path / capture_ref["artifact_relpath"]
    capture = json.loads(capture_path.read_text())
    capture.pop("index_acquisition_bundle")
    raw_capture = json.dumps(capture, sort_keys=True, separators=(",", ":")).encode()
    capture_path.write_bytes(raw_capture)
    proof["historical_capture"] = {
        "artifact_relpath": capture_ref["artifact_relpath"],
        "sha256": hashlib.sha256(raw_capture).hexdigest(),
    }
    raw_proof = json.dumps(proof, sort_keys=True, separators=(",", ":")).encode()
    proof_path = tmp_path / proof_ref["artifact_relpath"]
    proof_path.write_bytes(raw_proof)
    record["source_proof"] = {
        "artifact_relpath": proof_ref["artifact_relpath"],
        "sha256": hashlib.sha256(raw_proof).hexdigest(),
    }
    with pytest.raises(ValueError, match="trusted acquisition bundle reference missing"):
        validate_primary_document_historical_availability(
            record,
            decision_at="2024-01-01T00:00:00Z",
            artifact_root=tmp_path,
        )


def test_postdecision_archive_capture_fails_even_with_old_declared_publication(tmp_path, monkeypatch):
    record, _ = _record(tmp_path, capture_timestamp="20250102030405")
    _install_fake_attested_provider(monkeypatch, tmp_path)
    with pytest.raises(ValueError, match="at or before decision_at"):
        validate_primary_document_historical_availability(
            record,
            decision_at="2024-01-01T00:00:00Z",
            artifact_root=tmp_path,
        )
