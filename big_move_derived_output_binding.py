"""Deterministic output binding for accepted Cohort 001 derived market features.

The generic Cohort-001 preflight already verifies retained artifact bytes and source
proofs. This module closes a different integrity gap: a derived record must also prove
that its *claimed value* is the deterministic result of retained Binance spot kline
bytes, not merely a caller-supplied number attached to authentic inputs.

Only pre-outcome market features are handled here. Sector/classification remains a
separate unresolved binding because its mechanical primary-document classifier has
not yet been frozen strongly enough for authoritative label opening.

No outcome data, forecast formation, promotion or broker path is touched.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
from typing import Any
from urllib.parse import urlsplit

from big_move_binance_archive_binding import (
    verify_checksum_sidecar,
    verify_normalized_daily_rows,
)
from big_move_feature_derivations import (
    REGIME_TRANSFORM,
    RETURN_TRANSFORM,
    VOLATILITY_TRANSFORM,
    compute_btc_regime,
    compute_return_30d,
    compute_volatility_30d,
    value_matches,
)

UTC = timezone.utc
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
MAX_RETAINED_BYTES = 128 * 1024 * 1024
BINANCE_SOURCE_ID = "BINANCE_PUBLIC_DATA_SPOT_RAW"
BOUND_ROWS_SCHEMA = "binance_spot_daily_kline_rows.v1"
COMPLETED_DERIVED_FIELDS = ("return_30d", "volatility_30d", "regime")


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


def _verified_bytes(root: Path, ref: dict[str, Any], *, field: str) -> bytes:
    if not isinstance(ref, dict):
        raise ValueError(f"{field} reference must be an object")
    sha = ref.get("sha256")
    if not isinstance(sha, str) or not SHA256_RE.fullmatch(sha):
        raise ValueError(f"{field}.sha256 must be lowercase SHA-256")
    path = _safe_path(root, ref.get("artifact_relpath"), field=field)
    try:
        if path.stat().st_size > MAX_RETAINED_BYTES:
            raise ValueError(f"{field} retained artifact is too large")
        raw = path.read_bytes()
    except OSError as exc:
        raise ValueError(f"{field} retained artifact is unavailable") from exc
    if hashlib.sha256(raw).hexdigest() != sha:
        raise ValueError(f"{field} retained artifact SHA-256 mismatch")
    return raw


def _verified_json(root: Path, ref: Any, *, field: str) -> dict[str, Any]:
    raw = _verified_bytes(root, ref, field=field)
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{field} retained artifact must be JSON") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{field} retained artifact must be an object")
    return value


def _exact_parameters(spec: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in spec.items()
        if key not in {"transform_id", "transform_version", "metric"}
    }


def _validate_transform(record: dict[str, Any], spec: dict[str, Any], *, field: str) -> list[dict[str, Any]]:
    if not isinstance(record, dict):
        raise ValueError(f"{field} evidence must be an object")
    derivation = record.get("derivation")
    if not isinstance(derivation, dict):
        raise ValueError(f"{field}.derivation missing")
    if derivation.get("transform_id") != spec["transform_id"]:
        raise ValueError(f"{field}.derivation.transform_id violates frozen semantics")
    if derivation.get("transform_version") != spec["transform_version"]:
        raise ValueError(f"{field}.derivation.transform_version violates frozen semantics")
    if derivation.get("parameters") != _exact_parameters(spec):
        raise ValueError(f"{field}.derivation.parameters violate frozen semantics")
    inputs = derivation.get("inputs")
    if not isinstance(inputs, list) or not inputs:
        raise ValueError(f"{field}.derivation.inputs must be non-empty")
    if any(not isinstance(ref, dict) for ref in inputs):
        raise ValueError(f"{field}.derivation.inputs must contain only references")
    return inputs


def _approved_binance_locator(locator: Any, expected_symbol: str, *, field: str) -> str:
    if not isinstance(locator, str) or not locator.strip():
        raise ValueError(f"{field} Binance upstream locator missing")
    parsed = urlsplit(locator)
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or host != "data.binance.vision" or parsed.username or parsed.password:
        raise ValueError(f"{field} Binance upstream locator is not approved")
    path = PurePosixPath(parsed.path)
    symbol = expected_symbol.upper()
    parts = {part.upper() for part in path.parts}
    if symbol not in parts:
        raise ValueError(f"{field} Binance locator symbol mismatch")
    if "KLINES" not in parts or "1D" not in parts:
        raise ValueError(f"{field} requires Binance spot 1d kline archive")
    filename = path.name
    if not filename.lower().endswith(".zip"):
        raise ValueError(f"{field} Binance locator must identify a ZIP archive")
    return filename


def _bound_rows_for_inputs(
    inputs: list[dict[str, Any]],
    *,
    artifact_root: Path,
    decision_at: str,
    expected_symbol: str,
    field: str,
) -> list[dict[str, Any]]:
    decision = _utc(decision_at, field="decision_at")
    rows: list[dict[str, Any]] = []
    seen_dates: set[str] = set()

    for index, ref in enumerate(inputs):
        input_field = f"{field}.derivation.inputs[{index}]"
        artifact = _verified_json(artifact_root, ref, field=input_field)
        if artifact.get("schema") != BOUND_ROWS_SCHEMA:
            raise ValueError(f"{input_field} must use {BOUND_ROWS_SCHEMA}")
        if artifact.get("source_id") != BINANCE_SOURCE_ID:
            raise ValueError(f"{input_field}.source_id must be {BINANCE_SOURCE_ID}")
        if artifact.get("venue_symbol") != expected_symbol:
            raise ValueError(f"{input_field}.venue_symbol mismatch")
        normalized_rows = artifact.get("rows")
        if not isinstance(normalized_rows, list) or not normalized_rows:
            raise ValueError(f"{input_field}.rows must be non-empty")

        proof = _verified_json(artifact_root, artifact.get("source_proof"), field=f"{input_field}.source_proof")
        if proof.get("schema") != "binance_public_archive_proof.v1":
            raise ValueError(f"{input_field} requires binance_public_archive_proof.v1")
        filename = _approved_binance_locator(
            proof.get("upstream_locator"), expected_symbol, field=input_field
        )
        archive_ref = {
            "artifact_relpath": proof.get("archive_relpath"),
            "sha256": proof.get("archive_sha256"),
        }
        checksum_ref = {
            "artifact_relpath": proof.get("checksum_relpath"),
            "sha256": proof.get("checksum_sha256"),
        }
        archive_bytes = _verified_bytes(artifact_root, archive_ref, field=f"{input_field}.archive")
        checksum_bytes = _verified_bytes(artifact_root, checksum_ref, field=f"{input_field}.checksum")
        verify_checksum_sidecar(archive_bytes, checksum_bytes, filename)

        event_time_max = _utc(proof.get("event_time_max"), field=f"{input_field}.event_time_max")
        if event_time_max > decision:
            raise ValueError(f"{input_field} includes post-decision events")

        bound = verify_normalized_daily_rows(
            archive_bytes,
            normalized_rows,
            decision_at=decision_at,
        )
        for row in bound:
            date = row["date"]
            if date in seen_dates:
                raise ValueError(f"{field} derived inputs contain duplicate UTC date {date}")
            seen_dates.add(date)
            rows.append(row)

    rows.sort(key=lambda item: item["date"])
    return rows


def validate_snapshot_derived_output_bindings(
    snapshot: dict[str, Any],
    artifact_root: str | Path,
) -> None:
    """Recompute accepted market-derived fields from retained authenticated archives."""
    if not isinstance(snapshot, dict):
        raise ValueError("snapshot must be an object")
    root = Path(artifact_root)
    decision_at = snapshot.get("decision_at")
    _utc(decision_at, field="decision_at")
    symbol = snapshot.get("venue_symbol")
    if not isinstance(symbol, str) or not symbol.strip():
        raise ValueError("venue_symbol missing")
    features = snapshot.get("features")
    if not isinstance(features, dict):
        raise ValueError("features missing")

    return_record = features.get("return_30d")
    return_inputs = _validate_transform(return_record, RETURN_TRANSFORM, field="return_30d")
    return_rows = _bound_rows_for_inputs(
        return_inputs,
        artifact_root=root,
        decision_at=decision_at,
        expected_symbol=symbol,
        field="return_30d",
    )
    computed_return = compute_return_30d(return_rows, decision_at=decision_at)
    if not value_matches(return_record.get("value"), computed_return):
        raise ValueError("return_30d value does not equal retained-archive computation")

    volatility_record = features.get("volatility_30d")
    volatility_inputs = _validate_transform(
        volatility_record, VOLATILITY_TRANSFORM, field="volatility_30d"
    )
    volatility_rows = _bound_rows_for_inputs(
        volatility_inputs,
        artifact_root=root,
        decision_at=decision_at,
        expected_symbol=symbol,
        field="volatility_30d",
    )
    computed_volatility = compute_volatility_30d(volatility_rows, decision_at=decision_at)
    if not value_matches(volatility_record.get("value"), computed_volatility):
        raise ValueError("volatility_30d value does not equal retained-archive computation")

    regime_record = features.get("regime")
    regime_inputs = _validate_transform(regime_record, REGIME_TRANSFORM, field="regime")
    regime_rows = _bound_rows_for_inputs(
        regime_inputs,
        artifact_root=root,
        decision_at=decision_at,
        expected_symbol="BTCUSDT",
        field="regime",
    )
    computed_regime = compute_btc_regime(regime_rows, decision_at=decision_at)
    if regime_record.get("value") != computed_regime:
        raise ValueError("regime value does not equal retained BTC-archive computation")
