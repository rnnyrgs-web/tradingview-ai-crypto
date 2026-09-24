from datetime import date, datetime, timedelta, timezone
import hashlib
import io
import json
import zipfile

import pytest

from big_move_derived_output_binding import (
    BOUND_ROWS_SCHEMA,
    validate_snapshot_derived_output_bindings,
)
from big_move_feature_derivations import (
    REGIME_TRANSFORM,
    RETURN_TRANSFORM,
    VOLATILITY_TRANSFORM,
    compute_btc_regime,
    compute_return_30d,
    compute_volatility_30d,
)

UTC = timezone.utc
BINANCE = "BINANCE_PUBLIC_DATA_SPOT_RAW"
DECISION = "2024-04-01T00:00:00Z"


def _json_bytes(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def _write_bytes(root, name, raw):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    return {"artifact_relpath": name, "sha256": hashlib.sha256(raw).hexdigest()}


def _write_json(root, name, value):
    return _write_bytes(root, name, _json_bytes(value))


def _transform_params(spec):
    return {
        key: value
        for key, value in spec.items()
        if key not in {"transform_id", "transform_version", "metric"}
    }


def _daily_rows(decision, *, days, start=100.0, step=1.0):
    decision_date = date.fromisoformat(decision[:10])
    rows = []
    for offset in range(days, 0, -1):
        d = decision_date - timedelta(days=offset)
        index = days - offset
        close = start + step * index
        rows.append({
            "date": d.isoformat(),
            "close": f"{close:.8f}",
            "quote_volume_usd": "50000000.0",
        })
    return rows


def _archive_bytes(rows):
    buffer = io.BytesIO()
    csv_lines = []
    for row in rows:
        d = date.fromisoformat(row["date"])
        open_at = datetime(d.year, d.month, d.day, tzinfo=UTC)
        close_at = open_at + timedelta(days=1) - timedelta(milliseconds=1)
        open_ms = int(open_at.timestamp() * 1000)
        close_ms = int(close_at.timestamp() * 1000)
        close = float(row["close"])
        open_price = close * 0.995
        high = close * 1.01
        low = open_price * 0.99
        csv_lines.append(",".join([
            str(open_ms),
            f"{open_price:.8f}",
            f"{high:.8f}",
            f"{low:.8f}",
            row["close"],
            "1000.0",
            str(close_ms),
            row["quote_volume_usd"],
            "100",
            "500.0",
            "25000000.0",
            "0",
        ]))
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("fixture.csv", "\n".join(csv_lines) + "\n")
    return buffer.getvalue()


def _bound_input(root, prefix, symbol, rows):
    archive_name = f"{symbol}-1d-2024-03.zip"
    archive_raw = _archive_bytes(rows)
    archive_ref = _write_bytes(root, f"{prefix}/archive.zip", archive_raw)
    checksum_ref = _write_bytes(
        root,
        f"{prefix}/archive.CHECKSUM",
        f"{archive_ref['sha256']}  {archive_name}\n".encode(),
    )
    last_day = date.fromisoformat(rows[-1]["date"])
    event_time_max = datetime(last_day.year, last_day.month, last_day.day, tzinfo=UTC)
    event_time_max += timedelta(days=1) - timedelta(milliseconds=1)
    proof = {
        "schema": "binance_public_archive_proof.v1",
        "source_id": BINANCE,
        "upstream_locator": (
            f"https://data.binance.vision/data/spot/monthly/klines/{symbol}/1d/{archive_name}"
        ),
        "archive_relpath": archive_ref["artifact_relpath"],
        "archive_sha256": archive_ref["sha256"],
        "checksum_relpath": checksum_ref["artifact_relpath"],
        "checksum_sha256": checksum_ref["sha256"],
        "event_time_max": event_time_max.isoformat().replace("+00:00", "Z"),
    }
    proof_ref = _write_json(root, f"{prefix}/source_proof.json", proof)
    artifact = {
        "schema": BOUND_ROWS_SCHEMA,
        "source_id": BINANCE,
        "venue_symbol": symbol,
        "rows": rows,
        "source_proof": proof_ref,
    }
    return _write_json(root, f"{prefix}/bound_rows.json", artifact)


def _record(spec, value, inputs):
    return {
        "source_id": spec["transform_id"],
        "value": value,
        "derivation": {
            "transform_id": spec["transform_id"],
            "transform_version": spec["transform_version"],
            "parameters": _transform_params(spec),
            "inputs": inputs,
        },
    }


def _snapshot(root):
    asset_rows = _daily_rows(DECISION, days=100, start=10.0, step=0.05)
    btc_rows = _daily_rows(DECISION, days=100, start=30000.0, step=50.0)
    asset_ref = _bound_input(root, "asset-bars", "TESTUSDT", asset_rows)
    btc_ref = _bound_input(root, "btc-bars", "BTCUSDT", btc_rows)
    return {
        "stable_asset_id": "test",
        "venue_symbol": "TESTUSDT",
        "decision_at": DECISION,
        "features": {
            "return_30d": _record(
                RETURN_TRANSFORM,
                compute_return_30d(asset_rows, decision_at=DECISION),
                [asset_ref],
            ),
            "volatility_30d": _record(
                VOLATILITY_TRANSFORM,
                compute_volatility_30d(asset_rows, decision_at=DECISION),
                [asset_ref],
            ),
            "regime": _record(
                REGIME_TRANSFORM,
                compute_btc_regime(btc_rows, decision_at=DECISION),
                [btc_ref],
            ),
        },
    }


def test_retained_archive_bound_outputs_pass(tmp_path):
    snapshot = _snapshot(tmp_path)
    validate_snapshot_derived_output_bindings(snapshot, tmp_path)


def test_arbitrary_return_value_is_rejected(tmp_path):
    snapshot = _snapshot(tmp_path)
    snapshot["features"]["return_30d"]["value"] += 0.5
    with pytest.raises(ValueError, match="return_30d value does not equal"):
        validate_snapshot_derived_output_bindings(snapshot, tmp_path)


def test_normalized_rows_must_match_retained_archive_bytes(tmp_path):
    snapshot = _snapshot(tmp_path)
    ref = snapshot["features"]["return_30d"]["derivation"]["inputs"][0]
    path = tmp_path / ref["artifact_relpath"]
    artifact = json.loads(path.read_text())
    artifact["rows"][-1]["close"] = "999999.0"
    raw = _json_bytes(artifact)
    path.write_bytes(raw)
    ref["sha256"] = hashlib.sha256(raw).hexdigest()
    snapshot["features"]["volatility_30d"]["derivation"]["inputs"][0]["sha256"] = ref["sha256"]
    with pytest.raises(ValueError, match="does not match retained Binance archive"):
        validate_snapshot_derived_output_bindings(snapshot, tmp_path)


def test_regime_must_use_btc_spot_archive(tmp_path):
    snapshot = _snapshot(tmp_path)
    snapshot["features"]["regime"]["derivation"]["inputs"] = snapshot["features"]["return_30d"]["derivation"]["inputs"]
    with pytest.raises(ValueError, match="venue_symbol mismatch|locator symbol mismatch"):
        validate_snapshot_derived_output_bindings(snapshot, tmp_path)


def test_transform_version_or_parameters_cannot_drift(tmp_path):
    snapshot = _snapshot(tmp_path)
    snapshot["features"]["volatility_30d"]["derivation"]["transform_version"] = "999"
    with pytest.raises(ValueError, match="transform_version violates frozen semantics"):
        validate_snapshot_derived_output_bindings(snapshot, tmp_path)
