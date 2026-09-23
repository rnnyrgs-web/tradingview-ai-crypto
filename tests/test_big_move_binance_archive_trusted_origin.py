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
