import hashlib
import json
from datetime import datetime, timezone

import pytest

from big_move_source_authenticity import validate_record_authenticity
from c101h_binance_direct_acquisition import (
    _validate_provider_body,
    canonical_receipt as canonical_c101h_receipt,
    freeze_binance_c101h_request,
)
from trusted_remote_acquisition import FetchResult


UTC = timezone.utc
ARCHIVE_OBJECT_PATH = (
    "data/spot/monthly/klines/BTCUSDT/1h/BTCUSDT-1h-2024-01.zip"
)
ARCHIVE_URL = "https://data.binance.vision/" + ARCHIVE_OBJECT_PATH


def _retain(tmp_path, name: str, raw: bytes) -> dict[str, str]:
    (tmp_path / name).write_bytes(raw)
    return {
        "artifact_relpath": name,
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def _local_only_binance_record(tmp_path) -> dict:
    archive_raw = b"PK\x03\x04locally fabricated bytes that were never acquired from Binance"
    archive_sha = hashlib.sha256(archive_raw).hexdigest()
    checksum_raw = f"{archive_sha}  BTCUSDT-1h-2024-01.zip\n".encode("utf-8")

    archive_ref = _retain(tmp_path, "BTCUSDT-1h-2024-01.zip", archive_raw)
    checksum_ref = _retain(tmp_path, "BTCUSDT-1h-2024-01.zip.CHECKSUM", checksum_raw)

    proof = {
        "schema": "binance_public_archive_proof.v1",
        "upstream_locator": ARCHIVE_URL,
        "archive_relpath": archive_ref["artifact_relpath"],
        "archive_sha256": archive_ref["sha256"],
        "checksum_relpath": checksum_ref["artifact_relpath"],
        "checksum_sha256": checksum_ref["sha256"],
        "event_time_max": "2024-01-31T23:59:59Z",
    }
    proof_raw = json.dumps(proof, sort_keys=True, separators=(",", ":")).encode("utf-8")
    proof_ref = _retain(tmp_path, "binance-proof.json", proof_raw)
    return {
        "source_id": "BINANCE_PUBLIC_DATA_SPOT_RAW",
        "source_proof": proof_ref,
    }


def _canonical_but_unattested_c101h_receipt(archive_raw: bytes) -> dict:
    request = freeze_binance_c101h_request(
        source_kind="BINANCE_C101H_ARCHIVE",
        object_path=ARCHIVE_OBJECT_PATH,
    )
    result = FetchResult(
        status=200,
        headers={"content-type": "application/zip"},
        body=archive_raw,
        started_at="2024-02-01T00:00:00Z",
        completed_at="2024-02-01T00:00:01Z",
    )
    metadata = _validate_provider_body(request, archive_raw)
    github_context = {
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
    }
    return canonical_c101h_receipt(
        request,
        result,
        github_context=github_context,
        provider_metadata=metadata,
    )


def test_canonical_binance_archive_rejects_local_hash_only_origin(tmp_path):
    record = _local_only_binance_record(tmp_path)

    with pytest.raises(ValueError, match="trusted acquisition|receipt|provider evidence"):
        validate_record_authenticity(
            record,
            artifact_root=tmp_path,
            decision_at=datetime(2024, 2, 2, tzinfo=UTC),
            field="quote_volume",
        )


def test_canonical_binance_archive_rejects_canonical_but_unattested_receipt(tmp_path):
    record = _local_only_binance_record(tmp_path)
    proof_ref = record["source_proof"]
    proof_path = tmp_path / proof_ref["artifact_relpath"]
    proof = json.loads(proof_path.read_text(encoding="utf-8"))
    archive_raw = (tmp_path / proof["archive_relpath"]).read_bytes()

    proof["trusted_acquisition_receipt"] = _canonical_but_unattested_c101h_receipt(
        archive_raw
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
