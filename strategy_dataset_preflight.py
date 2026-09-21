"""Outcome-blind qualification for Strategy Factory Cohort-001 source data.

This module deliberately stops at dataset identity, provenance, schema, cadence and
chronology. It never computes returns, signals, labels, P&L or any other economic
outcome. The immutable compressed source is authenticated before decompression;
OHLCV values are JSON-decoded only through the development cutoff. Protected-tail
rows are traversed structurally and only their timestamps are decoded so chronology
can be proven without opening protected market values.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from btc_leadlag_selection import (
    DATASET_PATH,
    FROZEN_DATASET_SHA256,
    _load_contract,
    _validate_histories,
    _validate_row,
)
from research_artifact import sha256_hex

EXPECTED_INSTRUMENTS = (
    "BTC-USDT-SWAP",
    "ETH-USDT-SWAP",
    "SOL-USDT-SWAP",
)
EXPECTED_BAR = "1H"
DEVELOPMENT_END_UTC = "2026-08-31T23:00:00+00:00"
PROTECTED_START_UTC = "2026-09-01T00:00:00+00:00"
HOUR_SECONDS = 3600
HOUR_MS = HOUR_SECONDS * 1000

# Git blob identity of the exact committed compressed source on canonical main.
# This is checked on compressed bytes before any gzip/JSON processing. It is
# mechanically paired below with the already-frozen normalized dataset SHA in
# the source contract, so a caller cannot redefine what "certified dataset"
# means by supplying a matching digest for altered market values.
FROZEN_DATASET_GIT_BLOB_SHA1 = "3a93beb4b1b4ef7f5d32b2936bf3119c692e7c15"

_WS = b" \t\r\n"


def _parse_hour(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("chronology boundary must be timezone-aware")
    parsed = parsed.astimezone(timezone.utc)
    if parsed.minute or parsed.second or parsed.microsecond:
        raise ValueError("chronology boundary must be aligned to the UTC hourly grid")
    return parsed


def _iso_from_ms(timestamp_ms: int) -> str:
    return datetime.fromtimestamp(timestamp_ms / 1000, timezone.utc).isoformat()


def _contains_forbidden_market_values(value: Any) -> bool:
    forbidden = {
        "open",
        "high",
        "low",
        "close",
        "volume",
        "quote_volume",
        "return",
        "pnl",
        "profit_factor",
    }
    if isinstance(value, dict):
        return any(
            str(key).lower() in forbidden or _contains_forbidden_market_values(item)
            for key, item in value.items()
        )
    if isinstance(value, list):
        return any(_contains_forbidden_market_values(item) for item in value)
    return False


def _git_blob_sha1(payload: bytes) -> str:
    """Return Git's content-addressed blob identity; not a security primitive."""
    header = f"blob {len(payload)}\0".encode("ascii")
    return hashlib.sha1(header + payload, usedforsecurity=False).hexdigest()


def _skip_ws(data: bytes, index: int) -> int:
    while index < len(data) and data[index] in _WS:
        index += 1
    return index


def _scan_string_end(data: bytes, start: int) -> int:
    if start >= len(data) or data[start] != ord('"'):
        raise ValueError("expected JSON string")
    index = start + 1
    escaped = False
    while index < len(data):
        byte = data[index]
        if escaped:
            escaped = False
        elif byte == ord("\\"):
            escaped = True
        elif byte == ord('"'):
            return index + 1
        index += 1
    raise ValueError("unterminated JSON string")


def _scan_value_end(data: bytes, start: int) -> int:
    """Return the exclusive end of one JSON value without decoding it."""
    start = _skip_ws(data, start)
    if start >= len(data):
        raise ValueError("missing JSON value")
    first = data[start]
    if first == ord('"'):
        return _scan_string_end(data, start)
    if first in (ord("{"), ord("[")):
        stack = [ord("}") if first == ord("{") else ord("]")]
        index = start + 1
        in_string = False
        escaped = False
        while index < len(data):
            byte = data[index]
            if in_string:
                if escaped:
                    escaped = False
                elif byte == ord("\\"):
                    escaped = True
                elif byte == ord('"'):
                    in_string = False
            elif byte == ord('"'):
                in_string = True
            elif byte == ord("{"):
                stack.append(ord("}"))
            elif byte == ord("["):
                stack.append(ord("]"))
            elif byte in (ord("}"), ord("]")):
                if not stack or byte != stack[-1]:
                    raise ValueError("malformed JSON nesting")
                stack.pop()
                if not stack:
                    return index + 1
            index += 1
        raise ValueError("unterminated JSON container")

    index = start
    while index < len(data) and data[index] not in b",]} \t\r\n":
        index += 1
    if index == start:
        raise ValueError("malformed JSON primitive")
    return index


def _decode_json_slice(data: bytes, start: int, end: int, field: str) -> Any:
    try:
        return json.loads(data[start:end].decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"malformed JSON for {field}") from exc


def _iter_object_fields(data: bytes) -> Iterator[tuple[str, int, int]]:
    """Yield object key + raw value bounds without decoding value payloads."""
    index = _skip_ws(data, 0)
    if index >= len(data) or data[index] != ord("{"):
        raise ValueError("expected JSON object")
    index += 1
    seen: set[str] = set()
    index = _skip_ws(data, index)
    if index < len(data) and data[index] == ord("}"):
        index = _skip_ws(data, index + 1)
        if index != len(data):
            raise ValueError("trailing bytes after JSON object")
        return

    while True:
        index = _skip_ws(data, index)
        key_end = _scan_string_end(data, index)
        key = _decode_json_slice(data, index, key_end, "object key")
        if not isinstance(key, str):
            raise ValueError("JSON object key must be a string")
        if key in seen:
            raise ValueError(f"duplicate JSON object key: {key}")
        seen.add(key)
        index = _skip_ws(data, key_end)
        if index >= len(data) or data[index] != ord(":"):
            raise ValueError("missing JSON object colon")
        value_start = _skip_ws(data, index + 1)
        value_end = _scan_value_end(data, value_start)
        yield key, value_start, value_end
        index = _skip_ws(data, value_end)
        if index >= len(data):
            raise ValueError("unterminated JSON object")
        if data[index] == ord("}"):
            index = _skip_ws(data, index + 1)
            if index != len(data):
                raise ValueError("trailing bytes after JSON object")
            return
        if data[index] != ord(","):
            raise ValueError("malformed JSON object separator")
        index += 1


def _iter_array_values(data: bytes) -> Iterator[tuple[int, int]]:
    index = _skip_ws(data, 0)
    if index >= len(data) or data[index] != ord("["):
        raise ValueError("expected JSON array")
    index += 1
    index = _skip_ws(data, index)
    if index < len(data) and data[index] == ord("]"):
        index = _skip_ws(data, index + 1)
        if index != len(data):
            raise ValueError("trailing bytes after JSON array")
        return

    while True:
        value_start = _skip_ws(data, index)
        value_end = _scan_value_end(data, value_start)
        yield value_start, value_end
        index = _skip_ws(data, value_end)
        if index >= len(data):
            raise ValueError("unterminated JSON array")
        if data[index] == ord("]"):
            index = _skip_ws(data, index + 1)
            if index != len(data):
                raise ValueError("trailing bytes after JSON array")
            return
        if data[index] != ord(","):
            raise ValueError("malformed JSON array separator")
        index += 1


def _timestamp_only_from_row(raw_row: bytes) -> int:
    """Decode only the row timestamp; never decode protected OHLCV fields."""
    timestamp: int | None = None
    for key, value_start, value_end in _iter_object_fields(raw_row):
        if key != "ts":
            continue
        if timestamp is not None:
            raise ValueError("duplicate timestamp in history row")
        value = _decode_json_slice(raw_row, value_start, value_end, "history timestamp")
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError("history timestamp must be an integer")
        timestamp = value
    if timestamp is None:
        raise ValueError("history row missing timestamp")
    if timestamp <= 0 or timestamp % HOUR_MS:
        raise ValueError("history timestamp must be on the positive UTC hourly grid")
    return timestamp


def _parse_development_view(
    uncompressed_json: bytes,
    *,
    cutoff_ms: int,
    protected_ms: int,
) -> tuple[dict[str, Any], dict[str, list[dict[str, float | int]]], dict[str, list[int]]]:
    """Parse metadata + development OHLCV while leaving protected OHLCV opaque.

    This helper intentionally has no authority to certify a dataset identity; the
    public qualification boundary authenticates compressed bytes first.
    """
    metadata: dict[str, Any] = {}
    development_histories: dict[str, list[dict[str, float | int]]] = {}
    source_timestamps: dict[str, list[int]] = {}
    histories_seen = False

    for key, value_start, value_end in _iter_object_fields(uncompressed_json):
        raw_value = uncompressed_json[value_start:value_end]
        if key != "histories":
            metadata[key] = _decode_json_slice(uncompressed_json, value_start, value_end, key)
            continue

        histories_seen = True
        for instrument, rows_start, rows_end in _iter_object_fields(raw_value):
            rows_raw = raw_value[rows_start:rows_end]
            clean_development: list[dict[str, float | int]] = []
            timestamps: list[int] = []
            protected_started = False
            for row_start, row_end in _iter_array_values(rows_raw):
                row_raw = rows_raw[row_start:row_end]
                timestamp = _timestamp_only_from_row(row_raw)
                timestamps.append(timestamp)
                if timestamp <= cutoff_ms:
                    if protected_started:
                        raise ValueError("development timestamp appears after protected chronology began")
                    row_value = _decode_json_slice(
                        row_raw,
                        0,
                        len(row_raw),
                        "development history row",
                    )
                    if not isinstance(row_value, dict):
                        raise ValueError("history row must be an object")
                    clean_development.append(_validate_row(row_value))
                elif timestamp >= protected_ms:
                    protected_started = True
                    # Deliberately do not json.loads/decode any protected OHLCV field.
                else:
                    raise ValueError("history timestamp falls inside undeclared chronology gap")
            development_histories[instrument] = clean_development
            source_timestamps[instrument] = timestamps

    if not histories_seen:
        raise ValueError("dataset missing histories")
    return metadata, development_histories, source_timestamps


def qualify_cohort001_dataset(
    path: Path = DATASET_PATH,
    *,
    development_end_utc: str = DEVELOPMENT_END_UTC,
    protected_start_utc: str = PROTECTED_START_UTC,
) -> dict[str, Any]:
    """Return a deterministic metadata-only qualification receipt.

    Authority is fail-closed: the compressed source must equal the pinned Git
    blob before it is decompressed. Protected OHLCV values are never JSON-decoded
    by this function; only protected timestamps are inspected for chronology.
    """
    development_end = _parse_hour(development_end_utc)
    protected_start = _parse_hour(protected_start_utc)
    if development_end >= protected_start:
        raise ValueError("development window must end strictly before protected evidence")
    if int((protected_start - development_end).total_seconds()) != HOUR_SECONDS:
        raise ValueError("Cohort-001 development/protected boundary must be contiguous hourly chronology")

    compressed_bytes = path.read_bytes()
    actual_blob_sha1 = _git_blob_sha1(compressed_bytes)
    if actual_blob_sha1 != FROZEN_DATASET_GIT_BLOB_SHA1:
        raise RuntimeError("immutable compressed selection dataset identity mismatch")
    try:
        uncompressed_json = gzip.decompress(compressed_bytes)
    except OSError as exc:
        raise RuntimeError("certified selection dataset gzip payload is invalid") from exc

    cutoff_ms = int(development_end.timestamp() * 1000)
    protected_ms = int(protected_start.timestamp() * 1000)
    metadata, development_histories, source_timestamps = _parse_development_view(
        uncompressed_json,
        cutoff_ms=cutoff_ms,
        protected_ms=protected_ms,
    )

    if metadata.get("source") != "OKX /api/v5/market/history-candles":
        raise RuntimeError("unexpected dataset source")
    if metadata.get("bar") != EXPECTED_BAR:
        raise RuntimeError("unexpected dataset bar interval")
    if tuple(metadata.get("fixed_instruments") or ()) != EXPECTED_INSTRUMENTS:
        raise RuntimeError("unexpected fixed instrument set or order")
    if set(source_timestamps) != set(EXPECTED_INSTRUMENTS):
        raise RuntimeError("unexpected histories instrument set")

    contract = _load_contract()
    source_contract = contract["source"]
    if tuple(source_contract["required_instruments"]) != EXPECTED_INSTRUMENTS:
        raise RuntimeError("certified source contract instrument set changed")
    if source_contract.get("normalized_rows_sha256") != FROZEN_DATASET_SHA256:
        raise RuntimeError("certified source contract normalized dataset identity changed")
    if (
        source_contract.get("frozen_dataset_ref")
        != "orchestration/evidence/liquidity_meanrev_001_cache/dataset.json.gz"
    ):
        raise RuntimeError("certified source contract dataset reference changed")

    # Reuse the existing market-value validator only on development rows.
    clean_development = _validate_histories(
        development_histories,
        contract,
        exact_dataset=False,
    )

    common_source_timestamps: list[int] | None = None
    common_development_timestamps: list[int] | None = None
    per_instrument: dict[str, dict[str, Any]] = {}
    for instrument in EXPECTED_INSTRUMENTS:
        timestamps = source_timestamps[instrument]
        if not timestamps:
            raise RuntimeError(f"no source rows for {instrument}")
        if any(b - a != HOUR_MS for a, b in zip(timestamps, timestamps[1:])):
            raise RuntimeError(
                f"missing, duplicate, or non-hourly source timestamp for {instrument}"
            )
        if common_source_timestamps is None:
            common_source_timestamps = timestamps
        elif timestamps != common_source_timestamps:
            raise RuntimeError("source timestamps are not exactly aligned across instruments")

        development_timestamps = [int(row["ts"]) for row in clean_development[instrument]]
        protected_timestamps = [ts for ts in timestamps if ts >= protected_ms]
        if not development_timestamps:
            raise RuntimeError(f"no development rows for {instrument}")
        if development_timestamps[-1] != cutoff_ms:
            raise RuntimeError(f"development cutoff is not present for {instrument}")
        if any(ts >= protected_ms for ts in development_timestamps):
            raise RuntimeError("protected timestamp leaked into development selection")
        if common_development_timestamps is None:
            common_development_timestamps = development_timestamps
        elif development_timestamps != common_development_timestamps:
            raise RuntimeError("development timestamps are not exactly aligned across instruments")

        per_instrument[instrument] = {
            "source_rows": len(timestamps),
            "development_rows": len(development_timestamps),
            "protected_rows_excluded": len(protected_timestamps),
            "source_start_utc": _iso_from_ms(timestamps[0]),
            "source_end_utc": _iso_from_ms(timestamps[-1]),
            "development_start_utc": _iso_from_ms(development_timestamps[0]),
            "development_end_utc": _iso_from_ms(development_timestamps[-1]),
        }

    common_source_timestamps = common_source_timestamps or []
    if len(EXPECTED_INSTRUMENTS) * len(common_source_timestamps) != int(
        source_contract["normalized_row_count"]
    ):
        raise RuntimeError("frozen dataset row count mismatch")
    if (
        not common_source_timestamps
        or _iso_from_ms(common_source_timestamps[0]) != source_contract["coverage_start_utc"]
        or _iso_from_ms(common_source_timestamps[-1]) != source_contract["coverage_end_utc"]
    ):
        raise RuntimeError("frozen dataset coverage mismatch")

    common_development_timestamps = common_development_timestamps or []
    timestamp_identity = sha256_hex(
        {
            "bar": EXPECTED_BAR,
            "instruments": list(EXPECTED_INSTRUMENTS),
            "timestamps_ms": common_development_timestamps,
        }
    )
    receipt: dict[str, Any] = {
        "schema_version": 2,
        "qualification_id": "COHORT-001-SELECTION-DATA-PREFLIGHT-v2",
        "status": "QUALIFIED_DEVELOPMENT_ONLY",
        "source_ref": str(path.relative_to(Path(__file__).resolve().parent))
        if path.is_relative_to(Path(__file__).resolve().parent)
        else str(path),
        "source_git_blob_sha1": actual_blob_sha1,
        "source_dataset_sha256": FROZEN_DATASET_SHA256,
        "source": metadata["source"],
        "bar": EXPECTED_BAR,
        "instruments": list(EXPECTED_INSTRUMENTS),
        "development_end_utc": development_end.isoformat(),
        "protected_start_utc": protected_start.isoformat(),
        "development_timestamp_identity_sha256": timestamp_identity,
        "development_common_timestamps": len(common_development_timestamps),
        "development_rows_total": len(common_development_timestamps) * len(EXPECTED_INSTRUMENTS),
        "protected_rows_excluded_total": sum(
            item["protected_rows_excluded"] for item in per_instrument.values()
        ),
        "per_instrument": per_instrument,
        "checks": {
            "exact_committed_compressed_git_blob": True,
            "canonical_normalized_dataset_identity_bound_via_contract": True,
            "exact_fixed_instrument_set": True,
            "hourly_grid_monotonic_unique_common": True,
            "finite_nonnegative_volume_and_positive_valid_ohlc_development_only": True,
            "development_cutoff_present": True,
            "protected_timestamp_excluded_from_development": True,
            "protected_ohlcv_json_decoded": False,
        },
        "economic_outcomes_computed": False,
        "strategy_signals_computed": False,
        "protected_market_values_exported": False,
        "untouched_oos_opened": False,
        "genuine_forward_opened": False,
        "research_only": True,
        "trade_authority": False,
        "promotion_authority": False,
        "broker_connected": False,
    }
    if _contains_forbidden_market_values(receipt):
        raise RuntimeError("qualification receipt attempted to expose market values or outcomes")
    receipt["receipt_sha256"] = sha256_hex(receipt)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, default=DATASET_PATH)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    receipt = qualify_cohort001_dataset(args.dataset)
    rendered = json.dumps(receipt, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
