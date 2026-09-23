"""Deterministic Binance spot 1d archive parser/binder for Cohort 001.

The historical gate must not trust a normalized price/volume row merely because it
references a retained Binance archive. This module parses the retained archive bytes
and binds normalized daily close / source-native quote-asset-volume observations back
to those bytes.

Binance kline field 7 is quote-asset volume. Its unit is the venue symbol's quote
asset (for example USDT for BTCUSDT); this module deliberately does not relabel that
provider-native measure as USD and grants no currency-conversion authority.

It intentionally does not decide cohort membership, open outcomes, form forecasts, or
connect to a broker. Fetching/capture provenance and any later PIT currency conversion
remain separate ingestion/scientific concerns.
"""

from __future__ import annotations

import csv
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import io
from pathlib import PurePosixPath
from typing import Any
import zipfile

UTC = timezone.utc
KLINE_COLUMNS = 12
MAX_ARCHIVE_MEMBER_BYTES = 64 * 1024 * 1024
MILLISECONDS_THRESHOLD = 10**14
MICROSECONDS_THRESHOLD = 10**15


def _utc(value: str, *, field: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError(f"{field} must be RFC3339 UTC ending in Z")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise ValueError(f"{field} must be valid RFC3339 UTC") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != UTC.utcoffset(parsed):
        raise ValueError(f"{field} must be UTC")
    return parsed


def _timestamp_to_datetime(raw: str, *, field: str) -> datetime:
    try:
        value = int(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be an integer epoch timestamp") from exc
    if value >= MICROSECONDS_THRESHOLD:
        seconds = value / 1_000_000
    elif value >= MILLISECONDS_THRESHOLD:
        # Values in this band are neither realistic Binance millisecond timestamps nor
        # the documented post-2025 microsecond representation.
        raise ValueError(f"{field} has ambiguous epoch precision")
    else:
        seconds = value / 1_000
    try:
        return datetime.fromtimestamp(seconds, tz=UTC)
    except (OverflowError, OSError, ValueError) as exc:
        raise ValueError(f"{field} is outside supported epoch range") from exc


def _decimal(raw: str, *, field: str, positive: bool = False) -> Decimal:
    try:
        value = Decimal(raw)
    except (InvalidOperation, TypeError) as exc:
        raise ValueError(f"{field} must be decimal") from exc
    if not value.is_finite():
        raise ValueError(f"{field} must be finite")
    if positive and value <= 0:
        raise ValueError(f"{field} must be > 0")
    if not positive and value < 0:
        raise ValueError(f"{field} must be >= 0")
    return value


def verify_checksum_sidecar(archive_bytes: bytes, checksum_bytes: bytes, expected_archive_name: str) -> str:
    """Verify an exact `sha256  filename` sidecar and return the archive digest."""
    if not isinstance(expected_archive_name, str) or not expected_archive_name or "/" in expected_archive_name:
        raise ValueError("expected_archive_name must be a simple filename")
    try:
        text = checksum_bytes.decode("utf-8").strip()
    except UnicodeDecodeError as exc:
        raise ValueError("checksum sidecar must be UTF-8") from exc
    parts = text.split()
    if len(parts) != 2:
        raise ValueError("checksum sidecar must contain exactly digest and filename")
    expected_digest, filename = parts
    if filename.lstrip("*") != expected_archive_name:
        raise ValueError("checksum sidecar filename mismatch")
    if len(expected_digest) != 64 or expected_digest.lower() != expected_digest:
        raise ValueError("checksum sidecar digest must be lowercase SHA-256")
    try:
        int(expected_digest, 16)
    except ValueError as exc:
        raise ValueError("checksum sidecar digest must be lowercase SHA-256") from exc
    actual = hashlib.sha256(archive_bytes).hexdigest()
    if actual != expected_digest:
        raise ValueError("Binance archive digest does not match checksum sidecar")
    return actual


def _safe_single_member(archive_bytes: bytes) -> tuple[str, bytes]:
    try:
        with zipfile.ZipFile(io.BytesIO(archive_bytes), "r") as archive:
            members = [info for info in archive.infolist() if not info.is_dir()]
            if len(members) != 1:
                raise ValueError("Binance kline archive must contain exactly one data member")
            info = members[0]
            path = PurePosixPath(info.filename)
            if path.is_absolute() or ".." in path.parts or len(path.parts) != 1:
                raise ValueError("Binance archive member path is unsafe")
            if not info.filename.lower().endswith(".csv"):
                raise ValueError("Binance kline archive member must be CSV")
            if info.flag_bits & 0x1:
                raise ValueError("encrypted Binance archive members are unsupported")
            if info.file_size > MAX_ARCHIVE_MEMBER_BYTES:
                raise ValueError("Binance kline archive member exceeds size limit")
            raw = archive.read(info)
    except zipfile.BadZipFile as exc:
        raise ValueError("Binance archive is not a valid ZIP") from exc
    return info.filename, raw


def parse_spot_1d_kline_archive(archive_bytes: bytes, *, decision_at: str) -> list[dict[str, Any]]:
    """Parse official 12-column spot klines and keep only completed pre-cutoff bars.

    Field 7 is returned as ``quote_asset_volume`` exactly because Binance defines it
    in the symbol's quote-asset unit. Callers must not infer USD semantics from this
    provider-native value.
    """
    cutoff = _utc(decision_at, field="decision_at")
    _, csv_bytes = _safe_single_member(archive_bytes)
    try:
        text = csv_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("Binance kline CSV must be UTF-8") from exc

    parsed: list[dict[str, Any]] = []
    seen_open_times: set[int] = set()
    for line_number, row in enumerate(csv.reader(io.StringIO(text)), start=1):
        if not row or all(not cell.strip() for cell in row):
            continue
        if len(row) != KLINE_COLUMNS:
            raise ValueError(f"Binance kline CSV line {line_number} must have 12 columns")
        try:
            open_raw = int(row[0])
            close_raw = int(row[6])
            trade_count = int(row[8])
        except ValueError as exc:
            raise ValueError(f"Binance kline CSV line {line_number} has invalid integer fields") from exc
        if open_raw in seen_open_times:
            raise ValueError("Binance kline archive contains duplicate open time")
        seen_open_times.add(open_raw)
        open_at = _timestamp_to_datetime(row[0], field="open_time")
        close_at = _timestamp_to_datetime(row[6], field="close_time")
        if close_at < open_at:
            raise ValueError("Binance kline close time precedes open time")
        if trade_count < 0:
            raise ValueError("Binance kline trade count must be nonnegative")
        open_price = _decimal(row[1], field="open", positive=True)
        high = _decimal(row[2], field="high", positive=True)
        low = _decimal(row[3], field="low", positive=True)
        close = _decimal(row[4], field="close", positive=True)
        volume = _decimal(row[5], field="volume")
        quote_volume = _decimal(row[7], field="quote_asset_volume")
        if high < max(open_price, close, low) or low > min(open_price, close, high):
            raise ValueError("Binance kline OHLC ordering is impossible")
        if close_at >= cutoff:
            continue
        parsed.append(
            {
                "open_time": open_at.isoformat().replace("+00:00", "Z"),
                "close_time": close_at.isoformat().replace("+00:00", "Z"),
                "date": open_at.date().isoformat(),
                "open": str(open_price),
                "high": str(high),
                "low": str(low),
                "close": str(close),
                "volume": str(volume),
                "quote_asset_volume": str(quote_volume),
                "trade_count": trade_count,
            }
        )
    parsed.sort(key=lambda item: item["open_time"])
    return parsed


def verify_normalized_daily_rows(
    archive_bytes: bytes,
    normalized_rows: list[dict[str, Any]],
    *,
    decision_at: str,
) -> list[dict[str, Any]]:
    """Bind normalized `{date, close, quote_asset_volume}` rows to archive bytes.

    A row carrying the legacy ``quote_volume_usd`` key does not satisfy this binder:
    raw Binance quote-asset volume has no implicit USD conversion authority.
    """
    if not isinstance(normalized_rows, list) or not normalized_rows:
        raise ValueError("normalized_rows must be a non-empty list")
    parsed = parse_spot_1d_kline_archive(archive_bytes, decision_at=decision_at)
    by_date = {row["date"]: row for row in parsed}
    if len(by_date) != len(parsed):
        raise ValueError("Binance archive contains duplicate UTC dates for 1d klines")

    bound: list[dict[str, Any]] = []
    seen_dates: set[str] = set()
    for index, row in enumerate(normalized_rows):
        if not isinstance(row, dict):
            raise ValueError(f"normalized_rows[{index}] must be an object")
        date = row.get("date")
        if not isinstance(date, str) or not date:
            raise ValueError(f"normalized_rows[{index}].date missing")
        if date in seen_dates:
            raise ValueError("normalized rows contain duplicate date")
        seen_dates.add(date)
        source = by_date.get(date)
        if source is None:
            raise ValueError(f"normalized row {date} is absent from retained Binance archive")
        for key in ("close", "quote_asset_volume"):
            if key not in row:
                raise ValueError(f"normalized row {date}.{key} missing")
            try:
                normalized = Decimal(str(row[key]))
                source_value = Decimal(source[key])
            except InvalidOperation as exc:
                raise ValueError(f"normalized row {date}.{key} must be decimal") from exc
            if normalized != source_value:
                raise ValueError(f"normalized row {date}.{key} does not match retained Binance archive")
        bound.append(source)
    return bound
