"""Adversarial provenance regressions for retained derived-input JSON semantics.

A SHA-256 authenticates exact bytes, but those bytes must still have one unambiguous
scientific meaning.  Python's default JSON parser accepts duplicate object keys and
non-standard NaN/Infinity constants.  Retained derivation-input envelopes therefore
must fail closed before source-native authenticity checks consume them.
"""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import pytest

from big_move_source_authenticity import validate_record_authenticity

DECISION = datetime(2024, 1, 1, tzinfo=timezone.utc)


def _write(root: Path, name: str, raw: bytes) -> dict[str, str]:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    return {"artifact_relpath": name, "sha256": hashlib.sha256(raw).hexdigest()}


def _write_json(root: Path, name: str, value) -> dict[str, str]:
    return _write(
        root,
        name,
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8"),
    )


def _binance_input(root: Path) -> dict:
    archive_raw = b"provider archive fixture\n"
    archive_ref = _write(root, "binance/archive.zip", archive_raw)
    checksum_raw = f"{archive_ref['sha256']}  archive.zip\n".encode("utf-8")
    checksum_ref = _write(root, "binance/archive.zip.CHECKSUM", checksum_raw)
    proof = {
        "schema": "binance_public_archive_proof.v1",
        "upstream_locator": "https://data.binance.vision/data/spot/monthly/klines/BTCUSDT/1h/BTCUSDT-1h-2020-01.zip",
        "archive_relpath": archive_ref["artifact_relpath"],
        "archive_sha256": archive_ref["sha256"],
        "checksum_relpath": checksum_ref["artifact_relpath"],
        "checksum_sha256": checksum_ref["sha256"],
        "event_time_max": "2020-01-31T23:59:59Z",
    }
    proof_ref = _write_json(root, "binance/proof.json", proof)
    return {
        "source_id": "BINANCE_PUBLIC_DATA_SPOT_RAW",
        "source_version": "v1",
        "observed_at": "2020-01-31T23:00:00Z",
        "available_at": "2020-02-01T00:00:00Z",
        "value": 1,
        "source_proof": proof_ref,
    }


def _derived(input_ref: dict[str, str]) -> dict:
    return {
        "source_id": "DERIVED_PRE_CUTOFF_VENUE_BARS_V1",
        "source_version": "v1",
        "observed_at": "2020-01-31T23:00:00Z",
        "available_at": "2020-02-01T00:00:00Z",
        "value": 1,
        "derivation": {
            "transform_id": "DERIVED_PRE_CUTOFF_VENUE_BARS_V1",
            "transform_version": "1",
            "parameters": {},
            "inputs": [input_ref],
        },
    }


def test_retained_derived_input_duplicate_json_key_fails_closed(tmp_path):
    artifact = _binance_input(tmp_path)
    canonical = json.dumps(artifact, sort_keys=True, separators=(",", ":"))
    raw = (canonical[:-1] + ',"source_id":"BINANCE_PUBLIC_DATA_SPOT_RAW"}').encode("utf-8")
    input_ref = _write(tmp_path, "derived/input-duplicate-key.json", raw)

    with pytest.raises(ValueError, match="duplicate JSON object key"):
        validate_record_authenticity(
            _derived(input_ref),
            artifact_root=tmp_path,
            decision_at=DECISION,
            field="venue_bars",
        )


def test_retained_derived_input_nonstandard_numeric_constant_fails_closed(tmp_path):
    artifact = _binance_input(tmp_path)
    canonical = json.dumps(artifact, sort_keys=True, separators=(",", ":"))
    raw = (canonical[:-1] + ',"ambiguous_numeric":NaN}').encode("utf-8")
    input_ref = _write(tmp_path, "derived/input-nan.json", raw)

    with pytest.raises(ValueError, match="non-standard JSON numeric constant"):
        validate_record_authenticity(
            _derived(input_ref),
            artifact_root=tmp_path,
            decision_at=DECISION,
            field="venue_bars",
        )
