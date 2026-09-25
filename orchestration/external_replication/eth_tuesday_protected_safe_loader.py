from __future__ import annotations

"""Frozen stdlib-only development loader for EXT-ETH-TUESDAY-DRIFT-001-v1.

This file intentionally duplicates the small protected-safe JSON traversal boundary
needed by the authority-bearing guarded Stage-1 path so its complete behavior can be
content-addressed as one file. It authenticates the exact committed compressed source
before decompression, fully decodes/validates OHLCV only through the frozen development
cutoff, and decodes timestamps only for the protected tail.

It computes no returns, signals, P&L, baselines, labels, or protected market values.
"""

import gzip
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

ROOT = Path(__file__).resolve().parents[2]
DATASET_PATH = (
    ROOT / "orchestration" / "evidence" / "liquidity_meanrev_001_cache" / "dataset.json.gz"
)

EXPECTED_SOURCE = "OKX /api/v5/market/history-candles"
EXPECTED_BAR = "1H"
EXPECTED_INSTRUMENTS = (
    "BTC-USDT-SWAP",
    "ETH-USDT-SWAP",
    "SOL-USDT-SWAP",
)
TARGET_INSTRUMENT = "ETH-USDT-SWAP"
FROZEN_DATASET_GIT_BLOB_SHA1 = "3a93beb4b1b4ef7f5d32b2936bf3119c692e7c15"
FROZEN_NORMALIZED_DATASET_SHA256 = "047c098bb2957557f8344ca30c32339ecac01b5067ae424b147d21c9e9caaf9f"
EXPECTED_COVERAGE_START_UTC = "2025-05-07T05:00:00+00:00"
EXPECTED_COVERAGE_END_UTC = "2026-09-19T03:00:00+00:00"
EXPECTED_NORMALIZED_ROW_COUNT = 35997
DEVELOPMENT_END_UTC = "2026-08-31T23:00:00+00:00"
PROTECTED_START_UTC = "2026-09-01T00:00:00+00:00"
HOUR_MS = 3_600_000
_WS = b" \t\r\n"


def _parse_hour(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("chronology boundary must be timezone-aware")
    parsed = parsed.astimezone(timezone.utc)
    if parsed.minute or parsed.second or parsed.microsecond:
        raise ValueError("chronology boundary must be aligned to the UTC hourly grid")
    return parsed


def _iso_from_ms(timestamp_ms: int) -> str:
    return datetime.fromtimestamp(timestamp_ms / 1000, timezone.utc).isoformat()


def _git_blob_sha1(payload: bytes) -> str:
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


def _validate_development_row(raw: dict[str, Any]) -> dict[str, float | int]:
    try:
        row: dict[str, float | int] = {
            "ts": int(raw["ts"]),
            **{
                key: float(raw[key])
                for key in ("open", "high", "low", "close", "volume", "quote_volume")
            },
        }
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("malformed development history row") from exc
    values = [
        float(row[key])
        for key in ("open", "high", "low", "close", "volume", "quote_volume")
    ]
    if int(row["ts"]) <= 0 or int(row["ts"]) % HOUR_MS:
        raise ValueError("development timestamp must be on the positive UTC hourly grid")
    if not all(math.isfinite(value) for value in values):
        raise ValueError("development row contains non-finite market value")
    if min(float(row[key]) for key in ("open", "high", "low", "close")) <= 0:
        raise ValueError("development OHLC must be positive")
    if float(row["volume"]) < 0 or float(row["quote_volume"]) < 0:
        raise ValueError("development volume must be non-negative")
    if float(row["high"]) < max(
        float(row["open"]), float(row["close"]), float(row["low"])
    ):
        raise ValueError("impossible development high")
    if float(row["low"]) > min(
        float(row["open"]), float(row["close"]), float(row["high"])
    ):
        raise ValueError("impossible development low")
    return row


def _parse_development_view(
    uncompressed_json: bytes,
    *,
    cutoff_ms: int,
    protected_ms: int,
) -> tuple[dict[str, Any], dict[str, list[dict[str, float | int]]], dict[str, list[int]]]:
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
                    decoded = _decode_json_slice(row_raw, 0, len(row_raw), "development history row")
                    if not isinstance(decoded, dict):
                        raise ValueError("history row must be an object")
                    clean_development.append(_validate_development_row(decoded))
                elif timestamp >= protected_ms:
                    protected_started = True
                    # PROTECTED OHLCV IS INTENTIONALLY NEVER JSON-DECODED HERE.
                else:
                    raise ValueError("history timestamp falls inside undeclared chronology gap")
            development_histories[instrument] = clean_development
            source_timestamps[instrument] = timestamps

    if not histories_seen:
        raise ValueError("dataset missing histories")
    return metadata, development_histories, source_timestamps


def load_frozen_eth_development_rows(path: Path = DATASET_PATH) -> tuple[dict[str, float | int], ...]:
    development_end = _parse_hour(DEVELOPMENT_END_UTC)
    protected_start = _parse_hour(PROTECTED_START_UTC)
    if int((protected_start - development_end).total_seconds()) != 3600:
        raise RuntimeError("development/protected boundary must be contiguous hourly chronology")

    compressed = path.read_bytes()
    if _git_blob_sha1(compressed) != FROZEN_DATASET_GIT_BLOB_SHA1:
        raise RuntimeError("immutable compressed dataset Git blob mismatch")
    try:
        raw = gzip.decompress(compressed)
    except OSError as exc:
        raise RuntimeError("frozen dataset gzip payload is invalid") from exc

    cutoff_ms = int(development_end.timestamp() * 1000)
    protected_ms = int(protected_start.timestamp() * 1000)
    metadata, development, source_timestamps = _parse_development_view(
        raw,
        cutoff_ms=cutoff_ms,
        protected_ms=protected_ms,
    )

    if metadata.get("source") != EXPECTED_SOURCE:
        raise RuntimeError("unexpected frozen dataset source")
    if metadata.get("bar") != EXPECTED_BAR:
        raise RuntimeError("unexpected frozen dataset cadence")
    if tuple(metadata.get("fixed_instruments") or ()) != EXPECTED_INSTRUMENTS:
        raise RuntimeError("unexpected frozen dataset instrument set/order")
    if tuple(source_timestamps) != EXPECTED_INSTRUMENTS:
        raise RuntimeError("unexpected histories instrument set/order")

    common_source: list[int] | None = None
    common_development: list[int] | None = None
    for instrument in EXPECTED_INSTRUMENTS:
        timestamps = source_timestamps[instrument]
        if not timestamps:
            raise RuntimeError(f"no source rows for {instrument}")
        if any(b - a != HOUR_MS for a, b in zip(timestamps, timestamps[1:])):
            raise RuntimeError(f"missing, duplicate, or non-hourly source timestamp for {instrument}")
        if common_source is None:
            common_source = timestamps
        elif timestamps != common_source:
            raise RuntimeError("source timestamps are not exactly aligned across instruments")

        rows = development[instrument]
        development_ts = [int(row["ts"]) for row in rows]
        if not development_ts or development_ts[-1] != cutoff_ms:
            raise RuntimeError(f"development cutoff is missing for {instrument}")
        if any(ts >= protected_ms for ts in development_ts):
            raise RuntimeError("protected timestamp leaked into development rows")
        if any(b - a != HOUR_MS for a, b in zip(development_ts, development_ts[1:])):
            raise RuntimeError(f"development timestamps are not contiguous for {instrument}")
        if common_development is None:
            common_development = development_ts
        elif development_ts != common_development:
            raise RuntimeError("development timestamps are not exactly aligned across instruments")

    common_source = common_source or []
    if len(EXPECTED_INSTRUMENTS) * len(common_source) != EXPECTED_NORMALIZED_ROW_COUNT:
        raise RuntimeError("frozen dataset row count mismatch")
    if (
        not common_source
        or _iso_from_ms(common_source[0]) != EXPECTED_COVERAGE_START_UTC
        or _iso_from_ms(common_source[-1]) != EXPECTED_COVERAGE_END_UTC
    ):
        raise RuntimeError("frozen dataset coverage mismatch")

    # Only development rows for the frozen target instrument leave this boundary.
    return tuple(dict(row) for row in development[TARGET_INSTRUMENT])
