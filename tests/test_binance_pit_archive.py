from __future__ import annotations

import hashlib
import io
import zipfile
from pathlib import Path

import pytest

from binance_pit_archive import (
    ArchiveVerificationError,
    FundingSchemaUnverified,
    funding_archive_parser_unavailable,
    normalize_hourly_klines,
    validate_source_native_funding_events,
    verify_archive_pair,
)


def _kline_row(open_ts: int, close_ts: int) -> str:
    return ",".join(
        map(
            str,
            [
                open_ts,
                "100.0",
                "102.0",
                "99.0",
                "101.0",
                "10.0",
                close_ts,
                "1005.0",
                25,
                "4.0",
                "402.0",
                "0",
            ],
        )
    )


def _zip_bytes(member: str, payload: bytes, *, extra: tuple[str, bytes] | None = None) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        bundle.writestr(member, payload)
        if extra:
            bundle.writestr(extra[0], extra[1])
    return buffer.getvalue()


def _write_pair(tmp_path: Path, archive_name: str, archive_bytes: bytes, *, checksum: str | None = None, checksum_name: str | None = None):
    archive = tmp_path / archive_name
    sidecar = tmp_path / f"{archive_name}.CHECKSUM"
    archive.write_bytes(archive_bytes)
    digest = checksum or hashlib.sha256(archive_bytes).hexdigest()
    sidecar.write_text(f"{digest}  {checksum_name or archive_name}\n", encoding="utf-8")
    return archive, sidecar


def test_verified_archive_binds_exact_zip_checksum_and_single_csv(tmp_path):
    payload = (_kline_row(1735689600000, 1735693199999) + "\n").encode()
    archive_bytes = _zip_bytes("BTCUSDT-1h-2025-01.csv", payload)
    archive, sidecar = _write_pair(tmp_path, "BTCUSDT-1h-2025-01.zip", archive_bytes)

    verified = verify_archive_pair(archive, sidecar)

    assert verified.archive_sha256 == hashlib.sha256(archive_bytes).hexdigest()
    assert verified.checksum_sidecar_sha256 == hashlib.sha256(sidecar.read_bytes()).hexdigest()
    assert verified.csv_member == "BTCUSDT-1h-2025-01.csv"
    assert verified.csv_bytes == payload


def test_archive_checksum_or_filename_mismatch_fails_closed(tmp_path):
    archive_bytes = _zip_bytes("BTCUSDT.csv", b"x")
    archive, sidecar = _write_pair(tmp_path, "BTCUSDT.zip", archive_bytes, checksum="0" * 64)
    with pytest.raises(ArchiveVerificationError, match="does not match"):
        verify_archive_pair(archive, sidecar)

    archive, sidecar = _write_pair(tmp_path, "BTCUSDT-2.zip", archive_bytes, checksum_name="OTHER.zip")
    with pytest.raises(ArchiveVerificationError, match="filename"):
        verify_archive_pair(archive, sidecar)


def test_ambiguous_or_nested_archive_members_fail_closed(tmp_path):
    two_files = _zip_bytes("a.csv", b"a", extra=("b.csv", b"b"))
    archive, sidecar = _write_pair(tmp_path, "two.zip", two_files)
    with pytest.raises(ArchiveVerificationError, match="exactly one"):
        verify_archive_pair(archive, sidecar)

    nested = _zip_bytes("../escape.csv", b"a")
    archive, sidecar = _write_pair(tmp_path, "nested.zip", nested)
    with pytest.raises(ArchiveVerificationError, match="flat CSV"):
        verify_archive_pair(archive, sidecar)


def test_spot_2025_microsecond_klines_require_explicit_unit_and_normalize_without_inference():
    first = _kline_row(1735689600000000, 1735693199999999)
    second = _kline_row(1735693200000000, 1735696799999999)
    payload = f"{first}\n{second}\n".encode()

    rows = normalize_hourly_klines(payload, timestamp_unit="us")
    assert [row["open_ts_ms"] for row in rows] == [1735689600000, 1735693200000]
    assert [row["close_ts_ms"] for row in rows] == [1735693199999, 1735696799999]

    # The exact first rejecting invariant is an implementation detail. The scientific
    # contract is that declaring microsecond source rows as milliseconds fails closed.
    with pytest.raises(ArchiveVerificationError):
        normalize_hourly_klines(payload, timestamp_unit="ms")
    with pytest.raises(ArchiveVerificationError, match="explicitly"):
        normalize_hourly_klines(payload, timestamp_unit="infer")


def test_kline_duplicate_gap_and_impossible_market_values_fail_closed():
    duplicate = (
        _kline_row(1735689600000, 1735693199999)
        + "\n"
        + _kline_row(1735689600000, 1735693199999)
        + "\n"
    ).encode()
    with pytest.raises(ArchiveVerificationError, match="duplicate, gap"):
        normalize_hourly_klines(duplicate, timestamp_unit="ms")

    columns = _kline_row(1735689600000, 1735693199999).split(",")
    columns[2] = "98.0"  # high below open/close
    with pytest.raises(ArchiveVerificationError, match="OHLC"):
        normalize_hourly_klines((",".join(columns) + "\n").encode(), timestamp_unit="ms")

    columns = _kline_row(1735689600000, 1735693199999).split(",")
    columns[9] = "11.0"  # taker-buy base > total volume
    with pytest.raises(ArchiveVerificationError, match="taker-buy base"):
        normalize_hourly_klines((",".join(columns) + "\n").encode(), timestamp_unit="ms")


def test_funding_archive_parser_remains_hard_blocked_until_source_schema_is_authenticated():
    with pytest.raises(FundingSchemaUnverified, match="not yet independently source-verified"):
        funding_archive_parser_unavailable(b"untrusted funding bytes")


def test_funding_intervals_are_derived_from_source_events_not_forced_to_eight_hours():
    result = validate_source_native_funding_events(
        [
            {"funding_ts_ms": 1_700_000_000_000, "realized_funding_rate": "0.0001"},
            {"funding_ts_ms": 1_700_014_400_000, "realized_funding_rate": "0.0002"},  # 4h
            {"funding_ts_ms": 1_700_021_600_000, "realized_funding_rate": "-0.0001"},  # 2h
        ]
    )
    assert result["interval_seconds"] == [14_400, 7_200]
    assert result["fixed_interval_assumed"] is False

    with pytest.raises(ArchiveVerificationError, match="strictly increasing"):
        validate_source_native_funding_events(
            [
                {"funding_ts_ms": 1_700_000_000_000, "realized_funding_rate": 0.0},
                {"funding_ts_ms": 1_700_000_000_000, "realized_funding_rate": 0.0},
            ]
        )
