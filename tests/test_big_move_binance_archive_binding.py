import hashlib
import io
import zipfile

import pytest

from big_move_binance_archive_binding import (
    parse_spot_1d_kline_archive,
    verify_checksum_sidecar,
    verify_normalized_daily_rows,
)


def _zip(member, lines):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(member, "\n".join(lines) + "\n")
    return stream.getvalue()


def _row(open_time, close_time, *, close="110.0", quote="12345678.9", high="120", low="90"):
    return ",".join(
        [
            str(open_time), "100.0", high, low, close, "1000.0", str(close_time), quote,
            "42", "500.0", "6000000.0", "0",
        ]
    )


def test_checksum_sidecar_binds_exact_archive_and_filename():
    raw = _zip("BTCUSDT-1d-2024-01.csv", [_row(1704067200000, 1704153599999)])
    digest = hashlib.sha256(raw).hexdigest()
    sidecar = f"{digest}  BTCUSDT-1d-2024-01.zip\n".encode()
    assert verify_checksum_sidecar(raw, sidecar, "BTCUSDT-1d-2024-01.zip") == digest
    with pytest.raises(ValueError, match="filename mismatch"):
        verify_checksum_sidecar(raw, sidecar, "ETHUSDT-1d-2024-01.zip")


def test_parser_supports_documented_millisecond_and_microsecond_spot_timestamps():
    ms = _zip("BTCUSDT-1d-2024-01.csv", [_row(1704067200000, 1704153599999)])
    rows = parse_spot_1d_kline_archive(ms, decision_at="2024-01-03T00:00:00Z")
    assert rows[0]["date"] == "2024-01-01"
    assert rows[0]["close"] == "110.0"
    assert rows[0]["quote_asset_volume"] == "12345678.9"
    assert "quote_volume_usd" not in rows[0]

    micros = _zip(
        "BTCUSDT-1d-2025-01.csv",
        [_row(1735689600000000, 1735775999999999, close="111.0")],
    )
    rows = parse_spot_1d_kline_archive(micros, decision_at="2025-01-03T00:00:00Z")
    assert rows[0]["date"] == "2025-01-01"
    assert rows[0]["close"] == "111.0"


def test_normalized_close_and_quote_asset_volume_must_match_retained_archive():
    raw = _zip("BTCUSDT-1d-2024-01.csv", [_row(1704067200000, 1704153599999)])
    bound = verify_normalized_daily_rows(
        raw,
        [{"date": "2024-01-01", "close": "110.0", "quote_asset_volume": "12345678.9"}],
        decision_at="2024-01-03T00:00:00Z",
    )
    assert bound[0]["trade_count"] == 42

    with pytest.raises(ValueError, match="close does not match"):
        verify_normalized_daily_rows(
            raw,
            [{"date": "2024-01-01", "close": "999", "quote_asset_volume": "12345678.9"}],
            decision_at="2024-01-03T00:00:00Z",
        )

    with pytest.raises(ValueError, match="quote_asset_volume does not match"):
        verify_normalized_daily_rows(
            raw,
            [{"date": "2024-01-01", "close": "110.0", "quote_asset_volume": "999"}],
            decision_at="2024-01-03T00:00:00Z",
        )


def test_legacy_usd_labeled_quote_volume_is_not_accepted_as_source_native():
    raw = _zip("BTCUSDT-1d-2024-01.csv", [_row(1704067200000, 1704153599999)])
    with pytest.raises(ValueError, match="quote_asset_volume missing"):
        verify_normalized_daily_rows(
            raw,
            [{"date": "2024-01-01", "close": "110.0", "quote_volume_usd": "12345678.9"}],
            decision_at="2024-01-03T00:00:00Z",
        )


def test_post_cutoff_kline_cannot_be_bound():
    raw = _zip("BTCUSDT-1d-2024-01.csv", [_row(1704153600000, 1704239999999)])
    with pytest.raises(ValueError, match="absent from retained Binance archive"):
        verify_normalized_daily_rows(
            raw,
            [{"date": "2024-01-02", "close": "110.0", "quote_asset_volume": "12345678.9"}],
            decision_at="2024-01-02T12:00:00Z",
        )


def test_unsafe_or_ambiguous_archive_is_rejected():
    raw = _zip("../escape.csv", [_row(1704067200000, 1704153599999)])
    with pytest.raises(ValueError, match="unsafe"):
        parse_spot_1d_kline_archive(raw, decision_at="2024-01-03T00:00:00Z")

    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        archive.writestr("a.csv", _row(1704067200000, 1704153599999))
        archive.writestr("b.csv", _row(1704153600000, 1704239999999))
    with pytest.raises(ValueError, match="exactly one data member"):
        parse_spot_1d_kline_archive(stream.getvalue(), decision_at="2024-01-04T00:00:00Z")


def test_impossible_ohlc_is_rejected():
    raw = _zip(
        "BTCUSDT-1d-2024-01.csv",
        [_row(1704067200000, 1704153599999, close="110", high="105", low="90")],
    )
    with pytest.raises(ValueError, match="OHLC ordering"):
        parse_spot_1d_kline_archive(raw, decision_at="2024-01-03T00:00:00Z")
