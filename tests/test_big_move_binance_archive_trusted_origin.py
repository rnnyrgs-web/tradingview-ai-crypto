import hashlib
import json
from datetime import datetime, timezone

import pytest

from big_move_source_authenticity import validate_record_authenticity


UTC = timezone.utc


def _retain(tmp_path, name: str, raw: bytes) -> dict[str, str]:
    (tmp_path / name).write_bytes(raw)
    return {
        "artifact_relpath": name,
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def _local_only_binance_record(tmp_path) -> dict:
    # Deliberately not provider-authenticated. Current canonical validation proves only
    # that these locally retained bytes are self-consistent with caller-declared hashes.
    archive_raw = b"locally fabricated bytes that were never acquired from Binance"
    archive_sha = hashlib.sha256(archive_raw).hexdigest()
    checksum_raw = f"{archive_sha}  BTCUSDT-1d-2024-01.zip\n".encode("utf-8")

    archive_ref = _retain(tmp_path, "BTCUSDT-1d-2024-01.zip", archive_raw)
    checksum_ref = _retain(tmp_path, "BTCUSDT-1d-2024-01.zip.CHECKSUM", checksum_raw)

    proof = {
        "schema": "binance_public_archive_proof.v1",
        "upstream_locator": (
            "https://data.binance.vision/data/spot/monthly/klines/"
            "BTCUSDT/1d/BTCUSDT-1d-2024-01.zip"
        ),
        "archive_relpath": archive_ref["artifact_relpath"],
        "archive_sha256": archive_ref["sha256"],
        "checksum_relpath": checksum_ref["artifact_relpath"],
        "checksum_sha256": checksum_ref["sha256"],
        # This clock is caller-authored and therefore must not establish historical
        # availability or event-time bounds without provider-native evidence.
        "event_time_max": "2024-01-31T23:59:59Z",
    }
    proof_raw = json.dumps(proof, sort_keys=True, separators=(",", ":")).encode("utf-8")
    proof_ref = _retain(tmp_path, "binance-proof.json", proof_raw)
    return {
        "source_id": "BINANCE_PUBLIC_DATA_SPOT_RAW",
        "source_proof": proof_ref,
    }


def _self_authored_receipt(*, source_url: str, response_sha256: str, byte_count: int) -> dict:
    """Build an internally consistent receipt-shaped object with no external attestation."""
    receipt = {
        "schema": "trusted_remote_acquisition_receipt.v1",
        "source_contract_id": "PIT-TRUSTED-REMOTE-ACQUISITION-001-v1",
        "source_kind": "BINANCE_C101H_ARCHIVE",
        "request": {
            "method": "GET",
            "url": source_url,
            "range_header": None,
        },
        "response": {
            "status": 200,
            "sha256": response_sha256,
            "byte_count": byte_count,
            "content_type": "application/zip",
            "etag": None,
            "last_modified": None,
            "content_range": None,
        },
        "acquisition": {
            "started_at": "2024-02-01T00:00:00Z",
            "completed_at": "2024-02-01T00:00:01Z",
            "repository": "rnnyrgs-web/tradingview-ai-crypto",
            "git_sha": "a" * 40,
            "git_ref": "refs/heads/main",
            "workflow_ref": (
                "rnnyrgs-web/tradingview-ai-crypto/.github/workflows/"
                "pit-trusted-remote-acquisition.yml@refs/heads/main"
            ),
            "run_id": 123456,
            "run_attempt": 1,
            "event_name": "workflow_dispatch",
        },
        "chain": {"predecessor_receipt_sha256": None},
        "authority": "PROVIDER_BYTES_AUTHENTICATED_ONLY_AFTER_GITHUB_ATTESTATION_VERIFICATION",
    }
    canonical = json.dumps(receipt, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    receipt["receipt_sha256"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return receipt


def test_canonical_binance_archive_rejects_local_hash_only_origin(tmp_path):
    """A plausible Binance URL plus local hashes must not become trusted PIT evidence."""
    record = _local_only_binance_record(tmp_path)

    with pytest.raises(ValueError, match="trusted acquisition|receipt|provider evidence"):
        validate_record_authenticity(
            record,
            artifact_root=tmp_path,
            decision_at=datetime(2024, 2, 2, tzinfo=UTC),
            field="quote_volume",
        )


def test_canonical_binance_archive_rejects_self_authored_receipt_without_external_verification(tmp_path):
    """Receipt-shaped JSON is still caller data until a trusted boundary verifies it."""
    record = _local_only_binance_record(tmp_path)
    proof_ref = record["source_proof"]
    proof_path = tmp_path / proof_ref["artifact_relpath"]
    proof = json.loads(proof_path.read_text(encoding="utf-8"))
    archive_path = tmp_path / proof["archive_relpath"]

    proof["trusted_acquisition_receipt"] = _self_authored_receipt(
        source_url=proof["upstream_locator"],
        response_sha256=proof["archive_sha256"],
        byte_count=len(archive_path.read_bytes()),
    )
    raw = json.dumps(proof, sort_keys=True, separators=(",", ":")).encode("utf-8")
    proof_path.write_bytes(raw)
    proof_ref["sha256"] = hashlib.sha256(raw).hexdigest()

    with pytest.raises(ValueError, match="trusted acquisition|receipt|attestation|provider evidence"):
        validate_record_authenticity(
            record,
            artifact_root=tmp_path,
            decision_at=datetime(2024, 2, 2, tzinfo=UTC),
            field="quote_volume",
        )
