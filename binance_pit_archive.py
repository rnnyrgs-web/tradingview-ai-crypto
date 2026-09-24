"""Fail-closed local verifier for frozen Binance PIT archive inputs.

This module is deliberately network-free. A source worker must first retain the
Binance-hosted ZIP and its colocated ``.CHECKSUM`` sidecar. Only then may these
helpers verify bytes and normalize the already-frozen kline inputs for C101-H.

Funding archive parsing is intentionally *not* implemented until the exact
Binance-hosted funding CSV schema is independently authenticated. The generic
funding-event chronology validator below can be used only after a separately
verified parser has produced source-native event timestamps/rates.
"""
from __future__ import annotations

import csv
import hashlib
import io
import math
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

HOUR_MS = 3_600_000
SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")


class ArchiveVerificationError(ValueError):
    """The retained source pair or its normalized chronology is not admissible."""


class FundingSchemaUnverified(ArchiveVerificationError):
    """Funding bytes must not be parsed until the exact source schema is proven."""


@dataclass(frozen=True)
class VerifiedArchive:
    archive_sha256: str
    checksum_sidecar_sha256: str
    archive_filename: str
    csv_member: str
    csv_bytes: bytes


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _parse_checksum_sidecar(sidecar: bytes, expected_filename: str) -> str:
    try:
        text = sidecar.decode("utf-8").strip()
    except UnicodeDecodeError as exc:
        raise ArchiveVerificationError("checksum sidecar must be UTF-8 text") from exc
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(lines) != 1:
        raise ArchiveVerificationError("checksum sidecar must contain exactly one non-empty record")
    parts = lines[0].split()
    if len(parts) != 2:
        raise ArchiveVerificationError("checksum sidecar must use '<sha256> <filename>' format")
    digest, filename = parts
    filename = filename.lstrip("*")
    if not SHA256_RE.fullmatch(digest):
        raise ArchiveVerificationError("checksum sidecar digest is not SHA-256")
    if filename != expected_filename:
        raise ArchiveVerificationError("checksum sidecar filename does not match retained archive")
    return digest.lower()


def verify_archive_pair(archive_path: Path, checksum_path: Path) -> VerifiedArchive:
    """Verify retained ZIP bytes against the exact retained checksum sidecar.

    One ZIP member is required. Directory entries, path traversal, nested paths,
    encrypted members, non-CSV members and ambiguous multi-file archives fail
    closed so downstream provenance has one exact raw table identity.
    """
    archive_bytes = archive_path.read_bytes()
    sidecar_bytes = checksum_path.read_bytes()
    expected = _parse_checksum_sidecar(sidecar_bytes, archive_path.name)
    actual = _sha256(archive_bytes)
    if actual != expected:
        raise ArchiveVerificationError("archive SHA-256 does not match retained checksum sidecar")

    try:
        with zipfile.ZipFile(io.BytesIO(archive_bytes), "r") as bundle:
            members = [info for info in bundle.infolist() if not info.is_dir()]
            if len(members) != 1:
                raise ArchiveVerificationError("archive must contain exactly one data member")
            member = members[0]
            name = member.filename
            if member.flag_bits & 0x1:
                raise ArchiveVerificationError("encrypted archives are not admissible")
            if not name.endswith(".csv") or name.startswith(("/", "\\")) or "/" in name or "\\" in name or name in {".", ".."}:
                raise ArchiveVerificationError("archive member must be one flat CSV file")
            csv_bytes = bundle.read(member)
    except zipfile.BadZipFile as exc:
        raise ArchiveVerificationError("retained archive is not a valid ZIP") from exc

    if not csv_bytes:
        raise ArchiveVerificationError("archive CSV is empty")
    return VerifiedArchive(
        archive_sha256=actual,
        checksum_sidecar_sha256=_sha256(sidecar_bytes),
        archive_filename=archive_path.name,
        csv_member=name,
        csv_bytes=csv_bytes,
    )


def _timestamp_to_ms(raw: str, *, timestamp_unit: str) -> int:
    try:
        value = int(raw)
    except (TypeError, ValueError) as exc:
        raise ArchiveVerificationError("timestamp must be an integer") from exc
    if timestamp_unit == "ms":
        result = value
    elif timestamp_unit == "us":
        # Binance spot archives use microseconds from 2025 onward. Source close
        # timestamps may end at the final microsecond of the interval, so retain
        # explicit source-unit semantics and floor only for canonical ms storage.
        result = value // 1000
    else:
        raise ArchiveVerificationError("timestamp_unit must be explicitly 'ms' or 'us'")
    if result <= 0:
        raise ArchiveVerificationError("timestamp must be positive")
    return result


def _finite_float(raw: str, field: str, *, positive: bool = False, nonnegative: bool = False) -> float:
    try:
        value = float(raw)
    except (TypeError, ValueError) as exc:
        raise ArchiveVerificationError(f"{field} must be numeric") from exc
    if not math.isfinite(value):
        raise ArchiveVerificationError(f"{field} must be finite")
    if positive and value <= 0:
        raise ArchiveVerificationError(f"{field} must be positive")
    if nonnegative and value < 0:
        raise ArchiveVerificationError(f"{field} must be non-negative")
    return value


def normalize_hourly_klines(csv_bytes: bytes, *, timestamp_unit: str) -> list[dict[str, Any]]:
    """Normalize Binance 12-column kline CSV with explicit source timestamp unit.

    Timestamp-unit inference is forbidden. The caller must bind ``ms`` or ``us``
    from authenticated source documentation / archive semantics before parsing.
    No return, signal or P&L is computed here.
    """
    try:
        text = csv_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ArchiveVerificationError("kline CSV must be UTF-8") from exc

    rows: list[dict[str, Any]] = []
    previous_open: int | None = None
    for line_no, raw in enumerate(csv.reader(io.StringIO(text)), start=1):
        if len(raw) != 12:
            raise ArchiveVerificationError(f"kline row {line_no} must have exactly 12 columns")
        open_ms = _timestamp_to_ms(raw[0], timestamp_unit=timestamp_unit)
        close_ms = _timestamp_to_ms(raw[6], timestamp_unit=timestamp_unit)
        if open_ms % HOUR_MS:
            raise ArchiveVerificationError(f"kline row {line_no} is off the UTC hourly grid")
        if close_ms < open_ms or close_ms >= open_ms + HOUR_MS:
            raise ArchiveVerificationError(f"kline row {line_no} close timestamp is outside its hour")
        if previous_open is not None and open_ms - previous_open != HOUR_MS:
            raise ArchiveVerificationError("kline timestamps contain a duplicate, gap, or non-hourly step")

        open_px = _finite_float(raw[1], "open", positive=True)
        high = _finite_float(raw[2], "high", positive=True)
        low = _finite_float(raw[3], "low", positive=True)
        close = _finite_float(raw[4], "close", positive=True)
        volume = _finite_float(raw[5], "volume", nonnegative=True)
        quote_volume = _finite_float(raw[7], "quote_volume", nonnegative=True)
        try:
            trades = int(raw[8])
        except (TypeError, ValueError) as exc:
            raise ArchiveVerificationError("trade count must be integer") from exc
        if trades < 0:
            raise ArchiveVerificationError("trade count must be non-negative")
        taker_buy_base = _finite_float(raw[9], "taker_buy_base", nonnegative=True)
        taker_buy_quote = _finite_float(raw[10], "taker_buy_quote", nonnegative=True)
        if high < max(open_px, close, low) or low > min(open_px, close, high):
            raise ArchiveVerificationError("impossible OHLC ordering")
        if taker_buy_base > volume + max(1e-12, abs(volume) * 1e-12):
            raise ArchiveVerificationError("taker-buy base volume exceeds total volume")
        if taker_buy_quote > quote_volume + max(1e-12, abs(quote_volume) * 1e-12):
            raise ArchiveVerificationError("taker-buy quote volume exceeds total quote volume")

        rows.append(
            {
                "open_ts_ms": open_ms,
                "close_ts_ms": close_ms,
                "open": open_px,
                "high": high,
                "low": low,
                "close": close,
                "volume": volume,
                "quote_volume": quote_volume,
                "trades": trades,
                "taker_buy_base": taker_buy_base,
                "taker_buy_quote": taker_buy_quote,
            }
        )
        previous_open = open_ms
    if not rows:
        raise ArchiveVerificationError("kline CSV contains no rows")
    return rows


def funding_archive_parser_unavailable(*_args: Any, **_kwargs: Any) -> None:
    """Hard boundary until the exact Binance-hosted funding CSV schema is proven."""
    raise FundingSchemaUnverified("Binance funding archive schema is not yet independently source-verified")


def validate_source_native_funding_events(events: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Validate already-parsed source-native funding events without 8h assumptions."""
    normalized: list[tuple[int, float]] = []
    for event in events:
        try:
            ts = int(event["funding_ts_ms"])
            rate = float(event["realized_funding_rate"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ArchiveVerificationError("funding event requires integer funding_ts_ms and numeric realized_funding_rate") from exc
        if ts <= 0 or not math.isfinite(rate):
            raise ArchiveVerificationError("funding event timestamp/rate is invalid")
        normalized.append((ts, rate))
    if not normalized:
        raise ArchiveVerificationError("funding event stream is empty")
    timestamps = [ts for ts, _ in normalized]
    if any(right <= left for left, right in zip(timestamps, timestamps[1:])):
        raise ArchiveVerificationError("funding event timestamps must be strictly increasing and unique")
    intervals = [right - left for left, right in zip(timestamps, timestamps[1:])]
    if any(interval <= 0 for interval in intervals):
        raise ArchiveVerificationError("funding intervals must be source-derived positive durations")
    return {
        "events": len(normalized),
        "first_funding_ts_ms": timestamps[0],
        "last_funding_ts_ms": timestamps[-1],
        "interval_seconds": [interval // 1000 for interval in intervals],
        "fixed_interval_assumed": False,
    }
