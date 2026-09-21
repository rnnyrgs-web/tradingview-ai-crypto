import hashlib
import io
import json
from pathlib import Path
import zipfile

import pytest

from big_move_binance_price_binding import (
    CONTRACT_ARTIFACT_ID,
    CONTRACT_GIT_BLOB_SHA,
    load_price_binding_contract,
    validate_binance_decision_price,
)


def _write(root: Path, name: str, raw: bytes):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    return {"artifact_relpath": name, "sha256": hashlib.sha256(raw).hexdigest()}


def _json(root: Path, name: str, value):
    return _write(root, name, json.dumps(value, sort_keys=True, separators=(",", ":")).encode())


def _ms(iso: str) -> int:
    from datetime import datetime

    return int(datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp() * 1000)


def _row(day: str, close: str):
    open_time = _ms(f"{day}T00:00:00Z")
    close_time = _ms(f"{day}T23:59:59.999Z")
    return [
        str(open_time),
        "100",
        "120",
        "90",
        close,
        "10",
        str(close_time),
        "1100",
        "100",
        "4",
        "440",
        "0",
    ]


def _archive(rows):
    import csv

    text = io.StringIO()
    writer = csv.writer(text, lineterminator="\n")
    writer.writerows(rows)
    raw_csv = text.getvalue().encode()
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("BTCUSDT-1d-2024-01.csv", raw_csv)
    return out.getvalue()


def _fixture(root: Path, *, rows=None, price="111", observed_at="2024-01-02T23:59:59.999000Z"):
    archive_name = "BTCUSDT-1d-2024-01.zip"
    archive_raw = _archive(rows or [_row("2024-01-01", "105"), _row("2024-01-02", "111")])
    archive_ref = _write(root, f"raw/{archive_name}", archive_raw)
    checksum_raw = f"{archive_ref['sha256']}  {archive_name}\n".encode()
    checksum_ref = _write(root, f"raw/{archive_name}.CHECKSUM", checksum_raw)
    proof = {
        "schema": "binance_public_archive_proof.v1",
        "source_id": "BINANCE_PUBLIC_DATA_SPOT_RAW",
        "upstream_locator": f"https://data.binance.vision/data/spot/monthly/klines/BTCUSDT/1d/{archive_name}",
        "archive_relpath": archive_ref["artifact_relpath"],
        "archive_sha256": archive_ref["sha256"],
        "checksum_relpath": checksum_ref["artifact_relpath"],
        "checksum_sha256": checksum_ref["sha256"],
        "event_time_max": "2024-01-02T23:59:59.999000Z",
    }
    proof_ref = _json(root, "proof.json", proof)
    record = {
        "source_id": "BINANCE_PUBLIC_DATA_SPOT_RAW",
        "source_version": "v1",
        "observed_at": observed_at,
        "available_at": "2024-01-02T23:59:59.999000Z",
        "value": price,
        "source_proof": proof_ref,
    }
    return record, proof_ref


def test_price_binding_contract_is_git_blob_pinned():
    contract = load_price_binding_contract()
    assert contract["artifact_id"] == CONTRACT_ARTIFACT_ID
    assert len(CONTRACT_GIT_BLOB_SHA) == 40


def test_valid_price_is_reproduced_from_exact_retained_archive(tmp_path):
    record, _ = _fixture(tmp_path)
    result = validate_binance_decision_price(
        record,
        venue_symbol="BTCUSDT",
        decision_at="2024-01-03T00:00:00Z",
        artifact_root=tmp_path,
    )
    assert result["status"] == "BOUND"
    assert result["price"] == "111"
    assert result["observed_at"] == "2024-01-02T23:59:59.999000Z"
    assert result["authority"] == "EVIDENCE_ONLY_NO_OUTCOME_OR_FORECAST_AUTHORITY"


def test_forged_normalized_price_is_rejected(tmp_path):
    record, _ = _fixture(tmp_path, price="0.01")
    with pytest.raises(ValueError, match="does not match latest completed retained Binance close"):
        validate_binance_decision_price(
            record,
            venue_symbol="BTCUSDT",
            decision_at="2024-01-03T00:00:00Z",
            artifact_root=tmp_path,
        )


def test_forged_observation_time_is_rejected(tmp_path):
    record, _ = _fixture(tmp_path, observed_at="2024-01-02T00:00:00Z")
    with pytest.raises(ValueError, match="observed_at does not match"):
        validate_binance_decision_price(
            record,
            venue_symbol="BTCUSDT",
            decision_at="2024-01-03T00:00:00Z",
            artifact_root=tmp_path,
        )


def test_post_decision_archive_rows_cannot_be_hidden_by_claimed_event_max(tmp_path):
    record, _ = _fixture(
        tmp_path,
        rows=[
            _row("2024-01-01", "105"),
            _row("2024-01-02", "111"),
            _row("2024-01-03", "115"),
        ],
    )
    with pytest.raises(ValueError, match="post-decision or incomplete bar"):
        validate_binance_decision_price(
            record,
            venue_symbol="BTCUSDT",
            decision_at="2024-01-03T00:00:00Z",
            artifact_root=tmp_path,
        )


def test_locator_must_bind_exact_symbol_and_interval(tmp_path):
    record, proof_ref = _fixture(tmp_path)
    proof_path = tmp_path / proof_ref["artifact_relpath"]
    proof = json.loads(proof_path.read_text())
    proof["upstream_locator"] = proof["upstream_locator"].replace("BTCUSDT/1d", "ETHUSDT/1d")
    raw = json.dumps(proof, sort_keys=True, separators=(",", ":")).encode()
    proof_path.write_bytes(raw)
    record["source_proof"] = {
        "artifact_relpath": proof_ref["artifact_relpath"],
        "sha256": hashlib.sha256(raw).hexdigest(),
    }
    with pytest.raises(ValueError, match="does not bind symbol and 1d kline interval"):
        validate_binance_decision_price(
            record,
            venue_symbol="BTCUSDT",
            decision_at="2024-01-03T00:00:00Z",
            artifact_root=tmp_path,
        )
